Mục tiêu cốt lõi của Phase 1 là: Cơ chế Feed hoạt động theo cả Trending và Vector Search.
DAY 1: Infrastructure & Data Seeding

Mục tiêu: Thiết lập môi trường, DB và đẩy dữ liệu mẫu vào hệ thống.

    Bạn 1 (Frontend): UI Cơ bản & Tracking Event

        Setup Project React (Vite) + Tailwind CSS.

        Dựng Layout dọc (Vertical Scroll) giống TikTok.

        Tạo Component VideoPlayer (hỗ trợ auto-play khi vào viewport).

        Quan trọng: Viết helper function để bắt các event: onView, onLike, onComment (chưa cần gọi API, chỉ cần console.log).

    Bạn 2 (Backend): FastAPI & MongoDB Atlas Setup

        Khởi tạo Project Python (FastAPI/Flask) + Kết nối MongoDB Atlas.

        Tạo Collection videos và users.

        Nhiệm vụ then chốt: Cấu hình Vector Search Index trên MongoDB Atlas (trường video_embedding).

        Viết API POST /videos để admin đẩy video mới vào hệ thống.

    Bạn 3 (Fullstack/Lead): Embedding & Seeding Data

        Viết script Python gọi OpenAI/HuggingFace để tạo vector cho 50-100 video mẫu (dựa trên tags, mô tả).

        Thiết kế công thức tính Trending Score trong MongoDB Aggregation: (view * 1 + like * 3 + comment * 5).

        Thống nhất API Contract (JSON format) giữa FE và BE.

DAY 2: Interaction & Vector Search Logic

Mục tiêu: Biến hành vi người dùng thành "Sở thích" (User Embedding).

    Bạn 1 (Frontend): Kết nối API & Infinite Scroll

        Tích hợp thư viện react-intersection-observer để check xem user đã xem video nào (view count).

        Kết nối API GET /feed để hiển thị video từ Backend.

        Gửi các tín hiệu tương tác (Like, Comment) về Backend realtime.

    Bạn 2 (Backend): Profile & Interaction API

        Viết API xử lý tương tác: Khi user Like/Watch, Backend phải lưu lại vào collection user_interactions.

        Nhiệm vụ khó: Viết logic cập nhật User_Vector_Embedding dựa trên các video họ đã Like (Trung bình cộng các vector video đã tương tác).

    Bạn 3 (Fullstack/Lead): Personalized Feed Engine

        Xây dựng Pipeline chính:

            Nếu user mới: Trả về Top 5 Trending (từ Day 1).

            Nếu user cũ: Dùng $vectorSearch của MongoDB để tìm video tương tự User_Vector_Embedding.

        Xử lý logic Chunking/Batching: Mỗi lần fetch chỉ lấy 3-5 clip.

DAY 3: Diversity & Phase 2 Integration

Mục tiêu: Chống Bias (bọc kén thông tin) và chuẩn bị dữ liệu cho Doomscroll Detection.

    Bạn 1 (Frontend): Telemetry & UX Polish

        Nhiệm vụ Phase 2: Bắt đầu track swipe_speed (tốc độ vuốt) và watch_duration (thời gian xem từng clip).

        Gửi kèm các thông số này trong mỗi request/log về server.

        Thêm hiệu ứng transition mượt mà khi chuyển clip.

    Bạn 2 (Backend): Anti-Bias & Reranking

        Cải tiến API Feed: Không chỉ trả về kết quả Vector tương đồng 100%.

        Inject "Wildcards": Trong 10 video trả về, chèn 2 video hoàn toàn ngẫu nhiên hoặc từ category khác để mở rộng sở thích cho user (Tránh bias).

        Lọc bỏ những video user đã xem trong session hiện tại.

    Bạn 3 (Fullstack/Lead): Doomscroll Logging & Final Test

        Thiết lập Time-series collection trên MongoDB để lưu trữ log hành vi (behavior logs) thô phục vụ cho việc tính Fatigue Score ở Phase 2.

        Kiểm tra hiệu năng truy vấn Vector Search (đảm bảo latency thấp).

        Demo luồng: Xem video -> Like -> Refresh -> Thấy video liên quan.

Kỹ thuật lưu ý cho Team:

    Python (Backend): Sử dụng motor (async driver cho MongoDB) để không bị block khi xử lý nhiều request stream.

    React (Frontend): Dùng React Query hoặc SWR để quản lý cache và fetch batch tiếp theo một cách âm thầm (prefetch).

    MongoDB Atlas: Luôn phải tạo Index trước khi thực hiện truy vấn $vectorSearch, nếu không API sẽ báo lỗi.

Với kế hoạch này, hết ngày 3 bạn sẽ có một bản clone TikTok "thông minh", biết tự học hỏi sở thích của người dùng và sẵn sàng để nhảy vào Phase 2 (Phát hiện brainrot).