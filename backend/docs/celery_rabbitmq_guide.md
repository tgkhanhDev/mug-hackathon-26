# Hướng Dẫn Sử Dụng Celery và RabbitMQ trong Dự Án GoTouchGrass

Tài liệu này hướng dẫn cách cấu hình, khởi chạy, giám sát và phát triển các tác vụ nền (background tasks) sử dụng Celery kết hợp với RabbitMQ Broker trong dự án.

---

## 1. Tổng Quan Kiến Trúc Celery & RabbitMQ

* **RabbitMQ (Broker)**: Đóng vai trò là hàng đợi chứa thông điệp (Message Broker). Khi Client gửi yêu cầu tải video, FastAPI sẽ đưa thông tin tác vụ vào RabbitMQ và phản hồi ngay lập tức.
* **Celery Worker**: Tiến trình chạy nền độc lập, liên tục lắng nghe RabbitMQ. Khi có tác vụ mới, Worker sẽ lấy ra và thực thi tác vụ đó (transcoding HLS, trích xuất thumbnail, dự đoán danh mục, sinh embedding).
* **Redis (Result Backend)**: Lưu trữ kết quả và trạng thái thực thi của các tác vụ Celery.

---

## 2. Cấu Hình Hệ Thống

### A. Docker Services (`docker-compose.yml`)
RabbitMQ và Redis được chạy cục bộ thông qua Docker Compose. File cấu hình đã định nghĩa sẵn các service:
* **RabbitMQ**: Cổng `5672` (kết nối AMQP) và `15672` (Trang quản trị UI).
* **Redis**: Cổng `6379`.

### B. Biến Môi Trường (`.env`)
Các biến cấu hình bắt buộc trong file `.env`:
```ini
# Celery Configuration
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### C. Định Nghĩa Celery App (`app/celery_app.py`)
Ứng dụng Celery được khởi tạo như sau:
```python
from celery import Celery
from app.config import settings

celery_app = Celery(
    "gotouchgrass",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"]  # Đăng ký module chứa task
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
```

---

## 3. Quy Trình Khởi Chạy

Để chạy toàn bộ hệ thống xử lý ngầm, thực hiện theo các bước sau trong môi trường local:

### Bước 1: Khởi động các Docker Container (RabbitMQ, Redis, MinIO)
```bash
docker compose up -d
```
*Xác nhận các container đang chạy bằng lệnh `docker ps`.*

### Bước 2: Kích hoạt Virtual Môi Trường và Cài đặt thư viện
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Bước 3: Chạy Celery Worker
Chạy lệnh sau tại thư mục gốc của backend:
```bash
.venv/bin/celery -A app.celery_app worker --loglevel=info
```
*Trong môi trường Windows (nếu có lỗi xảy ra), bạn có thể chạy thêm cờ `-P solo` hoặc `-P gevent`:*
```bash
celery -A app.celery_app worker --loglevel=info -P solo
```

### Bước 4: Chạy API Server (Uvicorn)
Trong một terminal khác:
```bash
.venv/bin/uvicorn app.main:app --port 8033 --reload
```

---

## 4. Cách Định Nghĩa và Gọi Celery Task

### A. Cách Định Nghĩa Task (`app/tasks.py`)
Mọi task của Celery phải được bọc trong decorator `@celery_app.task`.
Do Celery worker chạy đồng bộ theo mặc định nhưng backend sử dụng thư viện bất đồng bộ (`Motor`, `httpx`), chúng ta bọc logic bất đồng bộ bằng `asyncio.run()` bên trong task đồng bộ:

```python
from app.celery_app import celery_app
import asyncio

@celery_app.task(name="app.tasks.my_background_task")
def my_background_task(param1: str):
    # Khởi chạy hàm async trong event loop cô lập
    return asyncio.run(_my_async_logic(param1))

async def _my_async_logic(param1: str):
    # Logic xử lý bất đồng bộ ở đây (truy vấn DB, gọi API ngoài,...)
    pass
```

### B. Cách Gọi Task từ Controller/Service
Gọi task bất đồng bộ thông qua phương thức `.delay()` (viết tắt của `.apply_async()`). Lệnh gọi này sẽ đẩy thông điệp vào RabbitMQ rồi trả về ngay lập tức, không block API:

```python
from app.tasks import my_background_task

# Gọi tác vụ nền chạy ngầm
my_background_task.delay(param1="some_value")
```

---

## 5. Giám Sát và Quản Trị Hệ Thống (Monitoring)

### A. RabbitMQ Management Web UI
RabbitMQ cung cấp một giao diện quản trị rất trực quan:
* **Địa chỉ**: `http://localhost:15672`
* **Tài khoản**: `guest`
* **Mật khẩu**: `guest`

Tại đây bạn có thể:
* Xem danh sách hàng đợi (Queues), ví dụ queue `celery`.
* Giám sát số lượng message đang chờ xử lý (Ready) và đang được xử lý (Unacked).
* Xem tốc độ đẩy message (Publish) và tiêu thụ message (Deliver).

### B. Công cụ Flower (Giám sát Celery chuyên dụng)
Flower là một công cụ quản trị web thời gian thực cho Celery:
1. Cài đặt Flower:
   ```bash
   pip install flower
   ```
2. Khởi chạy Flower kết nối tới RabbitMQ:
   ```bash
   celery -A app.celery_app flower --port=5555
   ```
3. Truy cập địa chỉ `http://localhost:5555` để xem biểu đồ, danh sách worker đang hoạt động, lịch sử chạy các task và chi tiết các task bị lỗi.
