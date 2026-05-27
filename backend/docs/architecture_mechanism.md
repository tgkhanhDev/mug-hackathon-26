# Kiến Trúc và Cơ Chế Xử Lý Video Bất Đồng Bộ (Architecture & Mechanisms)

Tài liệu này mô tả chi tiết kiến trúc hệ thống, quy trình tuần tự của luồng tải video lên, vòng đời trạng thái của video trong cơ sở dữ liệu, và tác động của nó đối với công cụ đề xuất tin tức (Feed Recommendation Engine).

---

## 1. Sơ Đồ Kiến Trúc Hệ Thống (High-Level Architecture)

Hệ thống hoạt động theo cơ chế hướng sự kiện (event-driven / task queue pattern):

```mermaid
graph TD
    Client[📱 Client / Web App] -->|1. POST /videos| API[🌿 FastAPI Web Server]
    API -->|2. Save File| Disk[(💾 Temporary Storage /tmp)]
    API -->|3. Create Placeholder| DB[(🍃 MongoDB Atlas)]
    API -->|4. Publish Task| Rabbit[🐇 RabbitMQ Broker]
    API -->|5. Return 201 'processing'| Client
    
    subgraph Celery Background Cluster
        Worker[⚙️ Celery Worker] <-->|6. Fetch Task| Rabbit
        Worker -->|7. Read File| Disk
        Worker -->|8. Transcode HLS & Thumbnail| FFmpeg[🎬 FFmpeg Tool]
        Worker -->|9. Upload HLS folder| MinIO[(🪣 Local MinIO Storage)]
        Worker -->|10. Extract Zero-Shot Metadata| HF[🤗 Hugging Face API]
        Worker -->|11. Generate Vector Embedding| OpenAI[🧠 OpenAI API / Mock]
        Worker -->|12. Update video to 'completed'| DB
        Worker -->|13. Clean Temp Files| Disk
    end
```

---

## 2. Quy Trình Tuần Tự (Sequence Diagram)

Quy trình từ lúc Client tải video lên cho đến khi video sẵn sàng hiển thị trên Feed:

```mermaid
sequenceDiagram
    autonumber
    actor Client as 📱 Client
    participant API as 🌿 FastAPI Server
    participant DB as 🍃 MongoDB Atlas
    participant Rabbit as 🐇 RabbitMQ Broker
    participant Worker as ⚙️ Celery Worker
    participant MinIO as 🪣 Local MinIO

    Client->>API: POST /api/v1/videos (Multipart Form + Video File)
    Note over API: Lưu video vào file tạm:<br/>/tmp/uploads/{folder_id}.mp4
    API->>DB: Ghi bản ghi video placeholder (status="processing")
    DB-->>API: Trả về video_id
    API->>Rabbit: Gửi task process_video_task(video_id, path, ...)
    API-->>Client: Trả về HTTP 201 Created (status="processing", id=video_id)
    Note over Client: Trực quan hóa tiến trình cho user.<br/>API phản hồi cực nhanh (<200ms)

    Note over Worker: Worker nhận task từ hàng đợi RabbitMQ
    Worker->>DB: [Kiểm tra Idempotency] Trạng thái video có phải "completed"?
    DB-->>Worker: Chưa completed
    Worker->>Worker: Chạy FFmpeg (ffprobe metadata + trích thumbnail)
    Worker->>Worker: Chạy FFmpeg phân mảnh HLS (.m3u8 & .m4s segments)
    Worker->>MinIO: Tải thư mục HLS & thumbnail lên bucket media
    MinIO-->>Worker: Trả về URL playlist.m3u8 và thumbnail.jpg
    Worker->>Worker: Gán nhãn AI & sinh vector embedding
    Worker->>DB: Cập nhật bản ghi video (status="completed", url=playlist_url, ...)
    Note over Worker: Dọn dẹp tệp tạm trên ổ đĩa /tmp
```

---

## 3. Vòng Đời Trạng Thái Video (Database Video Status Lifecycle)

Mỗi video được đại diện bởi một tài liệu (document) trong collection `videos` chứa trường `status` lưu trữ trạng thái xử lý hiện thời.

```mermaid
stateDiagram-v2
    [*] --> processing : Client tải video thành công, ghi placeholder vào DB
    
    processing --> completed : FFmpeg chunking, MinIO upload & AI embedding thành công
    processing --> failed : Lỗi transcode, lỗi API AI, hoặc lỗi upload MinIO
    processing --> failed_queue : RabbitMQ bị sập/không thể kết nối khi gọi task
    
    processing --> failed : Stuck Video Job phát hiện video kẹt > 15 phút
    
    completed --> [*] : Sẵn sàng đề xuất trên Feed và Tìm kiếm
    failed --> [*] : Bị ẩn hoàn toàn, cho phép xóa/tải lại
    failed_queue --> [*] : Bị ẩn hoàn toàn, hệ thống ghi nhận bảo trì
```

### Chi tiết các trạng thái:
1. **`processing`**: Trạng thái mặc định ban đầu. Video đang nằm trong hàng đợi hoặc đang được xử lý bởi Celery Worker.
2. **`completed`**: Quá trình xử lý video (cắt HLS, tạo thumbnail, gán nhãn AI, sinh vector embedding) hoàn tất. Video đã sẵn sàng để phát trực tuyến và phân phối.
3. **`failed`**: Đã xảy ra lỗi trong quá trình xử lý nền (ví dụ: lỗi định dạng video, hết dung lượng đĩa, timeout tiến trình FFmpeg).
4. **`failed_queue`**: Không thể đẩy tác vụ vào hàng đợi do lỗi kết nối giữa FastAPI và RabbitMQ.

---

## 4. Tích Hợp Vào Hệ Thống Đề Xuất (Feed Recommendation Integration)

Để tránh hiện tượng người dùng nhìn thấy các video chưa xử lý xong (lỗi không phát được hoặc thiếu ảnh thu nhỏ), hệ thống Feed đã cấu hình lọc nghiêm ngặt theo trạng thái:

### A. Lọc Mặc Định Cho Feed & Trending
Tất cả các truy vấn danh sách, xếp hạng thịnh hành (Trending), hoặc lấy ngẫu nhiên calming videos đều được chèn thêm điều kiện lọc:
$$\{\text{"status"}: \text{"completed"}\}$$

* *Vị trí xử lý*: `VideoRepository.find_many`, `VideoRepository.find_trending`, và `VideoRepository.find_random_calming`.

### B. Lọc Trong Tìm Kiếm Vector Atlas (Vector Search Post-Filter)
Khi thực hiện truy vấn tìm kiếm ngữ nghĩa bằng vector (`$vectorSearch`), điều kiện lọc trạng thái được chèn vào tầng `$match` ngay sau bước tìm kiếm vector. Quy trình này đảm bảo chỉ các video có trạng thái `"completed"` mới được đưa vào công thức tính điểm Fatigue và rebalance feed:

```python
# Trích đoạn logic trong VideoRepository.vector_search
status_filter = {"status": "completed"}
combined_filter = {"$and": [status_filter, filter_stage]} if filter_stage else status_filter
pipeline.insert(1, {"$match": combined_filter})
```

Nhờ đó, tính nhất quán dữ liệu của người dùng được đảm bảo tuyệt đối, ngăn ngừa hoàn toàn tình trạng trải nghiệm phát video bị đứt gãy hoặc lỗi giao diện trên ứng dụng Client.
