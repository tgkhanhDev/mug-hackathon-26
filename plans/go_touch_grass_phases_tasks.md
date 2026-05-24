# 🚀 GoTouchGrass: Master Tracking & Task Assignment

Với vai trò Project Manager, dưới đây là tài liệu quản lý tiến độ (Phases Tracking) và phân chia công việc (Task Breakdown) cho nhóm 3 người. Tài liệu này được thiết kế dựa trên đúng các Phase kỹ thuật mà đội đã vạch ra, kết hợp với kế hoạch 3 ngày Hackathon.

---

## 👥 Nhóm phát triển (3 Thành viên)
- **Member 1 (BE - Backend Dev):** Phụ trách Core Logic, Python, FastAPI, Xử lý Vector, Recommendation API.
- **Member 2 (FE - Frontend Dev):** Phụ trách React, Giao diện UX/UI, Component, Xử lý Tracking hành vi (Swipe, Duration).
- **Member 3 (FS - Fullstack/Lead):** Phụ trách System Design, MongoDB Atlas, Aggregation Pipeline, Pipeline Testing, Deploy & Kịch bản Demo.

---

## 🎯 PHASES TRACKING (Lộ trình nghiệp vụ)

### PHASE 1 — Normal Personalized Feed (The Baseline)
**Mục tiêu:** Xây dựng hệ thống lõi hoạt động mượt mà giống TikTok, tập trung vào độ cá nhân hóa.
* **Hành vi theo dõi (User Signals):** Like, watch, replay, comment, skip.
* **Luồng xử lý:**
  * Hệ thống khởi tạo và cập nhật `User Embedding Vector` liên tục.
  * *Ví dụ sở thích:* dark humor, coding meme, football edits, fast-cut videos.
  * Sử dụng **MongoDB Vector Search** để tìm các video tương tự vector người dùng (find similar videos).
* **Thuật toán xếp hạng (Scoring & Trending):**
  * `Xu hướng = (view * 1 + reaction * 3 + cmt * 5) & (Tốc độ tăng trưởng)`
  * Trộn điểm Similarity của Vector và Điểm Xu Hướng.
* **Chiến lược Load Feed & Data:**
  * Fetch top 5 video trong lần lướt đầu tiên để xử lý cold-start.
  * Các lần cuộn tiếp theo: fetch mỗi batch 3 clips. (Tích hợp chunk AWS stream để load video tối ưu).
  * *Dữ liệu mẫu:* 100 clips, 3 tags mỗi clip. Khi user onboard sẽ chọn 2 interested tags.
  * *Rủi ro cần tránh:* Ngăn ngừa hệ thống bị "bias" (chỉ gợi ý 1 topic duy nhất).

### PHASE 2 — Doomscroll Detection (The Core Problem)
**Mục tiêu:** Nhận diện mức độ quá tải cảm xúc theo thời gian thực trong một phiên lướt.
* **Tracking trong session (Tracking Signals):**
  | Signal (Tín hiệu) | Ý nghĩa hành vi |
  | :--- | :--- |
  | `swipe speed` tăng mạnh | Fatigue (Mệt mỏi, mất kiên nhẫn) |
  | `watch duration` giảm | Overstimulation (Bị kích thích quá mức) |
  | `interaction` giảm dần | Passive scrolling (Lướt thụ động, vô thức) |
  | `repetitive topics` liên tục | Emotional saturation (Bão hòa cảm xúc) |
  | `session` quá dài | Compulsive consumption (Tiêu thụ cưỡng chế) |
* **Xử lý MongoDB:** Sử dụng **Aggregation Pipeline** và Time-series logs để tổng hợp và tính toán chỉ số `Fatigue Score` (Ví dụ: Hệ thống phát hiện Fatigue Score = 82/100).

### PHASE 3 — Mindful Feed Injection (The Intervention)
* **Khi Fatigue Score tăng cao:**
  * Recommendation Engine **KHÔNG** dừng việc cá nhân hóa, mà thay đổi chiến lược:
    1. **Re-rank feed:** Sắp xếp lại thứ tự ưu tiên video.
    2. **Diversify content:** Tăng cường độ đa dạng của nội dung.
    3. **Giảm dopamine intensity:** Cắt giảm những nội dung giật gân (high intensity).
* **Ví dụ chuyển đổi (Transition in action):**
  * *Before (Dopamine Heavy):* ragebait → sigma edit → relationship drama → controversy clips.
  * *After (Palette Cleanser):* slow travel → night rain → educational mini-doc → calming piano. 🔥

---

## 🛠️ TASK BREAKDOWN (Chiến lược 3 Ngày Hackathon)

### 🟢 DAY 1: Setup, Database, Seed Data & Embedding Pipeline
* **BE (Backend Dev):**
  * Khởi tạo dự án FastAPI, cài đặt `motor` (MongoDB async) & `dotenv`.
  * Khởi tạo 3 collections (`videos`, `users`, `interactions`) theo schema đã chốt.
  * Viết script giả lập data (Seed script) cho 100 video (mỗi video có 3 tags).
  * Gọi API OpenAI `text-embedding-3-small` để nhúng (embed) vector cho video (Title + Tags).
  * Lên Atlas UI tạo **Vector Search Index** (field `embedding`, 1536d, cosine).
* **FE (Frontend Dev):**
  * Setup React/Next.js + TailwindCSS (cấu trúc thư mục `/feed`, `/hooks`, `/api`).
  * Xây dựng `VideoCard` component (gồm title, tags, category, thumbnail/video placeholder).
  * Viết hook `useFeed()` gọi API GET `/feed/{user_id}` kèm UI loading state.
  * Tạo `InteractionTracker` (bắt sự kiện `onClick` cho Like/Skip, `onView` dùng Intersection Observer để đo thời gian xem).
* **FS (Fullstack / Lead):**
  * Thiết kế **API Contract** (Request/Response JSON) chốt chuẩn giao tiếp cho BE và FE.
  * Khởi tạo MongoDB Atlas Cluster, tạo DB User, cấu hình Whitelist IP.
  * Viết User Seed script (Khởi tạo 5 users mẫu với `interest_vector` bám theo 2 tags).
  * Khởi tạo và test thử **Aggregation Pipeline** nháp dùng `$vectorSearch + $project`.

### 🟡 DAY 2: Recommendation Engine, Tracking API & User Vector Update
* **BE (Backend Dev):**
  * Hoàn thiện API `GET /feed/{user_id}`: chạy `$vectorSearch` với vector của user, kết hợp tính công thức điểm Xu Hướng. Fetch top 5 lần đầu, batch 3 clips cho lần sau (Tích hợp AWS Stream chunk nếu kịp).
  * Viết API `POST /users/{id}/interaction` lưu log tương tác (type, watch_time, timestamp).
  * Viết logic **Update User Embedding**: Tính trung bình có trọng số (weighted average) để thay đổi vector user sau các tương tác mới.
  * Viết job tính `trending_score` định kỳ cho video.
* **FE (Frontend Dev):**
  * Kết nối UI với API thật (Loại bỏ mock data).
  * Implement tính năng **Scroll-to-load** (cuộn gần cuối thì fetch tiếp 3 videos).
  * Liên tục gửi interaction events (`like`, `skip`, thời gian xem) mỗi khi user xem xong 1 clip.
  * Code UI cho Debug Mode: Hiển thị badge `Similarity Score` / `Fatigue Score` trên màn hình để dễ thuyết trình.
* **FS (Fullstack / Lead):**
  * Hoàn thiện Aggregation Pipeline lõi: `$vectorSearch` + `$addFields` (Score tổng) + `$sort`.
  * Viết Test Script: giả lập 20 lượt lướt để xem feed có thay đổi đúng theo sở thích hay không (Chứng minh Phase 1 hoạt động tốt).
  * Lên bản nháp Schema cho Phase 2 (`feed_sessions` để lưu `brainrot_score` hay `fatigue_score`).
  * Viết tài liệu mô tả Aggregation Pipeline để cả nhóm nắm luồng.

### 🔴 DAY 3: Polish UI, Phase 2+3 Foundation & Demo Preparation
* **BE (Backend Dev):**
  * Tối ưu cache vector cho user (Redis hoặc in-memory TTL 5p).
  * Thêm các field hứng data cho Phase 2: `swipe_speed`, `session_duration` vào API interactions.
  * Cài đặt API trả về `Fatigue Score` (Có thể dùng stub hoặc Aggregation Pipeline đơn giản đếm số video liên tiếp có độ tương tác thụ động).
  * Viết API Fallback `GET /videos/trending` dùng khi Cold-start.
* **FE (Frontend Dev):**
  * UI **Wellbeing Indicator Bar**: Một thanh bar đổi màu sắc hoặc phần trăm cảnh báo khi user lướt quá đà (Fatigue score tăng).
  * Xử lý luồng Cold Start: Giao diện Onboarding cho user mới chọn 2 tags ban đầu.
  * Bắt chỉ số `swipe_speed` (tốc độ vuốt tính bằng giây/px) và gửi kèm tracking event.
  * Trau chuốt UI/UX (Skeleton, error state, hiệu ứng chuyển video mượt).
* **FS (Fullstack / Lead):**
  * Chạy End-to-End (E2E) testing: Giả lập 1 phiên session dài, ép cho Fatigue Score tăng để xem Feed Phase 3 có kích hoạt (Palette Cleanser) hay không.
  * Viết spec mô tả rõ thuật toán Phase 2 (Công thức điểm Fatigue) để chuẩn bị pitch với Ban Giám Khảo.
  * **Deploy hệ thống:** Đưa BE lên Railway/Render, FE lên Vercel.
  * Chuẩn bị kịch bản Demo trực tiếp: Chạy song song màn hình FE và màn hình MongoDB Atlas log để chứng minh hệ thống real-time.
