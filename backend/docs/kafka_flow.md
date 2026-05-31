# 🔄 Luồng xử lý Behavior Log qua Kafka

Tài liệu này mô tả chi tiết cách hệ thống xử lý luồng dữ liệu (data flow) khi người dùng tương tác (view, skip, like...) với một video, từ Frontend tới Backend và đi qua Kafka.

---

## 1. Sơ đồ Kiến trúc (Architecture Diagram)

```mermaid
sequenceDiagram
    participant Client as Frontend (App)
    participant API as FastAPI (InteractionService)
    participant Redis as Redis (Seen Cache)
    participant Kafka as Kafka Topic<br/>(behavior_logs)
    participant Worker as Kafka Consumer<br/>(Background Task)
    participant MongoDB as MongoDB
    participant PubSub as Redis Pub/Sub<br/>(SSE Stream)

    %% Flow bắt đầu
    Client->>+API: POST /api/v1/interactions/behavior_log<br/>(log_id, video_id, swipe_speed...)
    
    %% Bước 1: Cache đồng bộ
    API->>Redis: SADD session:{id}:seen {video_id}
    Note right of API: Bắt buộc ĐỒNG BỘ (sync) để tránh lỗi<br/>"stupid paging" (trùng video) ở Frontend
    
    %% Bước 2: Produce Kafka
    API-)>Kafka: Produce JSON message (Fire-and-forget)
    
    %% Bước 3: Trả response
    API-->>-Client: 201 Created (Nhanh, Non-blocking)

    %% Bước 4: Consumer xử lý ngầm
    Kafka-->>+Worker: Consume message
    
    Worker->>MongoDB: 1. Get consecutive topics
    Worker->>MongoDB: 2. Insert BehaviorLog document
    Worker->>MongoDB: 3. Update session intensity_count
    
    Worker->>Worker: 4. Tính toán Fatigue Score (Độ mỏi)
    Worker->>MongoDB: 5. Update session stats (fatigue, state)
    
    Worker-)>PubSub: 6. Publish session_update (fatigue, state)
    PubSub-->>Client: SSE Event: Cập nhật UI realtime
    
    Worker-->>-Kafka: Tự động commit offset
```

---

## 2. Chi tiết các bước (Step-by-Step)

### Bước 1: Tiếp nhận Request (API Layer)
Khi Frontend gọi API `record_behavior_log`, file `interaction_service.py` sẽ tiếp nhận:
- **Ngay lập tức lưu Redis:** Thêm `video_id` vào danh sách `seen_videos` của session hiện tại. Điều này đảm bảo API `/feed` (lấy video tiếp theo) sẽ không bao giờ trả về lại video này.
- **Đóng gói Message:** Dữ liệu behavior log được đóng gói thành một file JSON (Dict dump).

### Bước 2: Đẩy vào Kafka (Producer)
- Gọi hàm `send_behavior_log` từ `kafka_client.py`.
- Message được đưa vào topic `behavior_logs`. 
- Hành động này là **Fire-and-forget** (thực hiện qua `asyncio.create_task`), API sẽ ngay lập tức trả về HTTP 201 cho Frontend mà không đợi Kafka hay Database.

### Bước 3: Tiêu thụ Message (Consumer Worker)
Bên trong FastAPI có một task chạy ngầm (`run_behavior_log_consumer` trong `behavior_log_consumer.py`) được khởi tạo khi startup app. Nó chạy một vòng lặp vô tận (infinite loop) để liên tục lắng nghe topic `behavior_logs`. Consumer này được thiết kế cực kỳ bền bỉ (robust):
- **Lazy Load DB:** Khởi tạo DB Repositories trễ (bên trong hàm) để tránh lỗi vòng lặp import và đảm bảo DB đã kết nối.
- **Tự động phục hồi (Auto-Recovery):** Trang bị cơ chế Retry & Exponential Back-off (chờ 2s, 4s, 8s... lên đến 30s) nếu mất kết nối Kafka thay vì bị crash.
- **Dừng an toàn (Graceful Shutdown):** Tự động đóng các kết nối khi nhận tín hiệu huỷ (lúc tắt server).

Khi có message mới, Consumer gọi hàm xử lý nghiệp vụ (Pipeline) nặng:
1. **Tính toán ngữ cảnh:** Lấy lịch sử 10 video gần nhất để xem user có đang xem cùng một chủ đề (topic) liên tục không (`consecutive_same_topic`).
2. **Lưu Database:** Lưu tài liệu `BehaviorLog` vào MongoDB.
3. **Cập nhật cường độ:** Tăng bộ đếm `high_intensity_count` hoặc `low_intensity_count` của session.
4. **Tính toán Fatigue Score:** Áp dụng công thức tính độ mỏi dựa vào `watch_duration`, `swipe_speed`, và cường độ.
5. **Cập nhật Trạng thái (Adaptive State):** Lưu Fatigue Score và State (Normal, Warning, v.v.) vào MongoDB.

### Bước 4: Real-time UI Update (SSE)
Sau khi Consumer tính xong Fatigue Score, nó sẽ bắn một message qua Redis Pub/Sub. Hệ thống Server-Sent Events (SSE) của bạn sẽ nhận message này và đẩy thẳng xuống Frontend để cập nhật thanh Fatigue bar mượt mà mà không cần Frontend phải gọi API polling liên tục.

---

## 3. Cơ chế chịu lỗi (Fault Tolerance) & Dead-Letter Queue (DLQ)

Nếu Consumer gặp lỗi trong quá trình xử lý (Ví dụ: Mất kết nối MongoDB, data bị sai định dạng):
1. Dòng code gây lỗi sẽ bị catch exception.
2. Message lỗi đó sẽ được Consumer đẩy sang topic **`behavior_logs_dlq`** (Dead-Letter Queue).
3. Consumer **bỏ qua lỗi và tiếp tục xử lý message tiếp theo**, giúp hệ thống không bị nghẽn (stuck).
4. Các message trong topic DLQ sẽ được giữ trong 7 ngày để Developer có thể xem lại log, fix bug, và chạy script để re-process lại các log này sau.
