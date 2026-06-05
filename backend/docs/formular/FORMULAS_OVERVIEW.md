# 📐 Tổng quan Công thức Thuật toán — GoTouchGrass Backend

> **Dành cho:** Developer, Product, và End-user muốn hiểu cách hệ thống hoạt động.  
> **Vị trí code:** `backend/app/utils/formula/`  
> **Cập nhật lần cuối:** 2026-06-05

---

## Mục lục

1. [Kiến trúc tổng quan](#1-kiến-trúc-tổng-quan)
2. [Công thức 1 — Fatigue Engine (Đo độ mệt não)](#2-công-thức-1--fatigue-engine-đo-độ-mệt-não)
3. [Công thức 2 — Interest Vector (Học sở thích người dùng)](#3-công-thức-2--interest-vector-học-sở-thích-người-dùng)
4. [Công thức 3 — Trending Score (Xếp hạng video hot)](#4-công-thức-3--trending-score-xếp-hạng-video-hot)
5. [Cách 3 công thức phối hợp với nhau](#5-cách-3-công-thức-phối-hợp-với-nhau)

---

## 1. Kiến trúc tổng quan

```
Người dùng lướt video
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Mỗi lần rời khỏi video → ghi Behavior Log          │
│  (thời gian xem, tốc độ vuốt, có tương tác không)  │
└────────────────────┬────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │   FATIGUE ENGINE    │  ← Công thức 1
          │  (Tính điểm mệt mỏi)│
          └──────────┬──────────┘
                     │
        ┌────────────▼────────────┐
        │   ADAPTIVE STATE        │
        │  normal / warning /      │
        │  exhausted / critical   │
        └────────────┬────────────┘
                     │
     ┌───────────────▼───────────────┐
     │      FEED GENERATION          │
     │  ← dùng Interest Vector (2)   │
     │  ← dùng Trending Score (3)    │
     │  ← lọc theo intensity_level   │
     └───────────────────────────────┘
```

**Ý nghĩa đơn giản:** Hệ thống liên tục theo dõi hành vi lướt của bạn để hiểu bạn đang "mệt não" đến mức nào, từ đó tự động điều chỉnh feed cho phù hợp — không phải để chiều bạn vô tận, mà để bảo vệ sức khỏe tâm thần.

---

## 2. Công thức 1 — Fatigue Engine (Đo độ mệt não)

**📄 File:** `app/utils/formula/fatigue.py`

### 2.1 Tại sao cần đo "mệt não"?

Khi bạn lướt TikTok, YouTube Shorts hay bất kỳ short-form video nào trong thời gian dài, não bạn tiết ra dopamine liên tục. Điều này dẫn đến trạng thái mà khoa học gọi là **Dopamine Exhaustion** — bạn tiếp tục lướt nhưng thực ra không còn thấy vui nữa, chỉ là theo thói quen. GoTouchGrass phát hiện điều này và can thiệp.

---

### 2.2 Bước 1: Tính điểm phạt cho từng video — `calculate_log_penalty()`

Mỗi lần bạn rời một video, hệ thống chấm 4 tiêu chí:

#### Tiêu chí A: Thời gian xem (`watch_duration`)

| Thời gian xem | Điểm phạt | Ý nghĩa |
|:---:|:---:|---|
| < 2 giây | **+30 điểm** | Doom-scrolling — lướt vô thức, não tìm "cú hích" nhưng không thỏa mãn |
| < 5 giây | **+15 điểm** | Lướt rất nhanh, mất tập trung |
| < 15 giây | **+5 điểm** | Thiếu kiên nhẫn nhẹ |
| ≥ 15 giây | **0 điểm** | Xem ổn định, không bị phạt |

> **Giải thích dễ hiểu:** Nếu bạn không dừng lại video nào quá 2 giây, hệ thống hiểu bạn đang "lướt xác sống" — bạn nhìn nhưng thực ra không xem gì. Đây là dấu hiệu cổ điển của doom-scrolling.

---

#### Tiêu chí B: Tốc độ vuốt (`swipe_speed`)

| Tốc độ vuốt | Điểm phạt | Ý nghĩa |
|:---:|:---:|---|
| > 800 px/giây | **+20 điểm** | Vuốt giật cục, vội vã (Frantic scrolling) |
| > 400 px/giây | **+10 điểm** | Vuốt nhanh hơn bình thường |
| ≤ 400 px/giây | **0 điểm** | Lướt thư thái |

> **Giải thích dễ hiểu:** Khi bạn bực bội hoặc bị cuốn vào vòng lặp tìm kiếm nội dung kích thích, ngón tay bạn sẽ vuốt mạnh và nhanh hơn mà không tự biết. Cảm biến tốc độ vuốt phát hiện điều này.

---

#### Tiêu chí C: Xem thụ động (`is_interaction`)

| Hành vi | Điểm phạt | Ý nghĩa |
|:---:|:---:|---|
| Không like/comment/share | **+15 điểm** | Trạng thái "zombie" — xem nhưng mắt lờ đờ |
| Có tương tác ít nhất 1 lần | **0 điểm** | Xem có chủ đích |

> **Giải thích dễ hiểu:** Khi bạn thực sự thích video và bấm like hay comment, đó là dấu hiệu bạn còn nhận thức. Khi bạn chỉ nhìn mà không làm gì, não bạn đang ở chế độ "auto-pilot".

---

#### Tiêu chí D: Xem lặp cùng chủ đề (`consecutive_same_topic`)

| Số video cùng topic liên tiếp | Điểm phạt | Ý nghĩa |
|:---:|:---:|---|
| ≥ 5 video | **+25 điểm** | Echo Chamber nặng |
| ≥ 3 video | **+15 điểm** | Bắt đầu bị "nghiện" chủ đề |
| < 3 video | **0 điểm** | Nội dung đa dạng |

> **Giải thích dễ hiểu:** Đây là cơ chế chống "Buồng vang" (Echo Chamber). Dù bạn rất thích xem video về mèo, nếu thuật toán cứ nhồi mèo mãi, bạn sẽ bị nhốt trong một bong bóng thông tin và mất đi sự đa dạng nhận thức.

---

**Công thức tổng hợp (cho 1 video):**
```
Điểm phạt = Phạt thời gian + Phạt tốc độ vuốt + Phạt thụ động + Phạt trùng chủ đề
```

---

### 2.3 Bước 2: Tính điểm mệt mỏi tổng — `calculate_fatigue_score()`

```
                   Σ(điểm phạt 10 video gần nhất)
avg_log_points = ──────────────────────────────────
                        max(5, số log)

                         high_intensity_count
dopamine_penalty = 10 × ──────────────────────
                         total_intensity_count

fatigue_score = clamp(avg_log_points + dopamine_penalty, 0.0, 100.0)
```

**Hai thành phần:**

| Thành phần | Nguồn dữ liệu | Ý nghĩa |
|---|---|---|
| `avg_log_points` | 10 video gần nhất | Đo **hành vi ngắn hạn** (mệt ngay bây giờ) |
| `dopamine_penalty` | Toàn bộ phiên lướt | Đo **tích lũy dopamine dài hạn** (mệt từ từ) |

> **Giải thích dễ hiểu:** Tưởng tượng đồng hồ đo mệt mỏi của bạn có **2 kim**. Kim thứ nhất đo hành vi 10 video vừa rồi (kim này nhảy nhanh). Kim thứ hai tích lũy chậm theo suốt buổi lướt — bạn xem càng nhiều video cường độ cao (giật gân, kích thích), kim này càng tăng.

---

### 2.4 Bước 3: Quyết định trạng thái — `determine_adaptive_state()`

| Điểm mệt mỏi | Trạng thái | Hành động của Feed |
|:---:|:---:|---|
| < 40 | 🟢 **normal** | Feed cá nhân hóa tối đa theo sở thích |
| 40 – 70 | 🟡 **warning** | Trộn thêm video nhẹ nhàng, giảm bớt nội dung kích thích |
| 71 – 80 | 🟠 **exhausted** | Chỉ trả về video cường độ thấp (thiên nhiên, ASMR, nấu ăn...) |
| > 80 | 🔴 **critical** | Cực hạn: Feed toàn video thư giãn + có thể hiện thông báo nghỉ ngơi |

> **Giải thích dễ hiểu:** Giống như đèn báo mệt mỏi trong xe hơi — xanh là ổn, đỏ là cần dừng lại nghỉ.

---

## 3. Công thức 2 — Interest Vector (Học sở thích người dùng)

**📄 File:** `app/utils/formula/interest_vector.py`

### 3.1 Interest Vector là gì?

Mỗi người dùng được đại diện bởi một **vector số học** — một dãy hàng trăm con số thập phân — phản ánh "gu" nội dung của họ. Mỗi video cũng có một vector tương tự (được tính bởi AI từ nội dung video).

**Khi vector của bạn và vector của video "gần nhau"** (đo bằng độ tương đồng cosine), video đó khả năng cao bạn sẽ thích.

---

### 3.2 Trọng số tương tác (`INTERACTION_WEIGHTS`)

| Hành động | Trọng số | Chiều tác động |
|:---:|:---:|---|
| `like` | **+1.0** | Kéo mạnh về phía video này |
| `replay` | **+0.8** | Xem lại — tín hiệu rất mạnh |
| `comment` | **+0.6** | Đã tương tác sâu |
| `share` | **+0.5** | Tích cực nhưng nhẹ hơn |
| `passive_view` | **+0.2** | Xem hết nhưng không làm gì |
| `skip` | **-0.3** | Đẩy vector **ra xa** video này |

> **Giải thích dễ hiểu:** Mỗi lần bạn bấm like, hệ thống "ghi nhớ" loại nội dung đó và sau này tìm thêm video tương tự. Mỗi lần bạn skip, hệ thống học rằng bạn không thích loại nội dung đó và dần tránh đi.

---

### 3.3 Công thức EMA — `calculate_ema_vector()`

**EMA = Exponential Moving Average (Trung bình động theo hàm mũ)**

```
new_vec[i] = α × old_vec[i]  +  (1 - α) × weight × video_vec[i]

Trong đó:
  α (momentum) = 0.85   →  giữ lại 85% sở thích cũ
  (1 - α)      = 0.15   →  hấp thụ 15% tín hiệu mới
  weight        = trọng số tương tác (bảng trên)
  
Sau đó: L2-normalize (chuẩn hóa độ dài vector về 1.0)
```

**Tại sao cần 85% momentum?**

> **Giải thích dễ hiểu:** Nếu bạn thích xem video về lập trình trong 3 tháng qua, hệ thống không "quên ngay" chỉ vì bạn vô tình xem 1 video về nấu ăn hôm nay. Momentum 85% đảm bảo sở thích lâu dài không bị xóa bởi hành vi nhất thời. Nhưng nếu bạn **liên tục** xem nấu ăn nhiều ngày, vector sẽ dần dịch chuyển theo.

---

### 3.4 Cập nhật theo lô — `calculate_batch_ema_vector()`

Khi một phiên lướt kết thúc, thay vì cập nhật vector từng tương tác một, hệ thống:

1. **Gom tất cả tương tác** trong phiên vừa xong
2. **Tính vector đại diện phiên** (trung bình có trọng số của tất cả video đã tương tác)
3. **Áp dụng EMA một lần** để cập nhật vector người dùng

```
session_vec[i] = Σ(video_vec[i] × weight) / Σ|weight|

new_user_vec = 0.85 × old_user_vec + 0.15 × session_vec
(sau đó L2-normalize)
```

> **Giải thích dễ hiểu:** Thay vì cập nhật "gu" của bạn sau mỗi video (tốn tài nguyên và dễ bị nhiễu), hệ thống đợi bạn xong một phiên lướt rồi mới tổng kết "phiên hôm nay bạn thích gì nhất" và cập nhật một lần. Chính xác hơn và hiệu quả hơn.

---

## 4. Công thức 3 — Trending Score (Xếp hạng video hot)

**📄 File:** `app/utils/formula/trending.py`

### 4.1 Điểm Trending Thô — `calculate_raw_trending_score()`

```
trending_score = view_count × 1  +  like_count × 3  +  comment_count × 5
```

| Hành động | Hệ số | Lý do |
|:---:|:---:|---|
| View | × 1 | Dễ có — chỉ cần mở video |
| Like | × 3 | Có chủ đích hơn |
| Comment | × 5 | Tốn công nhất — cho thấy sự gắn kết thực sự |

> **Giải thích dễ hiểu:** Video có 1000 comment được xem là "hot" hơn nhiều so với video có 5000 view nhưng không ai comment. Bởi vì comment chứng tỏ người ta thực sự bị đánh động bởi nội dung.

---

### 4.2 Phân rã theo thời gian — `calculate_time_decay_metrics()`

**Vấn đề:** Nếu chỉ dùng điểm thô, video cũ sẽ luôn thắng vì tích lũy view lâu hơn.

**Giải pháp: Time Decay (Phân rã theo thời gian)**

```
λ (decay constant) = ln(2) / half_life_hours

decay_factor = e^(-λ × age_hours)

effective_score = raw_score × decay_factor
```

**Half-life (Thời gian giảm nửa) theo danh mục:**

| Danh mục | Half-life | Ý nghĩa |
|---|:---:|---|
| Entertainment, Gaming | 168 giờ (7 ngày) | Nội dung "tươi" — mất độ hot nhanh |
| Sports | 120 giờ (5 ngày) | Tin thể thao lỗi thời rất nhanh |
| Lifestyle, Cooking | 336 giờ (14 ngày) | Nội dung sống lâu hơn |
| Education, Calming, Nature | 720 giờ (30 ngày) | Giá trị lâu dài |

> **Giải thích dễ hiểu:** Video hài về meme trên mạng hôm nay có thể đạt triệu view, nhưng 2 tuần sau không ai xem nữa. Trong khi đó, video "cách nấu phở ngon" vẫn được tìm kiếm sau nhiều năm. Công thức này phản ánh "tuổi thọ" khác nhau của từng loại nội dung.

---

### 4.3 Velocity (Tốc độ lan truyền)

```
velocity_7d = (view_count - snapshot_views) / elapsed_days
```

Video được coi là **đang trending** khi:
- `velocity_7d ≥ 10 view/ngày` (ít nhất 10 view mỗi ngày)
- `age_hours ≤ 28 ngày` (không quá cũ)

> **Giải thích dễ hiểu:** Một video có 10,000 view nhưng tích lũy trong 1 năm sẽ không được xem là trending. Nhưng video có 10,000 view chỉ trong 2 tuần — đó mới là viral thực sự.

---

## 5. Cách 3 công thức phối hợp với nhau

```
┌─────────────────────────────────────────────────────────────────────┐
│                      KHI USER GỌI "LẤY FEED MỚI"                   │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
                  ┌───────────────────▼───────────────────┐
                  │  1. Đọc adaptive_state từ phiên hiện tại │
                  │     (Công thức 1 - Fatigue Engine)       │
                  └───────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │ normal                │ warning               │ exhausted/critical
              ▼                       ▼                        ▼
     Tìm video giống        Tìm video vừa giống     Chỉ trả video
     interest_vector        vừa có intensity=low    intensity=low
     nhất (search_weight=10) (search_weight=7)       (search_weight=5)
              │                       │                        │
              └───────────────────────┼───────────────────────┘
                                      │
              ┌───────────────────────▼───────────────────────┐
              │  2. Truy vấn video bằng Interest Vector       │
              │     (Công thức 2 - EMA Interest Vector)       │
              │                                               │
              │  + Xếp hạng thêm bằng Trending Score         │
              │    (Công thức 3 - Time-decay Trending)        │
              └───────────────────────┬───────────────────────┘
                                      │
              ┌───────────────────────▼───────────────────────┐
              │  3. Exploration Factor (Chống Filter Bubble)  │
              │     → Chèn 1 video trending vào cuối batch    │
              └───────────────────────┬───────────────────────┘
                                      │
              ┌───────────────────────▼───────────────────────┐
              │  4. Palette Cleanser (chỉ khi exhausted)      │
              │     → Chèn 1 video thiên nhiên/ASMR vào vị   │
              │       trí thứ 2 để làm dịu não người dùng     │
              └───────────────────────────────────────────────┘
```

### Bảng tóm tắt các tham số trọng số feed

| Trạng thái | `search_weight` | `trending_weight` | Intensity filter |
|:---:|:---:|:---:|---|
| normal | 10.0 | 0.001 | Không giới hạn |
| warning | 7.0 | 0.1 | low + medium |
| exhausted | 5.0 | 0.5 | Chỉ low |
| critical | 5.0 | 0.5 | Chỉ low |

> **Giải thích dễ hiểu cho `search_weight` và `trending_weight`:** Đây là "thanh trượt" giữa hai chiến lược gợi ý:
> - `search_weight` cao → Ưu tiên video **giống gu của bạn** nhất (cá nhân hóa)
> - `trending_weight` cao → Ưu tiên video **đang hot trên toàn hệ thống** (trending)
>
> Khi bạn mệt, hệ thống chủ động giảm bớt "chiều bạn" (giảm search_weight) và tăng trending — bởi vì khi mệt, bạn cần một cú "refresh" với nội dung mới mẻ thay vì cùng một loại nội dung bạn thường xem.

---

## Phụ lục: Sơ đồ luồng dữ liệu đầy đủ

```
User lướt video
    │
    ├─ Rời video → POST /behavior-log
    │                   │
    │                   ├─ Ghi vào Redis (ngay lập tức, ~1ms)
    │                   │
    │                   └─ Kafka Consumer (bất đồng bộ):
    │                         1. Tính consecutive_same_topic
    │                         2. Lưu MongoDB
    │                         3. calculate_log_penalty()
    │                         4. calculate_fatigue_score()
    │                         5. determine_adaptive_state()
    │                         6. Cập nhật feed_session
    │                         7. Push SSE → Frontend (real-time)
    │
    ├─ Like/Skip/Share → POST /interactions
    │                        │
    │                        └─ Ghi interaction + tăng counter video
    │
    └─ Kết thúc phiên → POST /sessions/{id}/end
                             │
                             └─ calculate_batch_ema_vector()
                                 → Cập nhật interest_vector người dùng
```

---

*Tài liệu được tạo tự động từ source code. Nếu có thay đổi logic, vui lòng cập nhật tài liệu này.*
