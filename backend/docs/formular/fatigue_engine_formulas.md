# 📐 Công thức Fatigue Engine — Đo độ mệt não

> **Phiên bản cập nhật** — thay thế tài liệu cũ bằng mô tả đầy đủ hơn.

**📄 File nguồn:** `app/utils/formula/fatigue.py`  
**Được dùng bởi:** `interaction_service.py` → `_update_session_fatigue_and_state()`

---

## Mục đích

Fatigue Engine đo lường "sức khỏe tâm thần" của người dùng khi lướt video. Nó phát hiện các dấu hiệu của:
- **Doom-scrolling** (cuộn vô thức)
- **Dopamine Exhaustion** (kiệt sức dopamine)
- **Echo Chamber** (bị nhốt trong bong bóng nội dung)

Từ đó, hệ thống tự động điều chỉnh feed để bảo vệ người dùng.

---

## Hằng số cấu hình

### Ngưỡng phán xét hành vi

#### `WATCH_DURATION_TIERS` — Phạt thời gian xem

```python
WATCH_DURATION_TIERS = [
    (2.0,  30),   # < 2s  → +30 pts  ← Doom-scrolling
    (5.0,  15),   # < 5s  → +15 pts
    (15.0,  5),   # < 15s →  +5 pts
    # ≥ 15s       →   0 pts  ← Xem ổn định
]
```

| Thời gian xem | Điểm phạt | Ý nghĩa |
|:---:|:---:|---|
| < 2 giây | **+30** | Doom-scrolling rõ ràng, lướt vô thức |
| < 5 giây | **+15** | Thiếu tập trung nghiêm trọng |
| < 15 giây | **+5** | Thiếu kiên nhẫn nhẹ |
| ≥ 15 giây | **0** | Xem ổn định |

---

#### `SWIPE_SPEED_TIERS` — Phạt tốc độ vuốt

```python
SWIPE_SPEED_TIERS = [
    (800.0, 20),  # > 800 px/s → +20 pts  ← Frantic scrolling
    (400.0, 10),  # > 400 px/s → +10 pts
    # ≤ 400 px/s  →   0 pts   ← Lướt thư thái
]
```

| Tốc độ vuốt | Điểm phạt | Ý nghĩa |
|:---:|:---:|---|
| > 800 px/giây | **+20** | Vuốt giật cục, cáu kỉnh, sốt ruột |
| > 400 px/giây | **+10** | Nhanh hơn bình thường |
| ≤ 400 px/giây | **0** | Lướt thư thái |

---

#### `PASSIVE_PENALTY = 15` — Phạt xem thụ động

Áp dụng khi `is_interaction = False` (không like, không comment, không share):
- **+15 điểm** = trạng thái "zombie" (xem nhưng não không hoạt động)
- **0 điểm** = có ít nhất một tương tác chủ động

---

#### `CONSECUTIVE_TOPIC_TIERS` — Phạt xem cùng chủ đề

```python
CONSECUTIVE_TOPIC_TIERS = [
    (5, 25),   # ≥ 5 video cùng topic → +25 pts  ← Echo Chamber nặng
    (3, 15),   # ≥ 3 video cùng topic → +15 pts
    # < 3       →   0 pts
]
```

---

#### `DOPAMINE_PENALTY_MULTIPLIER = 10.0`

Hệ số nhân cho tỷ lệ video cường độ cao (high intensity) trong phiên lướt.

---

### Ngưỡng phán xét trạng thái

```python
FATIGUE_NORMAL_THRESHOLD   = 40.0   # < 40  → "normal"
FATIGUE_WARNING_THRESHOLD  = 70.0   # ≤ 70  → "warning"
FATIGUE_CRITICAL_THRESHOLD = 80.0   # ≤ 80  → "exhausted" | > 80 → "critical"
```

---

## Hàm 1: `calculate_log_penalty()` — Tính điểm phạt cho 1 video

```python
def calculate_log_penalty(
    watch_duration: float,          # Thời gian xem (giây)
    swipe_speed: float,             # Tốc độ vuốt (px/giây)
    is_interaction: bool,           # Có tương tác không?
    consecutive_same_topic: int,    # Số video cùng topic liên tiếp (0-based)
) -> int:
```

### Thuật toán:

```python
# 1. Tìm tier thời gian xem (first match wins)
for upper_bound, penalty in WATCH_DURATION_TIERS:
    if watch_duration < upper_bound:
        duration_penalty = penalty; break

# 2. Tìm tier tốc độ vuốt (first match wins)
for lower_bound, penalty in SWIPE_SPEED_TIERS:
    if swipe_speed > lower_bound:
        swipe_penalty = penalty; break

# 3. Phạt thụ động
passive_penalty = 15 if not is_interaction else 0

# 4. Phạt trùng chủ đề (count = stored + 1 vì stored là 0-based)
count = consecutive_same_topic + 1
for min_count, penalty in CONSECUTIVE_TOPIC_TIERS:
    if count >= min_count:
        consecutive_penalty = penalty; break

# Tổng
return duration_penalty + swipe_penalty + passive_penalty + consecutive_penalty
```

### Điểm phạt tối đa lý thuyết:

```
30 (lướt < 2s) + 20 (vuốt > 800px/s) + 15 (thụ động) + 25 (≥5 cùng topic) = 90 điểm/video
```

---

## Hàm 2: `calculate_fatigue_score()` — Điểm mệt mỏi tổng

```python
def calculate_fatigue_score(
    log_penalties: List[int],       # Điểm phạt của 10 video gần nhất
    high_intensity_count: int,      # Số video kích thích cao đã xem (toàn phiên)
    low_intensity_count: int,       # Số video nhẹ nhàng đã xem (toàn phiên)
) -> float:                         # [0.0, 100.0]
```

### Công thức:

```
# Phần 1: Hành vi ngắn hạn (10 video gần nhất)
avg_log_points = Σ(log_penalties) / max(5, len(log_penalties))
                                    ^^^^
                    Chia cho ít nhất 5 để làm dịu spike lúc đầu phiên
                    (tránh 1 video dở → điểm tăng vọt ngay từ đầu)

# Phần 2: Tích lũy dopamine (toàn phiên)
total_intensity = high_intensity_count + low_intensity_count
dopamine_penalty = 10.0 × (high_intensity_count / total_intensity)
                              ← tỷ lệ video kích thích cao × hệ số 10

# Tổng hợp và kẹp trong [0.0, 100.0]
fatigue_score = clamp(avg_log_points + dopamine_penalty, 0.0, 100.0)
```

### Hai lớp phát hiện mệt mỏi:

| Lớp | Nguồn dữ liệu | Phát hiện |
|---|---|---|
| `avg_log_points` | 10 video gần nhất | Mệt **ngay lúc này** (short-term) |
| `dopamine_penalty` | Toàn bộ phiên | Tích lũy **mệt từ từ** (long-term) |

### Ví dụ tính toán:

```
Tình huống: User vừa doom-scroll 10 video với watch_duration < 2s, không tương tác nào

log_penalties = [45, 45, 45, 45, 45, 45, 45, 45, 45, 45]  (30 + 15 = 45 mỗi video)
high_intensity_count = 8
low_intensity_count = 2

avg_log_points = 450 / max(5, 10) = 450 / 10 = 45.0
dopamine_penalty = 10.0 × (8 / 10) = 8.0

fatigue_score = 45.0 + 8.0 = 53.0  → Trạng thái: "warning" 🟡
```

---

## Hàm 3: `determine_adaptive_state()` — Quyết định trạng thái

```python
def determine_adaptive_state(fatigue_score: float) -> str:
```

### Ánh xạ điểm → trạng thái:

```
fatigue_score < 40.0  → "normal"
fatigue_score ≤ 70.0  → "warning"
fatigue_score ≤ 80.0  → "exhausted"
fatigue_score > 80.0  → "critical"
```

---

## Tác động của từng trạng thái lên Feed

| Trạng thái | `search_weight` | `trending_weight` | Intensity Filter | Palette Cleanser |
|:---:|:---:|:---:|---|:---:|
| 🟢 normal | 10.0 | 0.001 | Không lọc | Không |
| 🟡 warning | 7.0 | 0.1 | low + medium | Không |
| 🟠 exhausted | 5.0 | 0.5 | Chỉ low | Có (vị trí 2) |
| 🔴 critical | 5.0 | 0.5 | Chỉ low | Có (vị trí 2) |

**Palette Cleanser:** Video thiên nhiên/calming/ASMR được tự động chèn vào vị trí thứ 2 trong feed khi người dùng ở trạng thái exhausted/critical.

---

## Luồng xử lý đầy đủ

```
User rời video → POST /behavior-log
                     │
                     ├─ 1. Ghi seen_id vào Redis (~1ms, đồng bộ)
                     │
                     └─ 2. Kafka message (bất đồng bộ):
                           │
                           ├─ Tính consecutive_same_topic
                           ├─ Lưu BehaviorLog vào MongoDB
                           │
                           └─ _update_session_metrics_pipeline():
                               │
                               ├─ _update_session_intensity()
                               │   → Tăng high/low_intensity_count
                               │
                               └─ _update_session_fatigue_and_state()
                                   │
                                   ├─ Lấy 10 logs gần nhất
                                   ├─ calculate_log_penalty() × 10
                                   ├─ calculate_fatigue_score()
                                   ├─ determine_adaptive_state()
                                   ├─ Lưu vào feed_sessions
                                   └─ Publish SSE → Frontend (real-time)
```

---

## Lưu ý về "Soft Start" (Pha loãng đầu phiên)

```python
avg_log_points = sum(log_penalties) / max(5, len(log_penalties))
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^
```

Chia cho `max(5, N)` nghĩa là:
- Nếu có 1 log → chia cho 5 (thay vì 1) → điểm được "làm dịu" 5 lần
- Nếu có 3 log → chia cho 5 → vẫn làm dịu
- Nếu có ≥ 5 log → chia theo số thực tế

**Mục đích:** Tránh user mở app, lướt 1 video ngắn → ngay lập tức bị "warning". Hệ thống cần ít nhất 5 tín hiệu để có đánh giá đáng tin cậy.
