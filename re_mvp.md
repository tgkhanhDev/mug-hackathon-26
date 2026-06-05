# 🚀 MVP PITCH 10 PHÚT - GoTouchGrass: Mindful Recommendation Engine
## Triển khai Recommendation Engine với MongoDB Vector Search + Collaborative Filtering

---

## 📊 GIAI ĐOẠN 1: HOOK - DỮ LIỆU & SỐ LIỆU THÚC ĐẨY

### Thực trạng thị trường:
* **53% người dùng Gen Z** thường xuyên doomscroll — tỷ lệ cao nhất trong tất cả các thế hệ (Nguồn: Morning Consult, 2024).
* **Gần một nửa Gen Z** đã được chẩn đoán chính thức về sức khỏe tâm thần, và **hơn 1/3** tin rằng họ đang có vấn đề chưa được chẩn đoán (Nguồn: Harmony Healthcare IT, 5/2025).
* **Trung bình 7 giờ 43 phút/ngày** Gen Z dùng smartphone; riêng TikTok chiếm 95 phút — gấp hơn 3 lần mức khuyến nghị về sức khỏe kỹ thuật số (Nguồn: SQ Magazine, 2026).
* **72% người sáng tạo nội dung nhỏ lẻ** rất khó tiếp cận người dùng vì các hệ thống hiện tại chỉ ưu tiên phân phối các nội dung có tính kích thích cao (high-engagement/dopamine-heavy).

### Nguyên nhân gốc rễ & Vấn đề kinh doanh:
Các hệ thống gợi ý hiện tại **chỉ tối ưu một metric duy nhất: Watch Time & Retention**. Chúng hoàn toàn phớt lờ sức khỏe kỹ thuật số (Digital Wellbeing) của người dùng. Hệ quả là người dùng bị kiệt sức (burnout) dẫn đến tỷ lệ rời bỏ (churn rate) tăng, đồng thời các nhà sáng tạo nội dung tích cực bị chôn vùi khiến hệ sinh thái mất đi tính đa dạng.

---

## 💼 GIAI ĐOẠN 2: BUSINESS REQUIREMENT - PHÁT BIỂU VẤN ĐỀ

**The problem of:** Hệ thống gợi ý video ngắn truyền thống đang nhốt người dùng vào những vòng lặp Doomscrolling vô tận. Chúng không có khả năng phát hiện sự mệt mỏi của người dùng để điều chỉnh luồng nội dung một cách linh hoạt.

**Affects:** Gen Z, học sinh, sinh viên, nhân viên văn phòng và chính các nền tảng MXH đang muốn giữ chân người dùng một cách bền vững mà không phải hy sinh tính cá nhân hóa.

**The impact of which is:**
Sự suy giảm năng suất trầm trọng, khẩu vị nội dung bị "suy thoái" do quen với dopamine cường độ cao, và sự chìm nghỉm của các nhà sáng tạo nội dung mang tính giáo dục, chữa lành.

**Yêu cầu nghiệp vụ (Requirements) cho một giải pháp thành công:**
1. **Personalization:** Vẫn phải cá nhân hóa mạnh mẽ dựa trên hành vi và interest embeddings.
2. **Fatigue Detection:** Phát hiện doomscrolling theo thời gian thực qua tốc độ lướt, thời gian xem, và tần suất lặp lại.
3. **Adaptive Reranking:** Khả năng "bẻ lái" luồng nội dung một cách mượt mà sang các chủ đề thanh lọc (palette cleanser) khi người dùng chạm ngưỡng mệt mỏi.
4. **Performance:** Tốc độ phản hồi và điều chỉnh feed phải `< 300ms`.

---

## 👁️ GIAI ĐOẠN 3: PRODUCT VISION - TẦM NHÌN SẢN PHẨM

*Thay vì nhốt người dùng trong một ma trận nội dung ảo, chúng tôi muốn tạo ra một hệ thống biết điểm dừng.*

* **For (Dành cho):** Gen Z, học sinh, sinh viên và dân văn phòng thường xuyên sử dụng các nền tảng video ngắn.
* **Who (Những người):** Đang vô thức bị cuốn vào vòng lặp doomscrolling, cảm thấy kiệt quệ về mặt tinh thần sau mỗi phiên lướt web kéo dài nhưng không dứt ra được.
* **The product name (Tên sản phẩm):** **GoTouchGrass**
* **Is a (Là một):** Wellbeing-aware AI Recommendation Engine (Hệ thống gợi ý AI nhận thức sức khỏe tinh thần).
* **That (Với khả năng):** Cá nhân hóa nguồn cấp dữ liệu cực kỳ thông minh, đồng thời phát hiện ngưỡng mệt mỏi (Fatigue Score) theo thời gian thực để tự động cân bằng giữa nội dung giải trí cường độ cao và nội dung chữa lành.
* **Unlike (Khác với):** TikTok, Facebook hay các nền tảng truyền thống – những cỗ máy chỉ chực chờ vắt kiệt sự chú ý của người dùng bằng dopamine và tối ưu hóa duy nhất cho *Watch Time*.
* **Our product (Sản phẩm của chúng tôi):** Được xây dựng dựa trên cốt lõi là không chỉ tối ưu engagement, mà còn bảo vệ sức khỏe kỹ thuật số của bạn. GoTouchGrass vừa là một thuật toán tinh tế, vừa là một lời nhắc nhở nửa đùa nửa thật: **đã đến lúc ra ngoài trời và xem cỏ màu gì rồi đấy**. Khi nhận thấy bạn lướt quá nhanh và quá lâu, hệ thống không bắt ép bạn tắt app, mà mượt mà chuyển hướng sang các nội dung êm dịu, giảm nhịp độ, "chữa lành" tâm trí và từ từ đưa bạn trở về trạng thái cân bằng.

---

## 🔧 GIAI ĐOẠN 4: HOW WE RESOLVE - TRIỂN KHAI KỸ THUẬT VỚI MONGODB

### Architecture Overview:
Sức mạnh của hệ thống nằm ở lõi **MongoDB Aggregation Pipeline** kết hợp cùng **Atlas Vector Search**, đảm bảo độ trễ siêu thấp dù phải tính toán nhiều tham số realtime.

```text
┌─────────────────┐
│   Frontend UI   │ (Mô phỏng Short-form video feed)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Behavioral Tracking Engine         │ (Theo dõi realtime: Swipes, Watch Duration, Replay)
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│         CORE RECOMMENDATION ENGINE (MongoDB)               │
├─────────────────────────────────────────────────────────────┤
│ 1. Vector Search (Tính cá nhân hóa)                        │
│    → Atlas Vector Search đối chiếu user interest vectors   │
│                                                             │
│ 2. Collaborative Filtering (Độ đa dạng)                    │
│    → Aggregation Pipeline ($group, $lookup) tìm hành vi    │
│      tương đồng giữa các users.                            │
│                                                             │
│ 3. Fatigue Score Engine (Realtime Computation)             │
│    → Pipeline tính điểm mệt mỏi dựa trên tốc độ vuốt,      │
│      thời lượng phiên, và số lần xem lại.                  │
│                                                             │
│ 4. Multi-objective Adaptive Reranking                      │
│    → Mix 4 trọng số: Interest (40%) + Collab (25%) +       │
│      Diversity (20%) + Wellbeing (15%).                    │
│    → TRIGGER: Khi Fatigue > 70, swap nội dung dopanime cao │
│      thành nội dung có intensity thấp (chữa lành).         │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
         ┌────────────────────┐
         │  Mindful Feed      │ (Nội dung đã được "thanh lọc")
         └────────────────────┘