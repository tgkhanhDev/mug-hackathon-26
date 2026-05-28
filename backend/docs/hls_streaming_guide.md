# Hướng dẫn Tích hợp HLS Stream (.m3u8), Cài đặt FFMPEG & Cấu hình MinIO

Tài liệu này hướng dẫn cách cài đặt công cụ xử lý video **FFMPEG / FFPROBE**, cách khởi chạy kho lưu trữ **MinIO** ở local và cách phát đường dẫn luồng `.m3u8` ở Frontend.

---

## 1. Hướng dẫn Cài đặt FFMPEG và FFPROBE

Backend yêu cầu cả `ffmpeg` và `ffprobe` phải được cài đặt trên hệ thống và có thể thực thi thông qua terminal (đường dẫn nằm trong biến môi trường `PATH`).

### Trên Linux (Ubuntu/Debian)
Mở terminal và chạy lệnh:
```bash
sudo apt update
sudo apt install ffmpeg
```
Sau khi cài đặt xong, hãy kiểm tra lại bằng lệnh:
```bash
ffmpeg -version
ffprobe -version
```

### Trên macOS
Nếu đã cài đặt `Homebrew`, chạy lệnh sau trong terminal:
```bash
brew install ffmpeg
```

### Trên Windows
1. Tải bản build FFMPEG cho Windows từ trang chủ [ffmpeg.org](https://ffmpeg.org/download.html) hoặc trực tiếp tại [gyan.dev](https://www.gyan.dev/ffmpeg/builds/).
2. Giải nén thư mục tải về (ví dụ giải nén vào ổ `C:\ffmpeg`).
3. Thêm đường dẫn thư mục `bin` (ví dụ `C:\ffmpeg\bin`) vào biến môi trường hệ thống `Path` (System Environment Variables).
4. Khởi động lại terminal (CMD/Powershell) và kiểm tra:
   ```cmd
   ffmpeg -version
   ```

---

## 2. Hướng dẫn Khởi chạy và Cấu hình MinIO Local

Hệ thống lưu trữ local được triển khai sử dụng **MinIO** thông qua Docker Compose.

### Cách 1: Khởi chạy bằng Docker Compose (Khuyên dùng)
Dự án đã tích hợp sẵn cấu hình trong file `docker-compose.yml`. Bạn chỉ cần khởi chạy bằng một lệnh duy nhất:
```bash
docker compose up -d minio
```
Lệnh này sẽ tải xuống image MinIO mới nhất và khởi chạy:
* **MinIO S3 API**: Cổng `9000` (dành cho client code kết nối).
* **MinIO Console**: Cổng `9001` (giao diện web quản lý).
* **Tên đăng nhập / Mật khẩu**: `minioadmin` / `minioadmin`.
* **Thư mục lưu trữ**: `minio_data/` tại local của bạn (được bỏ qua trong git).

### Cách 2: Khởi chạy MinIO bằng file chạy độc lập (Không dùng Docker)
Nếu không dùng Docker, bạn có thể tải bản cài đặt MinIO Server cho hệ điều hành của bạn từ trang chủ [min.io/download](https://min.io/download).
Sau đó khởi chạy bằng terminal:
```bash
# Ví dụ chạy trên Linux/macOS và lưu dữ liệu vào thư mục ./minio_data
minio server ./minio_data --console-address ":9001"
```

### Cách truy cập giao diện quản trị (Web UI Console)
1. Mở trình duyệt và truy cập: `http://localhost:9001`
2. Đăng nhập bằng tài khoản: `minioadmin` / `minioadmin`
3. Tại đây bạn có thể theo dõi danh sách buckets, các folder video (`videos/{uuid}/`) và kiểm tra trực tiếp các phân đoạn video `.m4s` cũng như ảnh thumbnail.

---

## 3. Cơ chế Hoạt động của HLS với Trình duyệt

Khi Backend xử lý xong video và trả về đường dẫn danh sách phát:
`http://localhost:9000/gotouchgrass-media/videos/{video_id}/playlist.m3u8`

Trình phát video (video player) ở client sẽ hoạt động như sau:
1. **Tải file Playlist**: Trình phát tải file `playlist.m3u8` về để phân tích. File này chứa danh sách các phân đoạn video nhỏ (chỉ mục thời gian, tên file `.m4s` và file khởi tạo `init.mp4`).
2. **Tải phân đoạn tự động**: Dựa vào nội dung trong playlist, trình phát sẽ tự động tải file khởi tạo `init.mp4` (để thiết lập codec) và các phân đoạn `segment_000.m4s`, `segment_001.m4s`... tương ứng với mốc thời gian xem của người dùng.
3. **Giải quyết đường dẫn tương đối**: Do các phân đoạn trong playlist được định nghĩa bằng đường dẫn tương đối (ví dụ: `init.mp4` thay vì toàn bộ URL), trình phát sẽ tự động ghép nối đường dẫn gốc của playlist (`http://localhost:9000/gotouchgrass-media/videos/{video_id}/`) với tên phân đoạn để gửi request tải dữ liệu.

---

## 4. Hướng dẫn Phát Video trên Trình duyệt (Frontend)

Hầu hết các trình duyệt di động (Safari iOS, Chrome trên Android) hỗ trợ HLS nguyên bản (native). Tuy nhiên, các trình duyệt máy tính (Chrome, Firefox, Edge) yêu cầu sử dụng thư viện JavaScript hỗ trợ giải mã.

Dưới đây là 2 cách tích hợp phổ biến nhất:

### Cách 1: Sử dụng thư viện thuần `Hls.js` (Khuyên dùng - nhẹ và hiệu quả)

`Hls.js` là thư viện JavaScript dùng để giải mã luồng phát HLS thông qua Media Source Extensions (MSE) của HTML5.

```html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>HLS Stream Player</title>
    <!-- Nhúng thư viện Hls.js từ CDN -->
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        .player-container {
            max-width: 640px;
            margin: 20px auto;
        }
        video {
            width: 100%;
            border-radius: 8px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>

<div class="player-container">
    <h2>Trình phát Video HLS 🌿</h2>
    <video id="video" controls autoplay muted></video>
</div>

<script>
    const video = document.getElementById('video');
    // Đường dẫn m3u8 lấy từ API backend của bạn
    const videoSrc = 'http://localhost:9000/gotouchgrass-media/videos/{video_id}/playlist.m3u8';

    if (Hls.isSupported()) {
        const hls = new Hls();
        hls.loadSource(videoSrc);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, function() {
            video.play();
        });
    }
    // Dành cho Safari hoặc iOS Chrome hỗ trợ HLS native trực tiếp
    else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = videoSrc;
        video.addEventListener('loadedmetadata', function() {
            video.play();
        });
    }
</script>

</body>
</html>
```

---

### Cách 2: Sử dụng `Video.js` (Phù hợp nếu cần giao diện đẹp & nhiều plugin)

`Video.js` hỗ trợ sẵn HLS và cung cấp một giao diện phát video đồng bộ, đẹp mắt trên mọi thiết bị.

```html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Video.js HLS Player</title>
    <!-- Nhúng CSS và JS của Video.js -->
    <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" />
    <script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
    <style>
        .player-container {
            max-width: 640px;
            margin: 20px auto;
        }
    </style>
</head>
<body>

<div class="player-container">
    <h2>Video.js Player 🐰</h2>
    <video
        id="my-video"
        class="video-js vjs-default-skin vjs-big-play-centered"
        controls
        preload="auto"
        width="640"
        height="360"
        data-setup='{}'>
        <!-- Điền URL m3u8 vào đây kèm type tương ứng -->
        <source src="http://localhost:9000/gotouchgrass-media/videos/{video_id}/playlist.m3u8" type="application/x-mpegURL">
        <p class="vjs-no-js">
            Để xem video này, vui lòng kích hoạt JavaScript và nâng cấp trình duyệt.
        </p>
    </video>
</div>

</body>
</html>
```

---

## 5. Lưu ý về CORS (Cross-Origin Resource Sharing)

Vì các phân đoạn video được lưu trên máy chủ MinIO chạy độc lập tại cổng `9000`, trong khi frontend chạy trên cổng khác (ví dụ: `http://localhost:5173` hoặc `http://localhost:3000`):

1. **MinIO CORS**: MinIO cần cho phép các request CORS từ Origin của frontend để trình duyệt tải các file `.m3u8` và `.m4s`.
2. **Cấu hình Policy**: Hiện tại trong file `minio_client.py`, chúng ta đã tạo bucket với policy `public read-only` cho phép bất cứ ai cũng có thể đọc.
3. **CORS trên Local**: Mặc định, máy chủ MinIO khi khởi chạy bằng Docker Compose đã bật sẵn CORS mở cho phép các kết nối HTTP GET. Nếu gặp lỗi `Access-Control-Allow-Origin` ở frontend khi kết nối với MinIO, bạn có thể thiết lập biến môi trường CORS cho container MinIO trong file `docker-compose.yml` (hoặc cấu hình CORS trực tiếp trên MinIO Admin Console).
