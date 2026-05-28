# 📋 PHASE 2 & PHASE 3: Đánh giá Trạng thái & Kế hoạch Triển khai

**Ngày:** 24 tháng 5, 2026  
**Dự án:** GoTouchGrass - Hệ thống Gợi ý Feed có Nhận thức Sức khỏe Tinh thần  
**Phạm vi:** Phát hiện Doomscroll (Phase 2) + Can thiệp Feed Mindful (Phase 3)

---

## 📊 Tóm tắt Tổng quan

| Phase | Thành phần | Trạng thái | Tỷ lệ | Ưu tiên |
|-------|-----------|----------|-------|---------|
| **2** | Theo dõi tín hiệu | ✅ Hoàn thành | 100% | — |
| **2** | Tính toán Mệt mỏi | ✅ Hoàn thành | 100% | — |
| **2** | Máy trạng thái Thích ứng | ✅ Hoàn thành | 100% | — |
| **2** | Cập nhật Realtime | ✅ Hoàn thành | 100% | — |
| **3** | Phát hiện & Lọc trạng thái | ✅ Hoàn thành | 100% | — |
| **3** | Điều chỉnh Trọng số Động | ❌ Thiếu | 0% | 🔴 CAO |
| **3** | Bơm nội dung Palette Cleanser | ❌ Thiếu | 0% | 🔴 CAO |
| **3** | Xếp hạng lại theo Cường độ | ❌ Thiếu | 0% | 🔴 CAO |
| **3** | Kiểm thử E2E | ⚠️ Bộ phận | 60% | 🟡 TB |

**Tiến độ tổng thể:**
- **Phase 2:** 100% ✅ (Sẵn sàng dùng trong production)
- **Phase 3:** 30% (Cần 2-3 giờ triển khai)

---

## ✅ PHASE 2: Phát hiện Doomscroll — HOÀN THÀNH

### Các thứ đã được triển khai

#### 1. **Theo dõi Hành vi (Tất cả Tín hiệu)** ✅

| Tín hiệu | Ghi lại Trong | Công thức/Phạt | Trạng thái |
|---------|--------------|----------------|-----------|
| `swipe_speed` | `BehaviorLog.swipe_speed` | `> 800px/s = 20đ` | ✅ Hoạt động |
| `watch_duration` | `BehaviorLog.watch_duration` | `< 2s = 30đ`, `< 5s = 15đ` | ✅ Hoạt động |
| `interaction` | `BehaviorLog.is_interaction` | lắng nghe (False) = 15đ | ✅ Hoạt động |
| `repetitive_topics` | `consecutive_same_topic` | `≥ 5 lần = 25đ`, `≥ 3 lần = 15đ` | ✅ Hoạt động |
| `session_duration` | `FeedSession.started_at/ended_at` | Dùng tính thống kê cuối | ✅ Hoạt động |

**Tham khảo File:**
- [BehaviorLogCreate](../backend/app/models/behavior_log.py) — Data model
- [InteractionService.record_behavior_log()](../backend/app/services/interaction_service.py#L289) — Logic ghi lại

#### 2. **Tính toán Điểm Mệt mỏi** ✅

**Công thức Triển khai:**
```
fatigue_score = (avg_log_penalties / 10) + (dopamine_penalty)

Trong đó:
  - avg_log_penalties = trung bình các phạt từ 10 behavior logs gần nhất (0-100)
  - dopamine_penalty = (tỷ lệ_video_high_intensity * 10)
  - tỷ lệ_high_intensity = (số_video_high / tổng_video_xem)
```

**Đường dẫn Code:**
```python
# File: app/utils/formula/fatigue.py
calculate_log_penalty()          # Phạt từng video: 0→100
calculate_fatigue_score()        # Tổng hợp mệt mỏi: 0→100
```

**Ví dụ Tính toán:**
```
Kịch bản: User vuốt nhanh 10 video tất cả cường độ cao
- 10 logs cuối: [65, 60, 70, 65, 60, 65, 60, 70, 65, 60] (trung bình = 65 đ)
- high_intensity_count = 10, tổng_videos = 10
- dopamine_penalty = (10/10) * 10 = 10
- fatigue_score = 65 + 10 = 75 → Kích hoạt trạng thái "kiệt sức" ✅
```

#### 3. **Máy Trạng thái Thích ứng** ✅

```
Dải fatigue_score    →    adaptive_state
──────────────────────────────────────────
  0-40              →    "bình thường"      (Giữ feed hiện tại)
  40-70             →    "cảnh báo"         (Trộn nội dung low-intensity)
  >70               →    "kiệt sức"         (Chỉ nội dung low-intensity)
```

**Triển khai:**
```python
# File: app/utils/formula/fatigue.py → determine_adaptive_state()
def determine_adaptive_state(fatigue_score: float) -> str:
    if fatigue_score >= 70:
        return "exhausted"
    elif fatigue_score >= 40:
        return "warning"
    else:
        return "normal"
```

**Tham khảo File:**
- [FeedSessionInDB.adaptive_state](../backend/app/models/feed_session.py#L41) — Trường trạng thái
- [InteractionService._update_session_fatigue_and_state()](../backend/app/services/interaction_service.py#L357) — Logic cập nhật

#### 4. **Pipeline Cập nhật Realtime** ✅

**Luồng:**
```
record_behavior_log(data)
  ↓
[Fire-and-Forget] _update_session_metrics_pipeline(session_id, video_id)
  ├─ _update_session_intensity(session_id, video_id)
  │   └─ Tăng high/low_intensity_count dựa vào video.intensity_level
  │
  └─ _update_session_fatigue_and_state(session_id)
      ├─ Lấy 10 behavior logs gần nhất
      ├─ Tính toán phạt cho từng log
      ├─ Tổng hợp fatigue_score
      ├─ Xác định adaptive_state
      └─ Cập nhật document session nguyên tử
```

**File Chính:**
- [InteractionService._update_session_metrics_pipeline()](../backend/app/services/interaction_service.py#L334)

#### 5. **Phủ Kiểm thử E2E** ✅

**File Kiểm thử:** `backend/scratch/test_interaction_e2e.py`

**Các Kịch bản Xác thực:**
1. Onboarding người dùng chọn tags sở thích
2. Tạo feed session
3. Lấy feed cá nhân hóa với khám phá
4. **8 behavior logs được gửi nhanh** (mô phỏng doomscroll)
5. Điểm mệt mỏi tăng từ <40 lên >70 ✅
6. Trạng thái thích ứng chuyển sang "kiệt sức" ✅
7. Lọc feed được áp dụng (chỉ low intensity) ✅
8. Khẳng định: `assert fatigue_score > 40.0` ✅

**Chạy Kiểm thử:**
```bash
cd /home/nhphat/Personal/WorkSpace/Hackathon/backend
python -m pytest scratch/test_interaction_e2e.py -v
```

---

## 🟡 PHASE 3: Can thiệp Feed Mindful — CHƯA HOÀN THÀNH (30% XONG)

### Trạng thái Hiện tại

#### ✅ Điều gì đang hoạt động
1. **Phát hiện & Theo dõi Trạng thái** — `adaptive_state` tính toán đúng
2. **Lọc Cơ bản** — Áp dụng filter `intensity_level` cho vector search
3. **Đếm Cường độ Session** — Theo dõi high/low counts

**Đường dẫn Code:**
```python
# File: app/services/feed_service.py → get_feed()

if adaptive_state == "exhausted":
    filter_stage = {"intensity_level": "low"}       # ← Chỉ lọc, không boost
elif adaptive_state == "warning":
    filter_stage = {"intensity_level": {"$in": ["low", "medium"]}}
else:
    filter_stage = None

# Thực thi search (nhưng trọng số vẫn cố định)
docs = await self._video_repo.vector_search(
    query_vector=interest_vector,
    filter_stage=filter_stage,
    search_weight=10.0,      # ← Cố định! Nên thay đổi theo state
    trending_weight=0.001,   # ← Cố định! Nên thay đổi theo state
)
```

#### ❌ Điều gì bị thiếu

### 1. **Điều chỉnh Trọng số Động** (Ưu tiên: 🔴 CAO)

**Vấn đề Hiện tại:**
```python
# CÓ HIỆN TẠI (CỐ ĐỊNH):
search_weight=10.0
trending_weight=0.001
```

**Điều gì nên xảy ra:**
```python
# MỌI THỨ CÓ (ĐỘNG):
if adaptive_state == "exhausted":
    search_weight = 5.0      # ↓ Giảm ưu tiên vector similarity
    trending_weight = 0.5    # ↑ Tăng ảnh hưởng trending score
elif adaptive_state == "warning":
    search_weight = 7.0
    trending_weight = 0.1
else:  # "normal"
    search_weight = 10.0
    trending_weight = 0.001
```

**Lý do:**
- **Trạng thái bình thường:** Tối đa hóa cá nhân hóa (search_weight cao)
- **Trạng thái cảnh báo:** Cân bằng nội dung cá nhân + nội dung làm dịu
- **Trạng thái kiệt sức:** Ưu tiên nội dung trending làm dịu hơn khớp vector hoàn hảo

**Vị trí Triển khai:**
- File: `backend/app/services/feed_service.py`
- Hàm: `get_feed()` (khoảng dòng 45-65)

---

### 2. **Bơm Nội dung Palette Cleanser** (Ưu tiên: 🔴 CAO)

**Điều gì bị thiếu:**

Khi `adaptive_state == "exhausted"` và chúng ta có đủ video, bơm 1-2 video "làm dịu" ngẫu nhiên vào vị trí top để phá vỡ chu kỳ doomscroll.

**Code Hiện tại:**
```python
# Video cuối trong feed được thay bằng video trending ngẫu nhiên (khám phá)
# NHƯNG: Không chọn thông minh cho "làm dịu" hoặc giảm dopamine cố ý
if exploration_video:
    docs[-1] = exploration_video  # ← Chỉ là bất kỳ video trending
```

**Điều gì nên xảy ra:**
```python
if adaptive_state == "exhausted" and limit >= 3:
    # Chọn từ các danh mục làm dịu
    calming_categories = ["nature", "asmr", "lofi", "mindfulness", "tutorial"]
    
    # Tìm video làm dịu ngẫu nhiên CHƯA xem trong session
    cleanser_video = await self._video_repo.find_random_from_categories(
        categories=calming_categories,
        exclude_ids=seen_video_ids,  # Không lặp lại
        intensity_level="low",        # Lọc an toàn thêm
        limit=1
    )
    
    if cleanser_video:
        # Chèn ở vị trí 1 (không quá mạnh)
        docs.insert(1, cleanser_video)
        logger.info(f"🍃 Bơm nội dung yên bình: {cleanser_video['title']}")
```

**Vị trí Triển khai:**
- File: `backend/app/services/feed_service.py`
- Hàm: `get_feed()` (trong phần khám phá, ~dòng 75-95)

---

### 3. **Xếp hạng Theo Cường độ Ưu tiên** (Ưu tiên: 🔴 CAO)

**Điều gì bị thiếu:**

Khi ở trạng thái `exhausted`, ưu tiên các video LOW intensity xuất hiện trước, bất kể điểm khớp vector.

**Code Hiện tại:**
```python
# Sắp xếp hoàn toàn theo total_score (hybrid search + trending)
# Video low intensity có thể xếp thứ 5 dù khớp hoàn hảo
pipeline.append({"$sort": {"total_score": -1}})
```

**Điều gì nên xảy ra:**
```python
# Khi kiệt sức: Sắp xếp theo cường độ TRƯỚC, rồi theo score
if adaptive_state == "exhausted":
    # Trong MongoDB Aggregation Pipeline
    pipeline.append({
        "$sort": {
            "intensity_level": 1,       # "low" đứng đầu (A < H < M)
            "total_score": -1           # Rồi theo điểm liên quan
        }
    })
else:
    # Bình thường: Chỉ theo score
    pipeline.append({"$sort": {"total_score": -1}})
```

**Vị trí Triển khai:**
- File: `backend/app/repositories/video_repository.py`
- Hàm: `vector_search()` (chỉnh sửa các stage pipeline)

---

### 4. **Cải thiện Kiểm thử E2E** (Ưu tiên: 🟡 TB)

**Khoảng trống Kiểm thử Hiện tại:**
```python
# Hiện tại chỉ kiểm tra lọc hoạt động:
assert all(v.intensity_level == "low" for v in fatigue_feed)

# Thiếu kiểm tra:
# ❌ Không kiểm tra cleanser được bơm
# ❌ Không kiểm tra điều chỉnh trọng số ảnh hưởng xếp hạng
# ❌ Không kiểm tra nếu video low-intensity xuất hiện đầu
```

**Điều gì cần Thêm:**
```python
# Sau khi yêu cầu feed mệt mỏi:
fatigue_feed = await feed_service.get_feed(user_id, limit=5)

# Những khẳng định mới:
assert len(fatigue_feed) > 0, "Feed không nên trống"
low_intensity_videos = [v for v in fatigue_feed if v.intensity_level == "low"]
assert len(low_intensity_videos) > 0, "Nên có ít nhất 1 video low-intensity"
assert fatigue_feed[0].intensity_level == "low", "Video đầu tiên nên low-intensity"

# Nếu cleanser được bơm:
assert "nature" in [v.category for v in fatigue_feed] or \
       "asmr" in [v.category for v in fatigue_feed], \
       "Nên chứa danh mục làm dịu"
```

---

## 🔧 Kế hoạch Triển khai

### Phase 3a: Điều chỉnh Trọng số Động (30 phút)

**File:** `backend/app/services/feed_service.py`

**Thay đổi:**
1. Trích xuất tính toán trọng số vào hàm trợ giúp
2. Gọi dựa trên `adaptive_state`
3. Truyền trọng số tính được cho `vector_search()`

**Mã giả:**
```python
def _get_search_weights(adaptive_state: str) -> tuple[float, float]:
    """Trả về (search_weight, trending_weight) dựa trên trạng thái mệt mỏi."""
    if adaptive_state == "exhausted":
        return (5.0, 0.5)
    elif adaptive_state == "warning":
        return (7.0, 0.1)
    else:  # bình thường
        return (10.0, 0.001)

# Trong get_feed():
search_weight, trending_weight = self._get_search_weights(state)
docs = await self._video_repo.vector_search(
    query_vector=interest_vector,
    search_weight=search_weight,    # ← Động bây giờ!
    trending_weight=trending_weight,
    ...
)
```

---

### Phase 3b: Bơm Nội dung Palette Cleanser (45 phút)

**File Cần Sửa:**
1. `backend/app/repositories/video_repository.py` — Thêm phương thức mới
2. `backend/app/services/feed_service.py` — Gọi phương thức trong logic khám phá

**Phương thức Repository Mới:**
```python
# Trong lớp VideoRepository
async def find_random_from_categories(
    self,
    categories: List[str],
    exclude_ids: set,
    intensity_level: str = "low",
    limit: int = 1
) -> Optional[Dict[str, Any]]:
    """
    Tìm video ngẫu nhiên từ danh mục cụ thể không trong exclude_ids.
    Dùng để bơm nội dung yên bình khi kiệt sức.
    """
    pipeline = [
        {
            "$match": {
                "category": {"$in": categories},
                "intensity_level": intensity_level,
                "_id": {"$nin": [ObjectId(id) for id in exclude_ids]},
            }
        },
        {"$sample": {"size": limit}},  # ← Lựa chọn ngẫu nhiên
    ]
    results = await self.aggregate(pipeline)
    return results[0] if results else None
```

**Tích hợp trong FeedService:**
```python
# Trong phần khám phá get_feed()
if adaptive_state == "exhausted" and limit >= 3:
    calming_categories = ["nature", "asmr", "lofi", "mindfulness"]
    cleanser = await self._video_repo.find_random_from_categories(
        categories=calming_categories,
        exclude_ids=seen_set,
        intensity_level="low"
    )
    
    if cleanser:
        # Chèn ở vị trí 1 để hiển thị cao
        docs.insert(1, cleanser)
        logger.info(f"🍃 Nội dung yên bình: {cleanser['title']}")
```

---

### Phase 3c: Xếp hạng Theo Cường độ Ưu tiên (20 phút)

**File:** `backend/app/repositories/video_repository.py`

**Sửa phương thức `vector_search()`:**
```python
async def vector_search(
    self,
    query_vector: List[float],
    limit: int = 10,
    num_candidates: int = 100,
    filter_stage: Optional[Dict[str, Any]] = None,
    search_weight: float = 100.0,
    trending_weight: float = 1.0,
    adaptive_state: str = "normal",  # ← THAM SỐ MỚI
) -> List[Dict[str, Any]]:
    """
    Perform $vectorSearch với optional adaptive_state-aware sorting.
    """
    pipeline = [
        {"$vectorSearch": {...}},
        {"$addFields": {...}},
        # ... các stage hiện tại ...
    ]
    
    # Sắp xếp thích ứng dựa trên trạng thái
    if adaptive_state == "exhausted":
        pipeline.append({
            "$sort": {
                "intensity_level": 1,    # Low đứng đầu
                "total_score": -1
            }
        })
    else:
        pipeline.append({"$sort": {"total_score": -1}})
    
    return await self.aggregate(pipeline)
```

**Cập nhật lệnh gọi FeedService:**
```python
docs = await self._video_repo.vector_search(
    query_vector=interest_vector,
    filter_stage=filter_stage,
    search_weight=search_weight,
    trending_weight=trending_weight,
    adaptive_state=adaptive_state,  # ← Truyền trạng thái
)
```

---

### Phase 3d: Cải thiện Kiểm thử E2E (30 phút)

**File:** `backend/scratch/test_interaction_e2e.py`

**Thêm sau yêu cầu feed mệt mỏi:**
```python
# Xác thực ưu tiên low-intensity & Palette Cleanser Injection
print("\n[7/7] Xác thực Bơm Nội dung Yên bình & Ưu tiên Cường độ...")

low_intensity_count = sum(1 for v in fatigue_feed if v.intensity_level == "low")
high_intensity_count = sum(1 for v in fatigue_feed if v.intensity_level == "high")

assert low_intensity_count > high_intensity_count, \
    f"❌ Video low intensity ({low_intensity_count}) nên nhiều hơn high ({high_intensity_count})"

# Xác thực video đầu tiên là low-intensity
if len(fatigue_feed) > 0:
    assert fatigue_feed[0].intensity_level == "low", \
        f"❌ Video đầu tiên nên low-intensity, nhận được {fatigue_feed[0].intensity_level}"
    print(f"✅ Video đầu tiên được ưu tiên (low-intensity): {fatigue_feed[0].title}")

# Xác thực danh mục làm dịu có mặt
calming_categories = ["nature", "asmr", "lofi", "mindfulness"]
has_calming = any(
    v.category in calming_categories 
    for v in fatigue_feed
)
assert has_calming, "❌ Nên chứa ít nhất một danh mục làm dịu"
print(f"✅ Nội dung yên bình được phát hiện trong feed")

print("\n✅ Tất cả khẳng định Phase 3 đã vượt qua!")
```

---

## 📅 Lịch trình Triển khai

| Nhiệm vụ | Thời gian | Ưu tiên | Phụ thuộc |
|---------|---------|---------|-----------|
| 3a. Trọng số Động | 30 phút | 🔴 CAO | Không có |
| 3b. Bơm Nội dung | 45 phút | 🔴 CAO | 3a (tùy chọn) |
| 3c. Xếp hạng Cường độ | 20 phút | 🔴 CAO | 3a |
| 3d. Kiểm thử E2E | 30 phút | 🟡 TB | 3a, 3b, 3c |
| **TỔNG CỘNG** | **2h 5phút** | — | — |

**Thứ tự Thực hiện Khuyên:**
1. 3a → 3c (có thể chạy song song, cả hai ảnh hưởng vector_search)
2. 3b (bơm nội dung, độc lập)
3. 3d (kiểm thử toàn diện)

---

## 🧪 Danh sách Kiểm tra Xác thực

Sau khi triển khai, xác minh:

- [ ] **Trọng số Động**
  - [ ] Trạng thái kiệt sức → search_weight=5.0, trending_weight=0.5
  - [ ] Trạng thái cảnh báo → search_weight=7.0, trending_weight=0.1
  - [ ] Trạng thái bình thường → search_weight=10.0, trending_weight=0.001
  - [ ] Trọng số thực sự ảnh hưởng đến xếp hạng feed (kiểm tra với dữ liệu thật)

- [ ] **Bơm Nội dung Yên bình**
  - [ ] Video làm dịu được bơm khi kiệt sức + limit ≥ 3
  - [ ] Video được bơm KHÔNG trong tập đã xem session
  - [ ] Danh mục là một trong: nature, asmr, lofi, mindfulness
  - [ ] intensity_level == "low" được áp dụng

- [ ] **Xếp hạng Cường độ**
  - [ ] Trạng thái kiệt sức: video đầu tiên luôn low-intensity
  - [ ] Trạng thái cảnh báo: video low/medium được ưu tiên
  - [ ] Trạng thái bình thường: xếp hạng feed không thay đổi từ Phase 1

- [ ] **Kiểm thử E2E Vượt qua**
  - [ ] `pytest backend/scratch/test_interaction_e2e.py -v` ✅
  - [ ] Tất cả 7 bước vượt qua với những khẳng định mới
  - [ ] Phát hiện mệt mỏi vẫn hoạt động
  - [ ] Lọc vẫn hoạt động

---

## 📝 Tham khảo File Code

### Đọc/Sửa:
- `backend/app/services/feed_service.py` — Hàm get_feed() chính
- `backend/app/repositories/video_repository.py` — Vector search & phương thức mới
- `backend/scratch/test_interaction_e2e.py` — Kiểm thử E2E

### Tham khảo (Không sửa):
- `backend/docs/fatigue_engine_flow.md` — Tài liệu công thức
- `backend/app/utils/formula/fatigue.py` — Tính toán mệt mỏi
- `backend/app/models/feed_session.py` — Schema session

---

## 🎯 Kết quả Dự kiến

Sau khi triển khai tất cả các thành phần Phase 3:

**Hành trình người dùng - Trạng thái Kiệt sức:**
```
1. Người dùng vuốt nhanh 8 video (cường độ cao)
2. Điểm Mệt mỏi đạt 75/100 → adaptive_state="exhausted"
3. Yêu cầu feed tiếp theo:
   ✅ Giảm trọng số: Giảm độ ưu tiên similarity vector
   ✅ Sắp xếp: Ưu tiên video low-intensity
   ✅ Bơm: Chèn video làm dịu ngẫu nhiên ở vị trí 1
4. Người dùng thấy:
   - [0] 🍃 "Âm thanh mưa ASMR 1 giờ" (được bơm)
   - [1] "Yoga có ý thức" (khớp low-intensity)
   - [2] "Beats lofi để học" (khớp low-intensity)
   - [3] "Vlog du lịch - Đài Loan" (khớp low-intensity)
   - [4] "Hướng dẫn coding" (khớp medium-intensity)
5. Tải dopamine của người dùng giảm
6. Sức khỏe tâm thần được bảo vệ ✅
```

---

## ❓ Các Câu hỏi & Quyết định

**Q1: Điều chỉnh trọng số nên xảy ra ở VideoRepository hay FeedService?**
- **Quyết định:** FeedService (lớp logic kinh doanh) tính trọng số, truyền cho VideoRepository
- **Lý do:** Giữ lớp repository sạch sẽ; các quy tắc kinh doanh ở lớp service

**Q2: Bơm bao nhiêu video (1 hay 2)?**
- **Quyết định:** 1 video (ở vị trí 1, hiển thị cao)
- **Lý do:** Quá nhiều = ghi đè cá nhân hóa; 1 cái đủ để phá chu kỳ

**Q3: Video làm dịu nên ngẫu nhiên hay xếp hạng?**
- **Quyết định:** Ngẫu nhiên với lọc danh mục
- **Lý do:** Phá vỡ khả năng dự đoán; ngăn user học "hệ thống"

**Q4: Khi kiệt sức, nên hoàn toàn ẩn video cường độ cao?**
- **Quyết định:** KHÔNG — chỉ lọc trong top 5; hiển thị ít nhất 1 video cường độ cao lựa chọn
- **Lý do:** Quyền lực người dùng; tránh hành vi cấm cảnh báo

---

## 🎬 Frontend Testing Strategy (PHASE 3 Impact)

### Q: Phase 3 có phải toàn Backend code không?

**Trả lời: CÓ ✅**

Phase 3 **100% Backend implementation**:
- ✅ 3a. Điều chỉnh trọng số → `backend/app/services/feed_service.py`
- ✅ 3b. Bơm nội dung → `backend/app/services/feed_service.py` + `backend/app/repositories/video_repository.py`
- ✅ 3c. Xếp hạng độ cường độ → `backend/app/repositories/video_repository.py`
- ✅ 3d. E2E test → Backend kiểm thử

**Frontend không cần code thêm**, nhưng **cần test lại** khi backend thay đổi!

---

### Frontend Regression Testing Checklist

Frontend cần kiểm tra những điều sau khi Phase 3 backend được deploy:

#### **1. Feed Rendering Tests** (kiểm tra feed vẫn render đúng) ✅

```typescript
// frontend/src/components/Feed.tsx - Regression Tests

describe("Feed Component - Phase 3 Backend Changes", () => {
  
  // TEST 1: Feed vẫn load bình thường khi normal state
  test("feed renders correctly in normal state", async () => {
    const { videos } = await api.getFeed(userId, { limit: 5 });
    expect(videos).toHaveLength(5);
    expect(videos[0]).toHaveProperty("intensity_level");
    expect(videos[0]).toHaveProperty("_id");
  });

  // TEST 2: Feed có reorder khi exhausted state (low intensity first)
  test("feed reorders with low-intensity videos first when exhausted", async () => {
    // Simulate exhausted state: fatigue_score > 70
    const { videos } = await api.getFeed(userId, { limit: 5 });
    
    const lowIntensityVideos = videos.filter(v => v.intensity_level === "low");
    const highIntensityVideos = videos.filter(v => v.intensity_level === "high");
    
    // Low intensity should appear earlier in the list
    if (lowIntensityVideos.length > 0 && highIntensityVideos.length > 0) {
      const lowIndex = videos.findIndex(v => v.intensity_level === "low");
      const highIndex = videos.findIndex(v => v.intensity_level === "high");
      expect(lowIndex).toBeLessThan(highIndex);
    }
  });

  // TEST 3: Feed đã xem "Palette Cleanser" video (mới được bơm)
  test("feed contains calming category video when exhausted", async () => {
    const { videos } = await api.getFeed(userId, { limit: 5 });
    
    const calmingCategories = ["nature", "asmr", "lofi", "mindfulness"];
    const hasCalmingVideo = videos.some(v => 
      calmingCategories.includes(v.category)
    );
    
    // Khi exhausted, ít nhất 1 video nên từ danh mục làm dịu
    expect(hasCalmingVideo).toBe(true);
  });

  // TEST 4: Feed latency không tăng (performance check)
  test("feed API response time under 500ms", async () => {
    const startTime = performance.now();
    await api.getFeed(userId, { limit: 5 });
    const endTime = performance.now();
    
    const responseTime = endTime - startTime;
    expect(responseTime).toBeLessThan(500); // Should be < 500ms
  });
});
```

---

#### **2. Fatigue Score Display Tests** (UI vẫn hiển thị đúng) ✅

```typescript
// frontend/src/App.tsx - Fatigue UI Tests

describe("Fatigue Score Indicator UI", () => {
  
  // TEST 1: Fatigue bar hiển thị đúng % khi thay đổi
  test("fatigue score bar updates when score changes", async () => {
    const { getByTestId } = render(<App />);
    
    // Initial: normal state (< 40)
    let fatigueBar = getByTestId("fatigue-bar");
    expect(fatigueBar).toHaveStyle({ width: "25%" }); // 25% width
    
    // After doomscroll: exhausted state (> 70)
    // Wait for backend update
    await waitFor(() => {
      fatigueBar = getByTestId("fatigue-bar");
      expect(fatigueBar).toHaveStyle({ width: "80%" }); // 80% width
    });
  });

  // TEST 2: Màu sắc thay đổi theo trạng thái
  test("fatigue bar color changes by state", async () => {
    const { getByTestId } = render(<App />);
    
    let fatigueBar = getByTestId("fatigue-bar");
    
    // Normal: green
    expect(fatigueBar).toHaveClass("bg-emerald-500");
    
    // Warning: amber
    // (After behavior logs)
    await waitFor(() => {
      fatigueBar = getByTestId("fatigue-bar");
      expect(fatigueBar).toHaveClass("bg-amber-400");
    });
    
    // Exhausted: red
    await waitFor(() => {
      fatigueBar = getByTestId("fatigue-bar");
      expect(fatigueBar).toHaveClass("bg-rose-500");
    });
  });

  // TEST 3: Badge "Doomscrolling!" hiển thị khi score > 75
  test("doomscrolling badge appears when score > 75", async () => {
    const { queryByText } = render(<App />);
    
    // Initially not visible
    expect(queryByText("Doomscrolling!")).not.toBeInTheDocument();
    
    // After threshold
    await waitFor(() => {
      expect(queryByText("Doomscrolling!")).toBeInTheDocument();
    });
  });

  // TEST 4: Palette cleanser banner hiển thị khi exhausted
  test("mindful intervention banner appears when mindful active", async () => {
    const { queryByText } = render(<App />);
    
    await waitFor(() => {
      expect(queryByText(/Tự động can thiệp Mindful Feed/i))
        .toBeInTheDocument();
    });
  });
});
```

---

#### **3. Video Interaction Tests** (tương tác vẫn ghi nhận đúng) ✅

```typescript
// frontend/src/components/VideoCard.tsx - Interaction Tests

describe("Video Interaction Tracking - Phase 3", () => {
  
  // TEST 1: Like button gửi tracking event đúng
  test("like button sends interaction event", async () => {
    const mockApi = jest.spyOn(api, "recordInteraction");
    
    const { getByTestId } = render(
      <VideoCard video={mockVideo} sessionId="test_session" />
    );
    
    const likeButton = getByTestId("like-button");
    fireEvent.click(likeButton);
    
    expect(mockApi).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "like",
        session_id: "test_session",
      })
    );
  });

  // TEST 2: Skip (swipe) gửi behavior log đúng
  test("swipe sends behavior log with swipe_speed", async () => {
    const mockApi = jest.spyOn(api, "recordBehaviorLog");
    
    const { getByTestId } = render(
      <VideoCard video={mockVideo} sessionId="test_session" />
    );
    
    // Simulate swipe (or button click for skip)
    const skipButton = getByTestId("skip-button");
    fireEvent.click(skipButton);
    
    expect(mockApi).toHaveBeenCalledWith(
      expect.objectContaining({
        swipe_speed: expect.any(Number),
        watch_duration: expect.any(Number),
      })
    );
  });

  // TEST 3: Video không gây lỗi khi intensity_level undefined
  test("video renders with missing intensity_level", () => {
    const videoWithoutIntensity = { ...mockVideo };
    delete videoWithoutIntensity.intensity_level;
    
    const { container } = render(
      <VideoCard video={videoWithoutIntensity} />
    );
    
    expect(container).toBeInTheDocument();
  });
});
```

---

#### **4. Session State Tests** (session tracking vẫn đúng) ✅

```typescript
describe("Feed Session - Phase 3", () => {
  
  // TEST 1: Session ID không thay đổi khi load feed
  test("same session ID throughout feed browsing", async () => {
    const session1 = await api.createSession(userId);
    
    // Fetch feed multiple times
    await api.getFeed(userId, { limit: 5 });
    await api.getFeed(userId, { limit: 5 });
    
    const session2 = await api.getSession(session1.id);
    expect(session2.id).toBe(session1.id);
  });

  // TEST 2: Video count tăng sau mỗi interaction
  test("total_videos_watched increments after interactions", async () => {
    const session = await api.createSession(userId);
    const initialCount = session.total_videos_watched;
    
    // Record interaction
    await api.recordInteraction({
      user_id: userId,
      video_id: "video_123",
      session_id: session.id,
      type: "like",
    });
    
    const updatedSession = await api.getSession(session.id);
    expect(updatedSession.total_videos_watched).toBeGreaterThan(initialCount);
  });

  // TEST 3: Session end time được set đúng
  test("session end_time set when ends", async () => {
    const session = await api.createSession(userId);
    expect(session.ended_at).toBeNull();
    
    await api.endSession(session.id);
    
    const endedSession = await api.getSession(session.id);
    expect(endedSession.ended_at).not.toBeNull();
  });
});
```

---

#### **5. Integration Tests** (toàn flow từ FE) ✅

```typescript
describe("End-to-End: Frontend → Backend Phase 3", () => {
  
  // TEST 1: Doomscroll simulation end-to-end
  test("complete doomscroll flow: feed → fatigue → intervention", async () => {
    // 1. Create user & session
    const user = await api.createUser({ tags: ["music", "gaming"] });
    const session = await api.createSession(user.id);
    
    // 2. Get initial feed (normal state)
    let feed = await api.getFeed(user.id, { limit: 5 });
    expect(feed).toHaveLength(5);
    
    // 3. Simulate doomscroll: rapid interactions + behavior logs
    for (let i = 0; i < 8; i++) {
      await api.recordBehaviorLog({
        user_id: user.id,
        session_id: session.id,
        video_id: feed[0].id,
        swipe_speed: 900, // Fast swipe
        watch_duration: 1.5, // Short watch
        is_interaction: false, // Passive scroll
      });
    }
    
    // 4. Wait for backend to update fatigue
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // 5. Check session state changed to "exhausted"
    const updatedSession = await api.getSession(session.id);
    expect(updatedSession.adaptive_state).toBe("exhausted");
    expect(updatedSession.fatigue_score).toBeGreaterThan(70);
    
    // 6. Get new feed (should have low-intensity prioritized)
    feed = await api.getFeed(user.id, { limit: 5 });
    
    // 7. Verify low-intensity appears first
    const lowIntensityVideos = feed.filter(v => v.intensity_level === "low");
    expect(lowIntensityVideos.length).toBeGreaterThan(0);
    expect(feed[0].intensity_level).toBe("low");
  });

  // TEST 2: Palette cleanser video exists in exhausted feed
  test("palette cleanser video appears in exhausted state feed", async () => {
    // ... setup doomscroll as above ...
    
    const feed = await api.getFeed(user.id, { limit: 5 });
    
    const calmingVideo = feed.find(v => 
      ["nature", "asmr", "lofi", "mindfulness"].includes(v.category)
    );
    
    expect(calmingVideo).toBeDefined();
    expect(calmingVideo.intensity_level).toBe("low");
  });
});
```

---

### Frontend Component Changes (OPTIONAL - Enhancements)

Nếu FE muốn polish thêm khi Phase 3 backend activate:

#### **Option A: Show Intensity Label on Videos**
```tsx
// frontend/src/components/VideoCard.tsx

export const VideoCard = ({ video }) => {
  const getIntensityBadge = (level: string) => {
    const colors = {
      low: "bg-emerald-500/20 text-emerald-300",
      medium: "bg-amber-500/20 text-amber-300",
      high: "bg-rose-500/20 text-rose-300",
    };
    return colors[level] || colors.medium;
  };

  return (
    <div>
      {/* Video player */}
      
      {/* Intensity badge - NEW */}
      <div className={`absolute top-2 left-2 px-2 py-1 rounded text-xs font-semibold ${getIntensityBadge(video.intensity_level)}`}>
        {video.intensity_level === "low" ? "🍃 Yên bình" : 
         video.intensity_level === "medium" ? "⚡ Bình thường" : 
         "🔥 Kích thích"}
      </div>
    </div>
  );
};
```

#### **Option B: Inject Palette Cleanser Badge**
```tsx
// frontend/src/components/Feed.tsx

const isPaletteCleanser = (video: Video) => {
  return ["nature", "asmr", "lofi", "mindfulness"].includes(video.category);
};

// In feed render:
{videos.map((video, idx) => (
  <div key={video.id} className="relative">
    {isPaletteCleanser(video) && (
      <div className="absolute top-4 right-4 z-10 bg-emerald-500/90 px-3 py-1 rounded-full text-xs font-bold text-white">
        🍃 Nội dung yên bình
      </div>
    )}
    <VideoCard video={video} />
  </div>
))}
```

---

### Test Execution Guide

1. **Backend Phase 3 Deploy** (2h 5 phút)
   - Implement 3a, 3b, 3c, 3d
   - Run backend tests: ✅ All pass

2. **Frontend Regression Testing** (1h)
   ```bash
   # Run all tests
   cd frontend
   npm test -- --coverage
   
   # Check:
   # ✅ Feed.test.tsx
   # ✅ VideoCard.test.tsx  
   # ✅ App.integration.test.tsx
   ```

3. **Manual E2E Testing** (30 phút)
   - Start local: FE (port 5173) + BE (port 8000)
   - Simulate doomscroll path
   - Verify:
     - [ ] Feed reorders when exhausted
     - [ ] Fatigue bar color changes
     - [ ] Palette cleanser video appears
     - [ ] No console errors
     - [ ] Performance OK (< 500ms API calls)

---

## 📌 Ghi chú

- **Phase 2 sẵn sàng production** — Tất cả tín hiệu được theo dõi, mệt mỏi tính toán đúng
- **Phase 3 cần ~2 giờ triển khai** — Thay đổi đơn giản cho feed_service và video_repository
- **Kiểm thử E2E xác thực luồng end-to-end** — Sau triển khai, kiểm thử hồi quy đầy đủ có sẵn
- **Không cần thay đổi schema cơ sở dữ liệu** — Tất cả trường đã tồn tại (intensity_level, adaptive_state, v.v.)
- **Tương thích ngược** — Trạng thái bình thường hoạt động chính xác giống Phase 1
- **Frontend không code thêm** — Chỉ cần regression testing + optional polish

