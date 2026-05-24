# 🔄 Gotouchgrass End-to-End Interaction & Recommendation Flow

Tài liệu này giải thích chi tiết luồng xử lý dữ liệu từ đầu đến cuối (End-to-End Lifecycle Flow) của hệ thống Gotouchgrass: từ khi người dùng đăng ký mới, khởi tạo phiên, nhận bảng tin cá nhân hóa, ghi nhận hành vi thụ động (Fatigue calculation), đến tương tác chủ động (EMA Vector Update) và thay đổi trạng thái bảo vệ sức khỏe (Wellbeing filtering).

---



## 📝 Giải Thích Từng Bước Luồng Đi (Step-by-Step Flow)

### Bước 1: Đăng ký & Onboarding người dùng
1. Người dùng mở ứng dụng lần đầu và chọn các thẻ sở thích (ví dụ: `music`, `calming`).
2. Client gửi `POST /api/v1/users` lên Server.
3. Server truy xuất danh sách video mẫu tương ứng với các thẻ này từ collection `videos`.
4. Nếu tìm thấy video, Server lấy trung bình cộng mảng `embedding` của chúng. Nếu không, Server gọi Hugging Face API sinh vector từ văn bản `"User interests: music, calming"`.
5. **Điểm quan trọng:** Vector kết quả được **L2-normalize** (độ dài bằng 1) và lưu vào `interest_vector` của người dùng.

### Bước 2: Tạo phiên xem bảng tin
1. Khi người dùng vào trang bảng tin chính, client gọi `POST /api/v1/sessions`.
2. Hệ thống khởi tạo một tài liệu trong collection `feed_sessions` với trạng thái mặc định:
   * `fatigue_score`: `0.0`
   * `adaptive_state`: `"normal"`
   * `high_intensity_count`: `0`
   * `low_intensity_count`: `0`
3. Trả về `session_id` để client đính kèm vào các log hành động tiếp theo.

### Bước 3: Gợi ý bảng tin Wellbeing-Aware & Khám phá chủ đề mới
1. Client gọi `GET /api/v1/feed/{user_id}` để lấy video.
2. Server tìm phiên hoạt động của người dùng để đọc trạng thái mệt mỏi (`adaptive_state`):
   * Nếu ở trạng thái nguy kịch **`exhausted`**: Server ép buộc bộ lọc `{"intensity_level": "low"}`.
   * Nếu ở trạng thái cảnh báo **`warning`**: Server ép lọc `{"intensity_level": {"$in": ["low", "medium"]}}`.
   * Nếu **`normal`**: Không lọc độ kích thích.
3. Server thực hiện truy vấn **Atlas Vector Search (`$vectorSearch`)** so khớp vector sở thích của user với vector nội dung video, kết hợp lọc theo trạng thái trên.
4. **Phá vỡ bong bóng lọc (Exploration):** Để tránh trường hợp người dùng bị kẹt vào một chủ đề duy nhất (không đổi hướng được vector sở thích do hệ thống chỉ gợi ý một loại nội dung), hệ thống lấy thêm 1 video đang thịnh hành (Trending Video) thuộc chủ đề khác và chèn vào vị trí cuối của danh sách trả về.
5. Server gửi danh sách video đã được tối ưu hóa cho sức khỏe tinh thần về client.

### Bước 4: Đo lường mức độ mệt mỏi tinh thần thụ động (Fatigue Tracking)
1. Khi người dùng lướt qua một video, client gửi hành vi thô về `POST /api/v1/behavior-logs` (gồm thời gian xem, tốc độ vuốt, chủ đề).
2. Server lưu lại log này trong collection time-series `behavior_logs`.
3. Server chạy tác vụ nền để tính toán lại điểm mệt mỏi:
   * Lấy danh sách 10 video xem gần nhất trong phiên.
   * Tính điểm phạt: xem quá nhanh (<2 giây phạt 30), vuốt quá nhanh (>800 px/s phạt 20), không tương tác (phạt 15), xem lặp chủ đề (phạt 15-25).
   * Cộng thêm điểm phạt từ lượng dopamine hấp thụ (tỷ lệ video cường độ cao đã xem).
   * Cập nhật điểm mệt mỏi (`fatigue_score`) và tự động chuyển đổi trạng thái (`adaptive_state` chuyển sang `warning` hoặc `exhausted` nếu điểm vượt ngưỡng 40 hoặc 70).

### Bước 5: Cập nhật Vector sở thích thời gian thực & Cập nhật xu hướng
1. Khi người dùng thực hiện một hành động rõ ràng (Thích, Viết bình luận, Xem lại nhiều lần, hoặc Bỏ qua), client gọi `POST /api/v1/interactions`.
2. Hệ thống thực hiện đồng thời các công việc sau để tối ưu hiệu năng:
   * **Ghi log:** Lưu tương tác vào collection `interactions`.
   * **Cập nhật bộ đếm video:** Tăng số `like_count`, `view_count`, `comment_count` của video đó trong MongoDB và cập nhật trực tiếp điểm xu hướng `trending_score` của video đó.
   * **Cập nhật sở thích (EMA):** 
     $$\vec{V}_{new} = \text{L2\_Normalize}(0.85 \times \vec{V}_{current} + 0.15 \times W_{action} \times \vec{V}_{video})$$
     *Trọng số $W_{action}$ là dương khi thích/replay (kéo vector về gần video đó), và âm ($-0.3$) khi bỏ qua (đẩy vector ra xa video đó).*
   * **Real-time broadcast:** Gửi bản tin WebSocket tới tất cả những người dùng khác đang xem video này để cập nhật trực tiếp số tim/lượt xem trên giao diện.
