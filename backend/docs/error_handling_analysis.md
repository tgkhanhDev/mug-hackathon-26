# Phân Tích Lỗi Hệ Thống Celery + RabbitMQ Và Giải Pháp Khắc Phục (Error Handling Analysis)

Tài liệu này phân tích các rủi ro, lỗi hệ thống (failures) có khả năng xảy ra đối với luồng xử lý video bất đồng bộ qua Celery/RabbitMQ và chi tiết các cơ chế bảo vệ, chịu lỗi đã được hiện thực hóa trong mã nguồn dự án.

---

## Bảng Tổng Quan Các Lỗi & Giải Pháp Khắc Phục

| Kịch Bản Lỗi (Failure Case) | Hậu Quả Nếu Không Xử Lý | Giải Pháp & Cơ Chế Khắc Phục Đã Triển Khai | Vị Trí Hiện Thực Trong Code |
| :--- | :--- | :--- | :--- |
| **RabbitMQ bị sập / Quá tải kết nối** | API Upload bị lỗi 500 hệ thống, Client không biết nguyên nhân và không upload được tiếp. | Bọc `try-except` quanh lệnh `.delay()`. Ghi nhận video status thành `"failed_queue"`, xóa tệp tạm trên đĩa, ném lỗi HTTP 503 Service Unavailable để client thử lại sau. | [video_controller.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/controllers/video_controller.py) |
| **Trùng lặp tác vụ (Task Duplication / Redelivery)** | Task chạy lại từ đầu gây transcoding đè lên đĩa/MinIO, tiêu tốn tài nguyên GPU/CPU và API OpenAI vô ích. | Kiểm tra **Idempotency** ngay khi bắt đầu task. Nếu trạng thái video trong DB đã là `"completed"`, worker ghi nhận và kết thúc sớm (early return). | [tasks.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/tasks.py) |
| **Worker bị crash vật lý (OOM-killed, mất điện)** | Video bị treo trạng thái `"processing"` vĩnh viễn, không bao giờ hiển thị trên Feed hay chuyển sang `"failed"`. | **Stuck Video Cleanup Job** định kỳ (mỗi 10 phút) chuyển toàn bộ video `"processing"` đã tạo quá 15 phút về trạng thái `"failed"`. | [scheduler.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/utils/scheduler.py) |
| **Treo tiến trình FFmpeg (Định dạng video lỗi nặng)** | Thao tác FFmpeg/FFprobe chạy vô hạn, block worker concurrency slots dẫn đến sập worker do hết tài nguyên đĩa/RAM. | Tích hợp **Timeout** cứng qua `asyncio.wait_for`. Tự động gọi `proc.kill()` và `await proc.wait()` để dọn dẹp tiến trình con ngay lập tức khi hết giờ. | [video_processor.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/utils/video_processor.py) |
| **Xung đột Event Loop của MongoDB (Async Motor)** | Gây lỗi `RuntimeError: Timeout context manager ...` hoặc sập tiến trình worker do tranh chấp loop. | Đóng kết nối MongoDB cũ, tạo Motor Client động cục bộ bên trong tiến trình con của Worker (`asyncio.run()`), và đóng kết nối ở block `finally`. | [tasks.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/tasks.py) |
| **Lỗi mạng khi tải lên MinIO/S3 hoặc gọi API HF/OpenAI** | Bản ghi video bị kẹt ở trạng thái `"processing"`, rò rỉ file tạm thời trên ổ đĩa của Worker. | Bọc toàn bộ logic trong block `try-except`. Khi xảy ra lỗi kết nối ngoại vi, tự động cập nhật status sang `"failed"`. Block `finally` đảm bảo xóa file và thư mục tạm. | [tasks.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/tasks.py) |

---

## Chi Tiết Các Cơ Chế Chống Chịu Lỗi (Robustness Mechanisms)

### 1. Cơ chế Chống Sập API Khi Broker Ngắt Kết Nối
Khi gọi `process_video_task.delay()`, thư viện Kombu (tầng truyền thông điệp của Celery) sẽ cố gắng tạo kết nối ổ cắm (socket) đến cổng `5672` của RabbitMQ. Nếu không kết nối được, nó sẽ ném ra lỗi `kombu.exceptions.OperationalError`.

**Giải pháp hiện thực:**
```python
try:
    process_video_task.delay(...)
except (kombu.exceptions.OperationalError, Exception) as e:
    logger.error(f"❌ Failed to enqueue video processing task to broker: {e}")
    # 1. Cập nhật trạng thái sang failed_queue để ghi nhận lỗi hệ thống hàng đợi
    await service._repo.update_one(created_video.id, {"status": "failed_queue", "updated_at": datetime.utcnow()})
    # 2. Xóa file raw vừa ghi vào /tmp để giải phóng đĩa
    if os.path.exists(temp_video_path):
        os.remove(temp_video_path)
    # 3. Trả về HTTP 503 Service Unavailable để báo cho Client
    raise HTTPException(status_code=503, detail="Video processing service queue is currently unavailable.")
```

### 2. Thiết Kế Idempotent Task (Chống trùng lặp)
Hàng đợi tin nhắn AMQP của RabbitMQ có cơ chế đảm bảo phân phối tin nhắn ít nhất một lần (At-least-once delivery). Nếu mạng bị chập chờn khi worker xử lý xong nhưng chưa kịp trả về ACK (Acknowledgement), RabbitMQ sẽ đẩy lại task đó vào queue cho worker khác chạy.

**Giải pháp hiện thực:**
```python
# Ngay khi bắt đầu tác vụ async chạy ngầm
repo = VideoRepository()
video_doc = await repo.find_by_id(video_id)
if video_doc and video_doc.get("status") == "completed":
    logger.info(f"⏭️ Video {video_id} already completed. Skipping processing task to prevent duplicate execution.")
    return  # Thoát sớm, block finally vẫn chạy để xóa file tạm nếu còn kẹt
```

### 3. Stuck Video Cleanup Scheduler (Dọn dẹp video bị treo)
Nếu máy chủ chứa worker bị mất điện đột ngột hoặc tiến trình worker bị OOM-killed (Out Of Memory) trong lúc đang chạy FFmpeg, bản ghi video trong MongoDB sẽ mãi mãi bị kẹt ở trạng thái `"processing"`. Khách hàng tải lên sẽ thấy video luôn ở trạng thái "đang xử lý".

**Giải pháp hiện thực:**
Một job chạy định kỳ (mỗi 10 phút) kiểm tra các bản ghi:
$$\text{created\_at} < (\text{now} - 15\text{ phút}) \quad \text{và} \quad \text{status} = \text{"processing"}$$
Các bản ghi thoả mãn điều kiện này sẽ được cập nhật trạng thái hàng loạt sang `"failed"` để người dùng biết quá trình xử lý đã bị lỗi và cho phép họ tải lại video khác.

### 4. Kiểm Soát Timeout Cho Tiến Trình Con (FFmpeg Timeout)
Lệnh FFmpeg có thể bị treo vô hạn nếu gặp các tệp tin video bị lỗi cấu trúc nén nặng (malformed / corrupt video). Điều này sẽ làm cạn kiệt số lượng worker tối đa có thể chạy song song (concurrency slots).

**Giải pháp hiện thực:**
Sử dụng `asyncio.wait_for` cho tiến trình con:
```python
proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
try:
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
except asyncio.TimeoutError:
    proc.kill()  # Buộc dừng tiến trình FFmpeg đang treo
    await proc.wait()  # Thu hồi tài nguyên tiến trình tránh tạo zombie process
    logger.error(f"ffmpeg execution timed out after {timeout_seconds}s")
    raise
```
*Thời gian timeout mặc định: 30 giây cho trích xuất metadata/thumbnail, 120 giây cho stream-copy HLS, và 300 giây cho transcode HLS.*
