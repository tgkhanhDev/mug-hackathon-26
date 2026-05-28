# 📱 Luồng Tương Tác User — Hành Trình Xem Video

> **Tài liệu**: Mô tả đầy đủ luồng khi user xem video và tương tác  
> **Trạng thái**: Sẵn sàng triển khai  
> **Cập nhật**: 21/05/2026

---

## 🎬 Tổng quan luồng chính

```
USER LOGIN (tạo session)
    ↓
USER XEM VIDEO
    ├─ TẠO behavior_logs (theo dõi thụ động)
    └─ TÍNH fatigue_score
    ↓
USER TƯƠNG TÁC (LIKE/SKIP/REPLAY)
    ├─ TẠO interactions (sự kiện kinh doanh)
    └─ CẬP NHẬT interest_vector (trọng số EMA)
    ↓
LẦN SAU GỌI GET /feed
    ├─ $vectorSearch(interest_vector, videos.embedding)
    └─ Sắp xếp lại dựa vào fatigue_score
```

---

## 📍 Phase 1: User Đăng Nhập → Tạo Session

```
┌────────────────────────────────────────────────┐
│ User mở app / nhấn "Đăng nhập"                │
└────────────────────────────────────────────────┘
           │
           └──► Gửi request tạo session mới
                └─ Backend nhận user_id
                ↓
           ✅ Response 201:
               SessionID được sinh ra
               ├─ started_at: bây giờ (21/05/2026 10:00:00)
               ├─ ended_at: null (session đang hoạt động)
               ├─ total_videos_watched: 0
               ├─ fatigue_score: 0.0
               └─ adaptive_state: "normal"
                ↓
           MongoDB:
           ├─ TẠO document trong collection feed_sessions
           └─ Frontend lưu Session ID vào localStorage
```

### 🔑 Mục đích

- Tạo một **phiên lướt video** mới cho user
- Dùng để theo dõi trạng thái user trong phiên này
- Lưu fatigue_score để Phase 3 detect user mệt
- Nếu user đã có session active → tái sử dụng (không tạo mới)

---

## 🎥 Phase 2: User Xem Video X → Tạo Behavior Log

Mỗi khi user xem một video (ngay cả khi chỉ cuộn nhanh qua), hệ thống ghi lại hành vi.

```
┌─────────────────────────────────────────────────────────────────┐
│ User cuộn tới Video X trong feed                               │
│ → Ứng dụng phát hiện video xuất hiện trên màn hình              │
└─────────────────────────────────────────────────────────────────┘
         │
         ├─ Frontend ghi lại:
         │  ├─ Bao lâu user xem video (watch_duration)
         │  ├─ Tốc độ vuốt qua video (swipe_speed)
         │  ├─ Phần trăm video đã xem (watch_percentage)
         │  └─ Chủ đề chính của video (topic)
         │
         └──► Gửi request lưu behavior log
              ├─ Ghi vào collection behavior_logs
              ├─ Không modify, chỉ append (immutable)
              └─ Theo dõi toàn bộ hành vi xem (kể cả passive)
                ↓
              ✅ Response 201:
                 Log đã được lưu
                ↓
              📊 TÍNH FATIGUE SCORE:
                 ├─ Lấy 20 logs gần nhất trong session
                 ├─ Tính toán:
                 │  ├─ Trung bình tốc độ vuốt (avg_swipe_speed)
                 │  ├─ Trung bình thời gian xem (avg_watch_duration)
                 │  ├─ Số lần passive scroll
                 │  └─ Số video intensity cao
                 ├─ Công thức: fatigue = swipe_nhanh + watch_ít + intensity_cao
                 └─ Kết quả: Điểm mệt mỏi 0-100
```

### 📌 Ý nghĩa Behavior Log

- **Ghi lại toàn bộ hành vi**: User xem được ghi, dù có bấm nút hay không
- **Append-only**: Mỗi video = 1 document mới, không update
- **Phục vụ Fatigue Engine**: Dùng để phát hiện user có mệt không
- **TTL 30 ngày**: Chỉ giữ lại dữ liệu gần đây để tiết kiệm storage

---

## 🎯 Phase 3: User Tương Tác (LIKE/SKIP/REPLAY)

User tác động chủ động với video X:

```
┌────────────────────────────────────────────────┐
│ User bấm nút LIKE trên video                   │
│ (hoặc SKIP / COMMENT / REPLAY / SHARE)        │
└────────────────────────────────────────────────┘
         │
         └──► Gửi request tương tác
              ├─ Loại tương tác (like, skip, replay...)
              ├─ Bao lâu đã xem video
              ├─ Phần trăm video xem được
              └─ Số lần xem lại video
                ↓
              ✅ Response 201: API trả về NGAY (nhanh ⚡)
                 (Không chờ update interest_vector)
                ↓
              🔄 BACKEND TỰ ĐỘNG LÀM (Chạy song song):
                 
                 ① INSERT interactions
                 │  └─ Lưu sự kiện like/skip/replay
                 │  └─ Collection interactions
                 │  └─ Append-only (không update)
                 │
                 ② Increment video counters
                 │  └─ like_count++
                 │  └─ trending_score được tính lại
                 │  └─ Atomic update (đảm bảo đúng)
                 │
                 ③ ❌ KHÔNG update interest_vector ngay
                 │  └─ Đợi khi session kết thúc
                 │
                 ④ Tăng số video đã xem trong session
                 │  └─ total_videos_watched++
                 │
                 ⑤ Broadcast qua WebSocket
                    └─ Gửi tới tất cả clients xem video này
                    └─ Thông báo: có bao nhiêu lượt like, xem, bình luận
```

### 🔑 Ý nghĩa Interaction

- **Chỉ tương tác chủ ý**: Chỉ khi user bấm nút (không phải passive scroll)
- **Phục vụ Recommendation Engine**: Dùng để update sở thích user
- **Trọng số khác nhau**:
  - Like = 1.0 (user thích nhất)
  - Replay = 0.8 (xem lại = thích nhưng chưa bằng like)
  - Comment = 0.6 (có tương tác)
  - Skip = -0.3 (user không thích)

---

## 📊 Phase 4: Session Kết Thúc → Cập Nhật Interest Vector Hàng Loạt

Khi user đóng app hoặc inactive 30 phút:

```
┌────────────────────────────────────────────────┐
│ User đóng app / Hết phiên lướt                │
│ Frontend gửi: PUT /sessions/{id}/end          │
└────────────────────────────────────────────────┘
         │
         └──► Backend bắt đầu batch update:
              
              ① LẤY TẤT CẢ interactions trong session
              │  ├─ Query mongoDB lấy tất cả like/skip/replay
              │  ├─ Max 1000 interactions mỗi session
              │  └─ Tương tự: Lấy 20 interactions gần đây = tối ưu
              │
              ② TÍNH TOÁN interested_vector hàng loạt
              │  ├─ Công thức: 85% giữ cái cũ + 15% thêm tín hiệu mới
              │  ├─ Tín hiệu mới = trung bình weighted của all interactions
              │  └─ Ví dụ: Like 5 video "coding" + skip 1 video "gaming"
              │     = vector "coding" tăng lên, "gaming" giảm xuống
              │
              ③ NORMALIZE vector
              │  └─ Đảm bảo vector sử dụng được cho $vectorSearch
              │
              ④ UPDATE users.interest_vector (1 lần duy nhất)
              │  └─ MongoDB: LƯU vector cập nhật vào DB
              │
              ⑤ TÍNH & LƯU fatigue_score
              │  ├─ Lấy 20 behavior_logs gần nhất
              │  ├─ Tính điểm mệt mỏi
              │  └─ Lưu vào feed_sessions
              │
              ⑥ ĐÁNH DẤU session kết thúc
                 ├─ ended_at = current time
                 └─ adaptive_state = "normal" / "warning" / "exhausted"
                ↓
              ✅ Response 200:
                 Session đã kết thúc
                 Vector đã cập nhật
                 Fatigue score đã tính
```

### 📌 Tại sao cập nhật khi kết thúc session?

**Hiệu quả cao**:
- 1 lần cập nhật vector thay vì 20 lần
- 1 lần write DB thay vì 20 lần
- Tiệt kiệm tài nguyên DB + network

**Ý nghĩa**:
- Session end = user hoàn thành 1 chu kỳ lướt video
- Đó là lúc tốt để "suy ngẫm" về sở thích của user
- Concept: "Disconnect to Reflect"

---

## 🚀 Phase 5: Session Tiếp Theo → GET /feed với Vector Mới

Khi user mở app lần sau (24h sau):

```
┌────────────────────────────────────────────────┐
│ User mở app lại (ngày hôm sau)                 │
│ Frontend: TẠO session mới + GỌI GET /feed      │
└────────────────────────────────────────────────┘
         │
         └──► Backend xử lý GET /feed:
              
              ① LẤY session hiện tại
              │  └─ Tạo session mới nếu chưa có active session
              │
              ② TÍNH TOÁN fatigue_score
              │  ├─ Lấy 20 behavior_logs gần nhất
              │  ├─ Tính điểm mệt mỏi của phiên mới
              │  └─ Xác định trạng thái: normal / warning / exhausted
              │
              ③ LẤY interest_vector của user
              │  └─ Vector được cập nhật từ phiên hôm qua ✅
              │
              ④ TÌM videos tương tự
              │  ├─ $vectorSearch(user.interest_vector, videos.embedding)
              │  ├─ Tìm 30 video "gần nhất" về chủ đề
              │  └─ Sắp xếp theo similarity score
              │
              ⑤ NẾU user mệt (fatigue_score > 70):
              │  ├─ LỌC: chỉ giữ video intensity thấp/trung
              │  ├─ LOẠI: video intensity cao (ragebait, drama)
              │  └─ ĐẨY LÊN: video calm, relaxing (ASMR, nature)
              │
              └──► TRẢ VỀ top 10 videos
                   └─ Mỗi video: title, embedding, intensity, ...
                ↓
              ✅ Response 200:
                 [
                   {
                     "title": "10 Yoga Techniques for Relaxation",
                     "similarity_score": 0.87,
                     "intensity_level": "low",
                     ...
                   },
                   ...
                 ]
```

### 🎯 Kết quả chính

- ✅ Feed được cá nhân hóa dựa trên tương tác **hôm qua**
- ✅ Nếu user mệt → content calm được prioritize
- ✅ Interest vector **luôn cập nhật** sau mỗi session

---

## 📌 Tóm tắt 5 Phase

| Phase | Hành động | Collection | Kiểu update | Thời gian |
|---|---|---|---|---|
| 1 | Đăng nhập | feed_sessions | INSERT | Ngay lập tức |
| 2 | Xem video | behavior_logs | INSERT (append) | Ngay lập tức |
| 2.5 | Tính fatigue | feed_sessions | UPDATE | Khi gọi GET /feed |
| 3 | Like/Skip/Replay | interactions | INSERT | Ngay lập tức |
| 4 | Đóng app | users, feed_sessions | UPDATE (batch) | Khi PUT /sessions/{id}/end |
| 5 | Phiên tiếp theo | (chỉ đọc) | — | GET /feed dùng vector mới |

---

## 🎯 Điểm quan trọng

### ✅ Behavior Logs vs Interactions

| | Behavior Logs | Interactions |
|---|---|---|
| **Khi nào tạo** | Mỗi video xem (passive hoặc active) | Khi user bấm nút (like/skip/replay) |
| **Loại data** | Toàn bộ hành vi thô | Só kiến kinh doanh chủ ý |
| **Update hay append** | Chỉ append (thêm mới, không sửa) | Chỉ append |
| **Dùng để** | Tính fatigue_score | Update interest_vector |
| **TTL** | 30 ngày | Vô hạn |

### ✅ Tại sao update interest_vector khi session end?

1. **Nhanh hơn**: 1 lần write thay vì 20 lần
2. **Hiệu quả**: Batch processing (tất cả signals cùng lúc)
3. **Có ý nghĩa**: Session end = điểm reflect tự nhiên
4. **Đơn giản**: Logic rõ ràng, không race condition

### ✅ Tại sao có 2 collection riêng?

- `behavior_logs` → Phục vụ **Fatigue Engine** (detect user mệt?)
- `interactions` → Phục vụ **Recommendation Engine** (user thích gì?)
- Khác loại data, khác use-case → Tách để tối ưu

---

## 📚 Tài liệu liên quan

- [ERD Schema](./erd_schema.md) — Chi tiết các collection
- [Interest Vector Approaches](./interest_vector_approaches.md) — So sánh 3 cách update
- [Interaction API Design](../backend/docs/interaction_api_design.md) — API contracts

