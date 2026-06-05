# 📐 Công thức Interest Vector — EMA Update

**📄 File nguồn:** `app/utils/formula/interest_vector.py`  
**Được dùng bởi:** `interaction_service.py` → `_batch_update_interest_vector()`

---

## Mục đích

**Interest Vector** là "bản đồ sở thích" của người dùng dưới dạng vector số học nhiều chiều. Hệ thống dùng nó để tìm các video "gần" với gu của người dùng nhất thông qua **Cosine Similarity** trong MongoDB Atlas Vector Search.

---

## Hằng số cấu hình

### `EMA_MOMENTUM = 0.85`

Momentum điều chỉnh tốc độ học sở thích mới:
- **0.85** → giữ lại 85% gu cũ, hấp thụ 15% tín hiệu mới
- Giá trị cao → học chậm, ổn định hơn, ít bị nhiễu bởi hành vi nhất thời
- Giá trị thấp → thích nghi nhanh hơn nhưng dễ "quên" sở thích lâu dài

### `INTERACTION_WEIGHTS`

```python
INTERACTION_WEIGHTS = {
    "like":         +1.0,   # Tín hiệu tích cực mạnh nhất
    "replay":       +0.8,   # Xem lại — rất có chủ đích
    "comment":      +0.6,   # Đã đọc, đã suy nghĩ
    "share":        +0.5,   # Muốn người khác xem
    "passive_view": +0.2,   # Xem hết nhưng im lặng
    "skip":         -0.3,   # Tín hiệu tiêu cực — đẩy xa loại nội dung này
}
```

**Trọng số âm (`skip = -0.3`):** Vector người dùng sẽ bị đẩy **ra xa** khỏi embedding của video bị skip. Điều này có nghĩa là những video tương tự sẽ ít xuất hiện hơn trong feed.

---

## Hàm 1: `calculate_ema_vector()` — Cập nhật đơn lẻ

```python
def calculate_ema_vector(
    current_vec: List[float],   # Vector sở thích hiện tại của user
    video_vec: List[float],     # Embedding vector của video vừa tương tác
    weight: float,              # Trọng số từ INTERACTION_WEIGHTS
    momentum: float = 0.85,
) -> List[float]:
```

### Công thức:

```
new_vec[i] = α × current_vec[i]  +  (1 - α) × weight × video_vec[i]

Trong đó α = momentum = 0.85

Sau đó:
magnitude = √(Σ new_vec[i]²)
new_vec[i] = new_vec[i] / magnitude    ← L2 normalize
```

### Tại sao cần L2 Normalize?

MongoDB Atlas Vector Search dùng **cosine similarity** để tìm video gần nhất. Cosine similarity chỉ quan tâm đến **hướng** của vector, không quan tâm đến **độ dài**. L2 normalize đưa vector về độ dài bằng 1 để phép tính cosine similarity hoạt động chính xác.

### Ví dụ minh họa (giả định vector 2 chiều):

```
current_vec = [0.6, 0.8]      # User thích "sports" + "outdoor"
video_vec   = [0.9, 0.4]      # Video thiên về "sports"
weight      = 1.0              # User vừa "like"

new_vec[0] = 0.85 × 0.6  +  0.15 × 1.0 × 0.9 = 0.51 + 0.135 = 0.645
new_vec[1] = 0.85 × 0.8  +  0.15 × 1.0 × 0.4 = 0.68 + 0.060 = 0.740

magnitude = √(0.645² + 0.740²) = √(0.416 + 0.548) = √0.964 ≈ 0.982

new_vec = [0.645/0.982, 0.740/0.982] ≈ [0.657, 0.754]
```

Sau khi like video thể thao, chiều "sports" tăng nhẹ từ 0.6 → 0.657.

---

## Hàm 2: `calculate_batch_ema_vector()` — Cập nhật theo lô (khi kết thúc phiên)

```python
def calculate_batch_ema_vector(
    current_vec: List[float],
    list_of_video_vecs: List[List[float]],
    list_of_weights: List[float],
    momentum: float = 0.85,
) -> List[float]:
```

### Thuật toán:

```
# Bước 1: Tính vector đại diện của cả phiên (trung bình có trọng số)
total_weight = Σ|weight_i|

session_vec[i] = Σ(video_vec_i[j] × weight_i) / total_weight

# Bước 2: EMA blend với vector hiện tại
new_vec[i] = 0.85 × current_vec[i]  +  0.15 × session_vec[i]

# Bước 3: L2 normalize
new_vec = new_vec / ||new_vec||
```

### Khi nào dùng batch?

Hàm `_batch_update_interest_vector()` trong `interaction_service.py` được kích hoạt **khi user kết thúc phiên** (`end_session`). Lý do:

1. **Hiệu quả hơn:** Chỉ query database 1 lần thay vì nhiều lần
2. **Chính xác hơn:** Nhìn toàn bộ phiên để hiểu tổng thể "phiên này user thích gì"
3. **Chống nhiễu:** Một video vô tình xem trong phiên không ảnh hưởng quá lớn

---

## Hàm hỗ trợ: `get_interaction_weight()`

```python
def get_interaction_weight(interaction_type: str) -> float:
    return INTERACTION_WEIGHTS.get(interaction_type, 0.0)
```

Trả về 0.0 cho các loại tương tác không xác định → vector **không thay đổi**.

---

## Vị trí trong hệ thống

```
User like/skip/replay video
        │
        ▼
POST /interactions → record_interaction()
        │
        ├─ Ghi interaction vào MongoDB
        └─ (cuối phiên) _batch_update_interest_vector()
                │
                ├─ Lấy tất cả interactions trong phiên
                ├─ Map video_id → embedding vector
                ├─ calculate_batch_ema_vector()
                └─ Lưu new_vec vào users.interest_vector
```

---

## Lưu ý kỹ thuật

- **Dimension mismatch:** Nếu độ dài `current_vec` khác `video_vec`, hệ thống reset `current_vec = []` (coi như người dùng mới)
- **Cold start:** Nếu user chưa có `interest_vector`, dùng chỉ `session_vec` sau L2 normalize
- **Unknown type:** `get_interaction_weight()` trả về 0.0 → vector không đổi, không gây lỗi
