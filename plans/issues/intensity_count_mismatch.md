# 🐛 Issue: Mismatch Giữa `total_videos_watched` và `high/low_intensity_count`

**Ngày phát hiện:** 27/05/2026  
**Mức độ:** ⚠️ Medium — ảnh hưởng độ chính xác Fatigue Score  
**Trạng thái:** 🔵 Đang theo dõi (một phần tự hết sau fix Phase 1)

---

## 📋 Mô Tả Vấn Đề

Trong `feed_sessions`, có **2 field đếm video** nhưng được tính bằng **2 cơ chế hoàn toàn khác nhau**, dẫn đến mismatch khi có duplicate behavior logs:

| Field | Nguồn dữ liệu | Thời điểm tính | Logic dedup |
|---|---|---|---|
| `total_videos_watched` | `behavior_logs` (aggregation) | **Khi kết thúc session** (`end_session`) | ✅ `len(set(video_ids))` — chỉ tính unique |
| `high_intensity_count` | `_update_session_intensity()` | **Real-time** sau mỗi `record_behavior_log()` | ❌ `$inc` mù quáng — không dedup |
| `low_intensity_count` | `_update_session_intensity()` | **Real-time** sau mỗi `record_behavior_log()` | ❌ `$inc` mù quáng — không dedup |

---

## 🔎 Root Cause

### Luồng gây lỗi (trước khi fix Phase 1)

```
User dùng touchpad lướt nhẹ (scroll < 20%)
  ↓
setActiveIndex thay đổi → Video 1 bị "rời" → cleanup fires → behavior_log #1 bắn
  ↓
Touchpad snap lại → Video 1 active lại
  ↓
setActiveIndex thay đổi → cleanup fires lần 2 → behavior_log #2 bắn
```

**Kết quả:**
- `behavior_logs` có **2 documents** với cùng `video_id` trong session
- `_update_session_intensity()` được gọi **2 lần** → `high_intensity_count += 2`
- Nhưng `total_videos_watched` vẫn là **1** (vì dedup bằng `set()` khi end session)

→ **Fatigue Score bị tính sai** vì `high_intensity_ratio` dùng `high_intensity_count / total_videos_watched` sẽ bị inflate.

---

## 📍 Vị Trí Code Liên Quan

### `interaction_service.py` — hàm `_update_session_intensity()`

```python
# File: backend/app/services/interaction_service.py

async def _update_session_intensity(self, session_id: str, video_id: str) -> None:
    """Update high/low intensity counts for the session based on video's intensity_level."""
    try:
        video = await self._video_repo.find_by_id(video_id)
        if video and video.get("intensity_level"):
            await self._session_repo.update_intensity_count(
                session_id, video["intensity_level"]
            )
    except Exception as exc:
        logger.warning(f"Intensity count update failed: {exc}")
```

❌ **Vấn đề:** Không kiểm tra `video_id` đã được tính vào intensity của session chưa.

### `interaction_service.py` — hàm `end_session()` (đã đúng)

```python
# File: backend/app/services/interaction_service.py

# Count unique video IDs watched in this session
unique_video_ids = {log.get("video_id") for log in logs if log.get("video_id")}
total_videos_watched = len(unique_video_ids)  # ✅ Dedup bằng set()
```

✅ **Đúng:** Dùng `set()` để dedup, chỉ tính unique videos.

---

## ✅ Trạng Thái Fix

### Fix đã áp dụng (Phase 1 — Feed.tsx Scroll Threshold)

Sau khi implement **UI Scroll Threshold 20%** trong `Feed.tsx`:
- Mỗi video chỉ bắn **đúng 1 behavior_log** khi rời
- `_update_session_intensity()` chỉ được gọi **1 lần per video**
- Mismatch tự hết trong điều kiện bình thường

### Fix chưa áp dụng (Hardened Dedup — tùy chọn)

Để đảm bảo tuyệt đối, có thể thêm dedup trong `_update_session_intensity()`:

```python
# Ý tưởng — chưa implement

async def _update_session_intensity(self, session_id: str, video_id: str) -> None:
    """Update high/low intensity counts — chỉ tính mỗi video_id 1 lần per session."""
    try:
        # Kiểm tra xem video_id này đã được tính intensity chưa
        # (dùng Redis seen-set hoặc check behavior_log count cho video_id này)
        existing_logs_for_video = await self._log_repo.find_many({
            "session_id": session_id,
            "video_id": video_id
        }, limit=2)
        
        if len(existing_logs_for_video) > 1:
            # Đã có log trước đó cho video này → bỏ qua, không $inc nữa
            return
        video = await self._video_repo.find_by_id(video_id)
        
        if video and video.get("intensity_level"):
            await self._session_repo.update_intensity_count(
                session_id, video["intensity_level"]
            )
    except Exception as exc:
        logger.warning(f"Intensity count update failed: {exc}")
```

> **Lưu ý:** Cách trên có thêm 1 DB query. Cân nhắc dùng Redis seen-set (đã có sẵn) để dedup nhanh hơn.

---

## 🎯 Tác Động Lên Fatigue Score

Fatigue Score có thành phần `high_intensity_ratio`:

```
fatigue_score =
  (avg_swipe_speed / 1500 * 30)
  + ((1 - avg_watch_pct) * 30)
  + (high_intensity_ratio * 25)   ← BỊ ẢNH HƯỞNG
  + (passive_ratio * 15)
```

Nếu `high_intensity_count` bị inflate gấp đôi → `fatigue_score` bị đẩy cao hơn thực tế → user có thể bị trigger Mindful Feed sớm hơn cần thiết.

---

## 📌 Quyết Định

| Lựa chọn | Mô tả | Trạng thái |
|---|---|---|
| **Chấp nhận** Phase 1 fix là đủ | Scroll threshold 20% ngăn duplicate logs | ✅ Đã áp dụng |
| **Hardened fix** thêm dedup trong `_update_session_intensity()` | Bảo vệ thêm nếu có edge case khác tạo duplicate logs | ⬜ Chưa implement — cần quyết định |

---

## 🔗 Liên Quan

- [duplicate_behavior_log_fix_plan.md](../duplicate_behavior_log_fix_plan.md) — Kế hoạch fix duplicate behavior log
- `backend/app/services/interaction_service.py` — L360-379: `_update_session_metrics_pipeline`, `_update_session_intensity`
- `backend/app/services/interaction_service.py` — L254-287: `end_session` (có dedup đúng)
- `backend/app/repositories/feed_session_repository.py` — L49-65: `update_intensity_count`
