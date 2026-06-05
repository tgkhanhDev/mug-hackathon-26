# 📐 Công thức Trending Score — Time-Decay & Velocity

**📄 File nguồn:** `app/utils/formula/trending.py`  
**Được dùng bởi:** `interaction_service.py`, `video_repository.py`

---

## Mục đích

**Trending Score** quyết định video nào "đang hot" tại một thời điểm nhất định. Thay vì chỉ dùng tổng view/like, hệ thống áp dụng **phân rã theo thời gian (time decay)** để đảm bảo nội dung mới có cơ hội được khám phá, không bị chôn vùi bởi video cũ nhưng tích lũy view lâu.

---

## Hằng số cấu hình

### `TRENDING_WEIGHTS`

```python
TRENDING_WEIGHTS = {
    "view":    1,   # 1 view = 1 điểm
    "like":    3,   # 1 like = 3 điểm
    "comment": 5,   # 1 comment = 5 điểm
}
```

**Lý do hệ số:**
- **View** dễ "giả tạo" — người ta có thể vô tình mở video rồi thoát ngay
- **Like** có chủ đích hơn — người dùng phải chủ động bấm
- **Comment** tốn công nhất — cho thấy người dùng thực sự bị đánh động

### `HALF_LIFE_HOURS` — Thời gian giảm nửa

```python
HALF_LIFE_HOURS = {
    "entertainment": 168.0,   # 7 ngày
    "sports":        120.0,   # 5 ngày
    "gaming":        168.0,   # 7 ngày
    "lifestyle":     336.0,   # 14 ngày
    "education":     720.0,   # 30 ngày
    "calming":       720.0,   # 30 ngày
    "nature":        720.0,   # 30 ngày
    "cooking":       336.0,   # 14 ngày
    "_default":      168.0,   # 7 ngày (fallback)
}
```

**Ý nghĩa "thời gian giảm nửa":** Sau đúng `half_life` giờ, điểm trending của video sẽ giảm còn **50%** so với ban đầu.

### `MIN_VELOCITY_VIEWS_PER_DAY = 10`

Video cần ít nhất 10 lượt xem mỗi ngày để được coi là "đang trending".

---

## Hàm 1: `calculate_raw_trending_score()` — Điểm Trending Thô

```python
def calculate_raw_trending_score(
    view_count: int,
    like_count: int,
    comment_count: int,
) -> float:
```

### Công thức:

```
raw_score = view_count × 1  +  like_count × 3  +  comment_count × 5
```

### Ví dụ:

```
Video A: 10,000 view, 500 like, 50 comment
raw_score = 10000×1 + 500×3 + 50×5 = 10,000 + 1,500 + 250 = 11,750

Video B: 1,000 view, 200 like, 100 comment
raw_score = 1000×1 + 200×3 + 100×5 = 1,000 + 600 + 500 = 2,100
```

Video A thắng về raw score nhờ lượng view lớn.

---

## Hàm 2: `calculate_time_decay_metrics()` — Điểm Trending Có Phân Rã

```python
def calculate_time_decay_metrics(
    now: datetime,
    created_at: datetime,
    category: str,
    raw_score: float,
    view_count: int,
    snapshot_at: Optional[datetime] = None,
    snapshot_views: Optional[int] = None,
    window_days: int = 7,
) -> Dict[str, Any]:
```

### Công thức phân rã:

```
age_hours = (now - created_at) tính bằng giờ

λ (hằng số phân rã) = ln(2) / half_life_hours

decay_factor = e^(-λ × age_hours)

effective_score = raw_score × decay_factor
```

### Tính velocity (tốc độ lan truyền):

```
# Nếu có snapshot (điểm tham chiếu N ngày trước):
velocity_7d = (view_count - snapshot_views) / elapsed_days

# Nếu không có snapshot:
velocity_7d = view_count / (age_hours / 24)
```

### Điều kiện trending:

```
is_trending = (velocity_7d >= 10)  AND  (age_hours <= 28 ngày)
```

### Ví dụ với time decay (tiếp theo ví dụ trên):

```
Giả sử Video A được tạo 14 ngày trước, category="entertainment"
half_life = 168 giờ = 7 ngày
age_hours = 14 × 24 = 336 giờ

λ = ln(2) / 168 ≈ 0.00413
decay_factor = e^(-0.00413 × 336) ≈ e^(-1.387) ≈ 0.25

effective_score_A = 11,750 × 0.25 = 2,937.5

---

Giả sử Video B mới được đăng 3 ngày trước, category="entertainment"
age_hours = 3 × 24 = 72 giờ

decay_factor = e^(-0.00413 × 72) ≈ e^(-0.297) ≈ 0.743

effective_score_B = 2,100 × 0.743 = 1,560.3
```

Bây giờ Video A (2,937.5) vẫn thắng, nhưng Video B (1,560.3) đã rút ngắn đáng kể khoảng cách. Nếu Video B tiếp tục viral, nó có thể vượt Video A trong vài ngày tới.

### Bảng decay_factor theo tuổi video:

| Tuổi video | Entertainment (HL=7 ngày) | Education (HL=30 ngày) |
|:---:|:---:|:---:|
| 1 ngày | 0.906 (giảm ~10%) | 0.977 (giảm ~2%) |
| 7 ngày | 0.500 (giảm 50%) | 0.860 (giảm 14%) |
| 14 ngày | 0.250 (giảm 75%) | 0.740 (giảm 26%) |
| 30 ngày | 0.063 (giảm 94%) | 0.500 (giảm 50%) |

---

## Hàm 3: `build_trending_score_pipeline_stage()` — MongoDB Pipeline

Trả về một `$addFields` stage để tính `trending_score` **trực tiếp trong MongoDB aggregation pipeline**, không cần lấy data về Python:

```json
{
  "$addFields": {
    "trending_score": {
      "$add": [
        { "$multiply": [{ "$ifNull": ["$view_count", 0] }, 1] },
        { "$multiply": [{ "$ifNull": ["$like_count", 0] }, 3] },
        { "$multiply": [{ "$ifNull": ["$comment_count", 0] }, 5] }
      ]
    }
  }
}
```

**Lợi ích:** Tính toán xảy ra trong database, giảm lượng data truyền qua mạng.

---

## Hàm 4: `build_trending_score_update_pipeline()` — Atomic Counter Update

Khi có tương tác mới (view/like/comment), hệ thống cần:
1. Tăng counter (`view_count += 1`)
2. Đồng thời tính lại `trending_score`

Hàm này trả về MongoDB aggregation update pipeline để làm cả 2 việc **trong 1 lần write duy nhất** (atomic):

```python
build_trending_score_update_pipeline({"view_count": 1, "like_count": 1})
```

Kết quả:
```json
[
  {
    "$set": {
      "updated_at": "$$NOW",
      "view_count": { "$add": [{ "$ifNull": ["$view_count", 0] }, 1] },
      "like_count":  { "$add": [{ "$ifNull": ["$like_count", 0] }, 1] }
    }
  },
  {
    "$set": {
      "trending_score": {
        "$add": [
          { "$multiply": ["$view_count", 1] },
          { "$multiply": ["$like_count", 3] },
          { "$multiply": ["$comment_count", 5] }
        ]
      }
    }
  }
]
```

**Lợi ích:** Đảm bảo `trending_score` luôn nhất quán với counter — không có race condition.

---

## Cách trending score được dùng trong feed

```
Khi get_trending_videos() được gọi:
  1. Lấy top N×3 video theo trending_score (raw) từ MongoDB
  2. Với mỗi video → gọi calculate_time_decay_metrics()
  3. Sort lại theo effective_score (đã phân rã theo thời gian)
  4. Trả về top N video
```

Trong **personalized feed**, trending score được dùng như một trọng số phụ (`trending_weight`) để blend với vector similarity search — cho phép hệ thống ưu tiên video vừa phù hợp gu, vừa đang hot.

---

## Vị trí trong hệ thống

```
User like/view video
        │
        ▼
increment_video_counters()
        │
        └─ build_trending_score_update_pipeline()
               → Atomic update: counter + trending_score (1 write)

GET /feed
        │
        ├─ vector_search() → dùng trending_score làm trọng số phụ
        └─ find_trending() → sort theo trending_score đã tính
        
GET /trending
        │
        └─ get_trending_videos()
               → Calculate time-decay effective_score
               → Re-sort và trả về top N
```
