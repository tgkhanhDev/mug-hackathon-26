# Hướng dẫn Xử lý và Khắc phục Lỗi Hệ thống (FFmpeg, MinIO & HLS)

Tài liệu này tổng hợp toàn bộ các tình huống lỗi (failures) có thể xảy ra trong hệ thống khi sử dụng **FFmpeg/FFprobe**, **MinIO local**, **HLS Stream** và mô tả chi tiết cách xử lý hiện tại của mã nguồn để đảm bảo hệ thống hoạt động ổn định, không bị sập (crash).

---

## 1. Bảng Tổng hợp Tình huống lỗi và Cách xử lý của Code

| Thành phần | Tình huống lỗi (Failure Scenario) | Khả năng xảy ra | Cách xử lý trong code hiện tại | Trạng thái/Khắc phục |
| :--- | :--- | :--- | :--- | :--- |
| **FFmpeg** | FFMPEG/FFPROBE chưa được cài đặt trên máy chủ. | Thấp (local đã có) | Bọc trong khối `try...except` tại `video_processor.py`. Ghi nhận log warning và trả về giá trị mặc định (duration = 0, resolution = 0x0) hoặc `False`. Không làm sập ứng dụng. | Cần đảm bảo cài đặt trên môi trường deploy mới. |
| **FFmpeg** | File video tải lên bị lỗi hoặc sai định dạng (ví dụ: file text đổi đuôi `.mp4`). | Trung bình | `ffprobe` và `ffmpeg` báo lỗi (exit code != 0). Code bắt sự kiện này, log warning cụ thể và bỏ qua việc sinh thumbnail/metadata một cách an toàn. | API vẫn tạo video thành công nhưng không có metadata. |
| **FFmpeg** | Video tải lên quá ngắn (dưới 1 giây) khiến lệnh cắt thumbnail tại mốc `1.0s` bị lỗi. | Trung bình | `video_controller.py` tự động tính toán thời lượng: Nếu video dưới 1s, tham số seek ảnh thumbnail sẽ là `duration / 2.0` (cắt ở giữa video). | Tự động thích ứng, lệnh cắt luôn thành công. |
| **FFmpeg** | Lệnh chia nhỏ video HLS chế độ sao chép nhanh (`-c copy`) bị lỗi do codec gốc không tương thích. | Thấp đến Trung bình | Bắt lỗi lệnh copy, ghi log warning và kích hoạt chế độ dự phòng (fallback) tự động transcode video về chuẩn `libx264` (H.264) và `aac` (AAC). | Đảm bảo video HLS xuất ra tương thích với mọi trình duyệt. |
| **Hệ thống** | Ổ cứng server bị đầy (Disk Exhaustion) do tích tụ file video tạm hoặc folder chunk tạm. | Thấp đến Trung bình | Toàn bộ quá trình tạo file tạm/folder HLS tạm đều nằm trong khối `try...finally` ở `video_controller.py`. Lệnh dọn dẹp file (`os.remove`, `shutil.rmtree`) bắt buộc chạy ở `finally`. | Không bị rác ổ cứng kể cả khi API xảy ra lỗi giữa chừng. |
| **MinIO** | Dịch vụ MinIO bị dừng (Container bị tắt/sập). | Thấp đến Trung bình | Trình duyệt ném ngoại lệ kết nối. Exception được bắt ở controller, dọn dẹp file tạm ở `finally` và trả về lỗi `500 Internal Server Error` sạch sẽ cho client. | Hệ thống backend không bị treo. Cần restart MinIO container. |
| **MinIO** | Bucket `gotouchgrass-media` bị xóa thủ công từ admin. | Thấp | Trong `minio_client.py`, hàm `get_minio_client` tự động kiểm tra sự tồn tại của bucket bằng `head_bucket`. Nếu thiếu, nó tự động tạo mới lại bucket và cấu hình lại policy `public-read`. | Tự động phục hồi bucket trong quá trình chạy. |
| **MinIO** | Trùng tên file (Key Collision) khi lưu trữ các video và phân đoạn. | Rất thấp (gần như = 0) | Mỗi video/thư mục HLS được gán một chuỗi định danh ngẫu nhiên `uuid.uuid4()` làm prefix trên MinIO (ví dụ: `videos/{uuid}/playlist.m3u8`). | Triệt tiêu khả năng trùng lặp hoặc ghi đè file chéo. |

---

## 2. Chi tiết Kỹ thuật Xử lý Lỗi trong Mã nguồn

### 2.1. Cơ chế Tự động Phục hồi Bucket (MinIO)
Mã nguồn trong [minio_client.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/utils/minio_client.py) tự kiểm tra và phục hồi khi bucket bị mất:
```python
try:
    minio_client.head_bucket(Bucket=bucket_name)
    logger.info(f"MinIO Bucket '{bucket_name}' already exists.")
except Exception:
    logger.info(f"MinIO Bucket '{bucket_name}' does not exist. Creating it...")
    minio_client.create_bucket(Bucket=bucket_name)
    # Tự cấu hình lại quyền đọc public
    minio_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
```

### 2.2. Cơ chế Fallback Codec khi chia nhỏ HLS
Mã nguồn trong [video_processor.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/utils/video_processor.py) thực hiện phân đoạn nhanh, nếu lỗi sẽ tự động chuyển sang chế độ transcode:
```python
# Lệnh 1: Copy luồng dữ liệu (siêu nhanh)
proc = await asyncio.create_subprocess_exec(*cmd_copy, ...)
stdout, stderr = await proc.communicate()

if proc.returncode == 0:
    return True
else:
    # Lệnh 2: Fallback sang transcoding H.264/AAC
    proc = await asyncio.create_subprocess_exec(*cmd_transcode, ...)
    ...
```

### 2.3. Đảm bảo dọn dẹp file tạm (Local Disk Security)
Mã nguồn trong [video_controller.py](file:///home/andev03/Desktop/programming/hackathon/backend/app/controllers/video_controller.py) bọc luồng ghi file tạm và folder tạm trong cấu trúc `try...finally`:
```python
try:
    # Xử lý video, chia nhỏ HLS, upload lên MinIO...
    ...
finally:
    # Khối code này luôn luôn chạy kể cả khi có exception xảy ra
    if temp_video_path and os.path.exists(temp_video_path):
        os.remove(temp_video_path)
    if temp_hls_dir and os.path.exists(temp_hls_dir):
        shutil.rmtree(temp_hls_dir)
```

---

## 3. Khuyến nghị và Khắc phục Sự cố khi Deploy

1. **Khi triển khai lên Production (Dockerized Backend)**: 
   - Đảm bảo trong `Dockerfile` của backend có cài đặt gói `ffmpeg` và `ffprobe`.
     *Ví dụ trong Dockerfile base Debian/Ubuntu:*
     ```dockerfile
     RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
     ```
2. **Khi gặp lỗi CORS ở trình duyệt**:
   - MinIO mặc định cho phép các request CORS cơ bản trên local. Nếu frontend của bạn bị chặn CORS khi fetch file `.m3u8` hoặc `.m4s`, hãy vào giao diện **MinIO Console (http://localhost:9001)** -> Chọn **Configuration** -> Cấu hình các headers và origins cho phù hợp.
3. **Giới hạn kích thước tải lên (Upload Max Body Size)**:
   - Hãy cấu hình giới hạn kích thước file upload ở Nginx/API Gateway (ví dụ: `client_max_body_size 100M;`) để tránh việc client cố tình upload các file video quá lớn gây nghẽn băng thông và đầy bộ nhớ đệm server.
