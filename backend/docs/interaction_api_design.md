# 🏗️ Interaction & Trending API — Design Document

> **Status**: Pending Review  
> **Owner**: Bạn 2 (Backend)  
> **Day**: DAY 2 — Interaction & Vector Search Logic

---

## 📐 Tổng quan kiến trúc

```
Frontend                Backend                    MongoDB
   │                       │
   │──POST /interactions──►│ InteractionController
   │                       │  └─ InteractionService
   │                       │       ├─ save interaction doc
   │                       │       ├─ increment video counters (atomic)
   │                       │       ├─ update user interest_vector  (async)
   │                       │       └─ broadcast via WebSocket
   │◄─ WS push (counts) ───│ WebSocketManager
   │                       │
   │──WS /ws/stats/{vid}──►│ WebSocket endpoint
   │◄─ {like,view,comment}─│ broadcast to all subscribers of that video_id
```

---

## 1️⃣ REST Endpoints

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/interactions` | Ghi nhận 1 event (like/skip/watch/comment/replay) |
| `POST` | `/api/v1/sessions` | Tạo session mới khi user mở app |
| `PUT` | `/api/v1/sessions/{id}/end` | Đóng session |
| `POST` | `/api/v1/behavior-logs` | Ghi raw behavior log (mỗi video xem qua) |
| `GET` | `/api/v1/users/{id}/vector-status` | Kiểm tra interest_vector hiện tại |
| `GET` | `/api/v1/videos/trending` | Trending với time-decay (mở rộng từ cái cũ) |
| `WS` | `/ws/stats/{video_id}` | Real-time like/view/comment counts |

---

## 2️⃣ WebSocket — Real-time Stats

### Lý do dùng WebSocket (không phải polling)
- Like/view/comment có thể đến từ nhiều user cùng lúc → push 1 lần thay vì N clients poll mỗi 1s
- Frontend chỉ cần subscribe 1 connection cho video đang hiển thị trong viewport

### Cơ chế

```
WS /ws/stats/{video_id}
  ↓ connect
  Backend gửi ngay snapshot hiện tại: { like_count, view_count, comment_count }
  ↓ giữ kết nối
  Mỗi khi có POST /interactions với video_id này:
    Backend broadcast tới tất cả clients đang xem video đó:
    { "event": "stats_update", "video_id": "...", "like_count": 542, "view_count": 3201, "comment_count": 88 }
  ↓ frontend disconnect khi scroll qua video tiếp theo
```

### WebSocketManager (singleton)

```python
class VideoStatsWSManager:
    """
    Quản lý connections theo video_id.
    connections: Dict[video_id, Set[WebSocket]]
    """
    async def connect(video_id, ws)
    async def disconnect(video_id, ws)
    async def broadcast_stats(video_id, stats_dict)
```

> [!NOTE]
> Không cần Redis pub/sub ở hackathon scale. Singleton in-process là đủ.

---

## 3️⃣ User Interest Vector Update

### Thuật toán: Weighted Average với INTERACTION_WEIGHTS

```
INTERACTION_WEIGHTS = {
    "like":    1.0,   # strong positive signal
    "replay":  0.8,   # strong — rewatched
    "comment": 0.6,   # engaged enough to comment
    "share":   0.5,   # positive but weaker signal
    "skip":   -0.3,   # negative signal
}
```

### Công thức

```
new_interest_vector = normalize(
    current_vector * α  +  video_embedding * weight * (1 - α)
)

α = momentum = 0.85   ← giữ lại 85% vector cũ, blend 15% tín hiệu mới
```

> [!IMPORTANT]
> Dùng **exponential moving average** thay vì cộng trung bình toàn bộ:
> - Cộng trung bình toàn bộ: phải query lại 100 videos mỗi lần → chậm
> - EMA: chỉ cần vector cũ + embedding video mới nhất → O(1) update

### Khi nào trigger update?

```
Interaction type       Trigger update?
─────────────────────────────────────
like                   ✅ immediate (weight 1.0)
replay                 ✅ immediate (weight 0.8)
comment                ✅ immediate (weight 0.6)
share                  ✅ immediate (weight 0.5)
skip                   ✅ immediate (weight -0.3)
watch (behavior_log)   ❌ không (chỉ lưu behavior_log, không update vector)
```

### Pseudo-code

```python
async def update_interest_vector(user_id, video_id, interaction_type):
    weight = INTERACTION_WEIGHTS[interaction_type]
    
    # Fetch in parallel
    user, video = await asyncio.gather(
        user_repo.find_by_id(user_id),
        video_repo.find_by_id(video_id),
    )
    
    current_vec = user["interest_vector"]   # 1536-dim
    video_vec   = video["embedding"]        # 1536-dim
    
    if not video_vec:
        return   # video chưa có embedding → skip
    
    α = 0.85
    new_vec = [
        α * c + (1 - α) * weight * v
        for c, v in zip(current_vec, video_vec)
    ]
    
    # L2-normalize để cosine similarity hoạt động đúng
    magnitude = math.sqrt(sum(x**2 for x in new_vec))
    new_vec = [x / magnitude for x in new_vec] if magnitude > 0 else new_vec
    
    await user_repo.update_interest_vector(user_id, new_vec)
```

---

## 4️⃣ Trending Score — Time-Decay (chống "treo bảng xếp hạng")

### Vấn đề với công thức cũ

```
trending_score = view*1 + like*3 + comment*5   ← tích lũy mãi
```

Video viral từ 3 tháng trước vẫn đứng top → chặn video mới nổi.

### Giải pháp: Time-Decay Score

```
decay_factor = e^(-λ * age_hours)

λ (half-life):
  - 3 ngày  = 0.0096   ← video news/trend ngắn hạn
  - 7 ngày  = 0.0041   ← video entertainment vừa
  - 30 ngày = 0.00096  ← content evergreen

effective_score = raw_score * decay_factor
```

### Phân tầng half-life theo category

```python
HALF_LIFE_HOURS = {
    "news":          72,    # 3 ngày
    "entertainment": 168,   # 7 ngày  
    "sports":        120,   # 5 ngày
    "gaming":        168,   # 7 ngày
    "education":     720,   # 30 ngày
    "lifestyle":     336,   # 14 ngày
    "calming":       720,   # 30 ngày
    "nature":        720,   # 30 ngày
    "cooking":       336,   # 14 ngày
    # default
    "_default":      168,   # 7 ngày
}
```

### Ngưỡng "Out-Trend" Detection

```
Video bị đánh dấu stale nếu THỎA MÃN 1 trong 2 điều kiện:

1. VELOCITY CHECK (3-7 ngày):
   view_velocity_7d = (view_count_now - view_count_7d_ago) / 7
   if view_velocity_7d < VELOCITY_THRESHOLD:
       → video không còn tăng trưởng đủ mạnh
       
2. AGE CHECK:
   if age_days > 30 AND effective_score < TOP_N_THRESHOLD:
       → quá cũ, nhường chỗ cho video mới

VELOCITY_THRESHOLD = max(10, raw_score * 0.01)
  → Video có score 10,000: cần ít nhất 100 views/ngày để còn được coi là trending
```

> [!TIP]
> Để đơn giản cho hackathon: lưu thêm `view_count_snapshot` + `snapshot_at` vào video document mỗi khi scheduler chạy (mỗi 6h). Velocity = delta / hours_elapsed.

### Trending API response với decay

```python
GET /api/v1/videos/trending?limit=10&window=7d

Response:
[
  {
    "id": "...",
    "title": "...",
    "raw_score": 15420,
    "effective_score": 12800,    ← sau time-decay
    "age_hours": 48,
    "is_trending": true,         ← effective_score > threshold
    "velocity_7d": 850,          ← views/ngày trong 7 ngày qua
    ...
  }
]
```

---

## 5️⃣ Files cần tạo/sửa

```
backend/app/
├── repositories/
│   └── interaction_repository.py   ✅ ĐÃ CÓ (đã tạo)
│
├── services/
│   └── interaction_service.py      🔲 CẦN TẠO
│       ├── record_interaction()     → lưu + update vector + broadcast WS
│       ├── create_session()
│       ├── end_session()
│       ├── record_behavior_log()
│       └── get_trending_with_decay()
│
├── controllers/
│   └── interaction_controller.py   🔲 CẦN TẠO
│       ├── REST endpoints
│       └── WebSocket /ws/stats/{video_id}
│
├── utils/
│   └── websocket_manager.py        🔲 CẦN TẠO
│       └── VideoStatsWSManager (singleton)
│
└── main.py                         🔲 CẦN SỬA
    └── include interaction_controller router
```

---

## 6️⃣ Luồng dữ liệu đầy đủ khi user LIKE

```
[FE] POST /api/v1/interactions
  { user_id, video_id, session_id, type: "like", watch_duration, watch_percentage, swipe_speed }
  ↓
[Controller] validate → InteractionService.record_interaction()
  ↓
[Service] asyncio.gather(
  ① repo.insert(interaction_doc)          → interactions collection
  ② repo.increment_video_counters()       → videos.like_count++, trending_score recalc
  ③ update_interest_vector()              → users.interest_vector = EMA update
  ④ session_repo.increment_watched()      → feed_sessions.total_videos_watched++
)
  ↓
[Service] ws_manager.broadcast_stats(video_id, new_counts)
  → All WS clients watching this video_id receive:
    { event: "stats_update", like_count: 541, view_count: 3200, comment_count: 87 }
  ↓
[HTTP Response 201]
  { id, type, timestamp, vector_updated: true }
```

---

## 7️⃣ Câu hỏi cần xác nhận trước khi implement

> [!CAUTION]
> Tôi cần bạn xác nhận các quyết định thiết kế này:

1. **Momentum α = 0.85**: Bạn có muốn điều chỉnh không? Cao hơn → vector thay đổi chậm hơn (ổn định), thấp hơn → phản ứng nhanh hơn nhưng có thể "nhảy" nhiều.

2. **Half-life per category**: Có category nào cần tune lại không?

3. **Velocity threshold**: `view_velocity_7d < 10 views/ngày` → out-trend. Threshold này có hợp lý với seed data của bạn không?

4. **`watch` event**: Hiện tôi thiết kế `behavior_log` (POST /behavior-logs) riêng — KHÔNG update vector. Chỉ dùng để tính fatigue. Có đồng ý không, hay `watch` cũng nên ảnh hưởng nhẹ đến vector?

5. **WebSocket scope**: Mỗi video có 1 WS channel. Frontend phải disconnect khi scroll qua. Bạn có muốn thêm 1 global channel để push thông báo khác không?
