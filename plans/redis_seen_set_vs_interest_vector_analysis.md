# 🔍 Redis Seen-Set vs Interest Vector: Phân tích & Đề xuất cải thiện

**Ngày:** 26/05/2026
**Tác giả:** AI Assistant
**Scope:** Làm rõ mối quan hệ giữa `behavior_log`, `interaction`, `Redis seen-set`, và `interest_vector`

---

## 📋 Mục lục

1. [Bản đồ dữ liệu hiện tại](#1-bản-đồ-dữ-liệu-hiện-tại)
2. [Xác nhận: Redis lưu đúng hay sai?](#2-xác-nhận-redis-lưu-đúng-hay-sai)
3. [Interest vector dựa vào gì?](#3-interest-vector-dựa-vào-gì)
4. [Vấn đề mà bạn phát hiện](#4-vấn-đề-mà-bạn-phát-hiện)
5. [Kết luận & Đề xuất](#5-kết-luận--đề-xuất)

---

## 1. Bản đồ dữ liệu hiện tại

Trước hết, hãy phân biệt rõ 2 khái niệm hoàn toàn khác nhau trong hệ thống:

### Collection `behavior_logs` — MỌI video user nhìn thấy (passive)

```
Trigger:  FE gửi POST /behavior-logs mỗi khi user SWIPE qua 1 video
Dữ liệu: { video_id, swipe_speed, watch_duration, is_interaction, topic }
Mục đích:
  ✅ Tính fatigue_score (Phase 2)
  ✅ Theo dõi "đã xem" (dedup) — user đã LƯỚT QUA video này rồi
  ❌ KHÔNG dùng để tính interest_vector
```

### Collection `interactions` — Hành động CHỦ ĐỘNG của user (explicit)

```
Trigger:  FE gửi POST /interactions khi user LIKE / SKIP / REPLAY / COMMENT / SHARE
Dữ liệu: { video_id, type: "like"|"skip"|"replay"..., watch_duration, watch_percentage }
Mục đích:
  ✅ Tính interest_vector (EMA) — vector sở thích cá nhân hóa
  ✅ Tăng counter video (view_count, like_count...)
  ✅ Theo dõi "đã tương tác" (cũng là đã xem)
  ❌ KHÔNG dùng để tính fatigue_score
```

### Mối quan hệ tập hợp

```
┌─────────────────────────────────────────────┐
│           Videos user đã XEM                │
│  (behavior_logs — MỌI video lướt qua)       │
│                                             │
│   ┌─────────────────────────────────┐       │
│   │  Videos user đã TƯƠNG TÁC       │       │
│   │  (interactions — like/skip/...) │       │
│   │                                 │       │
│   │  → Dùng cho interest_vector     │       │
│   └─────────────────────────────────┘       │
│                                             │
│   → Dùng cho dedup (seen-set)               │
└─────────────────────────────────────────────┘

behavior_logs ⊇ interactions
(Mọi video tương tác đều đã xem, nhưng không phải mọi video xem đều tương tác)
```

---

## 2. Xác nhận: Redis lưu đúng hay sai?

### Redis hiện tại lưu gì?

```python
# interaction_service.py L302
async def record_behavior_log(self, data):
    await add_seen_video(data.session_id, data.video_id)  # ← Lưu từ behavior_log
```

**Redis `session:{id}:seen` = tập hợp video_id từ behavior_logs**

### ✅ ĐÚNG — Redis ĐÚNG KHI lưu behavior_log video IDs

**Lý do:** Redis seen-set phục vụ cho mục đích **DEDUP** (loại trừ video trùng lặp trong feed), KHÔNG phải cho interest_vector.

Khi dedup, ta cần loại bỏ TẤT CẢ video user đã **NHÌN THẤY**, bao gồm:
- Video user lướt qua nhanh mà không tương tác (chỉ có behavior_log)
- Video user đã like/skip/replay (có interaction)

Nếu Redis chỉ lưu interaction → user lướt qua video A (không like/skip) → GET /feed vẫn có thể trả lại video A → **trùng lặp!**

### Fallback logic cũng confirm điều này

```python
# feed_service.py L116-126 (khi Redis trống/unavailable)
else:
    # From explicit interactions (like, skip, replay, …)
    seen_video_ids = await self._interaction_repo.find_video_ids_in_session(session_id)
    seen_set.update(seen_video_ids)

    # From passive behavior logs  ← LẤY CẢ HAI NGUỒN
    behavior_docs = await self._log_repo.find_many(...)
    seen_set.update(d["video_id"] for d in behavior_docs)
```

Fallback lấy cả `interactions` VÀ `behavior_logs` → merge lại thành seen_set.
Redis chỉ làm tắt bước này bằng cách lưu ngay tại `record_behavior_log`.

---

## 3. Interest vector dựa vào gì?

### ✅ Interest vector dựa vào INTERACTIONS — không phải behavior_logs

```python
# interaction_service.py L142-192: _batch_update_interest_vector()
interactions = await self._repo.find_by_session(session_id)  # ← interactions collection
#                      ^^^^^^^^
#                      InteractionRepository.find_by_session()
#                      Lấy từ collection "interactions", KHÔNG PHẢI "behavior_logs"

for interaction in interactions:
    weight = get_interaction_weight(interaction["type"])  # like=1.0, skip=-0.3, ...
    # ...
    list_of_video_vecs.append(video_vec)
    list_of_weights.append(weight)

new_vec = calculate_batch_ema_vector(current_vec, list_of_video_vecs, list_of_weights)
```

**Luồng hoàn chỉnh:**

```
1. User LIKE video X
   → POST /interactions { type: "like", video_id: X }
   → InteractionRepository.insert_one()  ← vào collection "interactions"

2. User END SESSION
   → InteractionService.end_session()
   → _batch_update_interest_vector(session_id)
   → InteractionRepository.find_by_session(session_id)  ← đọc "interactions"
   → get_interaction_weight("like") = 1.0
   → calculate_batch_ema_vector() → cập nhật user.interest_vector

3. User START NEW SESSION
   → GET /feed → user.interest_vector đã được cập nhật từ session cũ
   → $vectorSearch với vector mới → gợi ý phù hợp hơn
```

### Interest vector KHÔNG BAO GIỜ đọc behavior_logs

Không có dòng code nào trong `_batch_update_interest_vector()` truy vấn `behavior_logs`.
Behavior logs chỉ phục vụ: fatigue calculation + dedup.

---

## 4. Vấn đề mà bạn phát hiện

Bạn đang lo ngại rằng:

> "Redis lưu behavior_log → nhưng interest_vector dựa vào interaction →
> vậy Redis nên lưu interaction chứ?"

### Trả lời: **Không cần thay đổi**, vì chúng phục vụ 2 mục đích khác nhau

| Thành phần | Nguồn dữ liệu | Mục đích |
|---|---|---|
| **Redis seen-set** | behavior_logs (mọi video đã xem) | **DEDUP** — loại video trùng khỏi feed |
| **Interest vector** | interactions (like/skip/replay) | **CÁ NHÂN HÓA** — hướng feed theo sở thích |

Chúng **KHÔNG liên quan** với nhau:
- Redis seen-set quyết định video nào **KHÔNG ĐƯỢC hiển thị** (đã xem rồi)
- Interest vector quyết định video nào **NÊN ĐƯỢC ƯU TIÊN** (phù hợp sở thích)

### Tuy nhiên — có 1 cải thiện nhỏ nên làm

Hiện tại `record_interaction()` **KHÔNG** ghi vào Redis seen-set:

```python
# interaction_service.py L68-136: record_interaction()
# ❌ THIẾU: await add_seen_video(data.session_id, data.video_id)
```

Vấn đề nhỏ: Nếu user chỉ LIKE video mà không có behavior_log (edge case khi FE gửi
interaction trước behavior_log), video đó sẽ không nằm trong Redis seen-set.

**Fix nhỏ:** Thêm `add_seen_video()` vào `record_interaction()` để đảm bảo consistency.

---

## 5. Kết luận & Đề xuất

### Kết luận

| Câu hỏi | Trả lời |
|---|---|
| Redis nên lưu behavior_log hay interaction? | ✅ **Behavior_log** (đúng như hiện tại) — vì mục đích là DEDUP |
| Interest vector dựa vào behavior_log hay interaction? | ✅ **Interaction** (đúng như hiện tại) — EMA chỉ xử lý like/skip/replay |
| Có bug không? | ❌ **Không có bug** — hai hệ thống phục vụ mục đích khác nhau |

### Đề xuất cải thiện (Optional — ưu tiên thấp)

#### Fix 1: Thêm `add_seen_video` vào `record_interaction()` (2 dòng code)

```python
# interaction_service.py → record_interaction()
# Thêm sau validate + trước gather:

await add_seen_video(data.session_id, data.video_id)
```

**Lý do:** Đảm bảo mọi video user tương tác đều nằm trong seen-set, kể cả khi
behavior_log chưa kịp gửi. Tính consistency tốt hơn.

#### Fix 2: Rename Redis key cho rõ nghĩa (tùy chọn)

Hiện tại key là `session:{id}:seen` — đã rõ nghĩa. Không cần đổi.

---

## Tóm tắt bằng sơ đồ

```
User lướt video
     │
     ├─── POST /behavior-logs (MỌI video)
     │       ├─── Redis SADD session:{id}:seen ← DEDUP cho GET /feed
     │       └─── MongoDB behavior_logs       ← Tính fatigue_score
     │
     └─── POST /interactions (chỉ khi like/skip/replay...)
             ├─── MongoDB interactions         ← Tính interest_vector (EMA)
             ├─── Increment video counters     ← trending_score
             └─── (NÊN THÊM) Redis SADD       ← Đảm bảo dedup consistency
```
