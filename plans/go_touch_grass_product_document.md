# Project Document: GoTouchGrass (Mindful Feed Recommendation Engine)

Với vai trò là Project Manager cho đội ngũ 3 người tham gia MongoDB Hackathon, dưới đây là tài liệu chi tiết (Detailed Breakdown) để làm kim chỉ nam cho team trong quá trình phát triển MVP.

---

## 1. Business Requirements (Yêu cầu nghiệp vụ)
**Bối cảnh và nhu cầu thị trường:**
- **Thực trạng:** Người dùng trên các nền tảng video ngắn (TikTok, Reels, Shorts) đang dành quá nhiều thời gian để lướt feed một cách thụ động, dẫn đến tình trạng **doomscrolling** (lướt mạng vô thức) và kiệt quệ về mặt tinh thần (mental exhaustion).
- **Nguyên nhân cốt lõi:** Các hệ thống gợi ý hiện tại tối ưu hóa hoàn toàn cho tỷ lệ giữ chân (retention) và thời gian xem (watch time). Điều này tạo ra sự thiên vị nặng nề, liên tục phân phối các nội dung giật gân, tạo dopamine cao và nhốt người dùng vào một vòng lặp nội dung lặp đi lặp lại.
- **Hậu quả kinh doanh & người dùng:** Người dùng cảm thấy tội lỗi, mệt mỏi sau mỗi phiên sử dụng kéo dài. Đồng thời, các nhà sáng tạo nội dung nhỏ hoặc có nội dung nhẹ nhàng/chữa lành bị hạn chế khả năng tiếp cận (low discoverability).
- **Giải pháp (Nhu cầu sản phẩm):** Xây dựng một **Hệ thống Gợi ý nội dung Mindful Feed** có khả năng:
  1. Cá nhân hóa mạnh mẽ nhưng mang tính nhận thức về sức khỏe tinh thần (wellbeing-aware).
  2. Phát hiện sớm các dấu hiệu doomscrolling và mệt mỏi theo thời gian thực.
  3. Tự động tái cân bằng (rebalance) feed bằng các nội dung có tính chất làm dịu, giáo dục để phá vỡ vòng lặp cường độ cao.
  4. Cân bằng giữa việc duy trì tương tác (engagement) tự nhiên và bảo vệ sức khỏe kỹ thuật số (digital wellbeing) của người dùng.

---

## 2. Problem Statement (Phát biểu vấn đề)
- **The problem of:** Hệ thống gợi ý video ngắn hiện tại chỉ tập trung tối đa hóa engagement thông qua các nội dung kích thích, dẫn đến vòng lặp Doomscrolling, kiệt sức tinh thần, giảm sự tập trung và gây burnout số (digital burnout) do người dùng tiêu thụ nội dung vô thức kéo dài.
- **Affects:** Gen Z, học sinh sinh viên, nhân viên văn phòng, nhà sáng tạo nội dung và cả các nền tảng MXH muốn cải thiện Digital Wellbeing mà không muốn hy sinh chất lượng tương tác cá nhân hóa.
- **The impact of which is:**
  - Gia tăng tình trạng "nghiện" dopamine và suy giảm năng suất làm việc, học tập.
  - Hệ thống vô tình khuếch đại sự kích thích cảm xúc quá mức do chỉ tối ưu cho *Watch Time*.
  - Người dùng kẹt trong vòng lặp nội dung thiếu đa dạng, trong khi các nội dung tích cực/nhẹ nhàng bị chôn vùi.
- **A successful solution would be:** Một Mindful Recommendation Engine có khả năng:
  - Gợi ý cá nhân hóa thông qua *user interest embeddings* và độ tương đồng hành vi.
  - Tracking hành vi theo thời gian thực để phát hiện Doomscrolling (dựa trên swipe speed, watch duration, v.v.).
  - Tính toán linh hoạt **Fatigue Score** (Điểm mệt mỏi).
  - Bơm (inject) các nội dung "Palette Cleanser" (thanh lọc) như thiên nhiên, thiền định, nhịp chậm khi người dùng có dấu hiệu mệt mỏi.
  - Sử dụng **MongoDB Vector Search** và **Aggregation Pipeline** để cân bằng hoàn hảo giữa Personalization, Engagement, Diversity, và Wellbeing.

---

## 3. Product Vision (Tầm nhìn sản phẩm)
- **For:** Người dùng Gen Z, học sinh, sinh viên và dân văn phòng thường xuyên sử dụng TikTok, Reels, Shorts.
- **Who:** Đang gặp vấn đề với hành vi doomscrolling, kiệt sức tinh thần do vòng lặp nội dung cường độ cao và thiếu một trải nghiệm cá nhân hóa lành mạnh.
- **The product name:** **GoTouchGrass**
- **Is a:** Wellbeing-aware AI Recommendation Engine (Hệ thống gợi ý AI nhận thức sức khỏe tinh thần) dành cho nền tảng video ngắn.
- **That:** Cá nhân hóa một cách thông minh nguồn cấp dữ liệu video, đồng thời phát hiện sự mệt mỏi do doomscrolling theo thời gian thực để cân bằng linh hoạt giữa các nội dung kích thích tương tác cao và các gợi ý mang tính chữa lành, ý nghĩa.
- **Unlike:** Các hệ thống gợi ý truyền thống chỉ tối ưu đơn thuần cho tỷ lệ giữ chân (retention) và tương tác do dopamine điều khiển.
- **Our product:** Kết hợp sức mạnh của **MongoDB Vector Search**, phân tích hành vi, tính điểm Fatigue Score và tái xếp hạng feed (reranking) thích ứng. Từ đó tạo ra một trải nghiệm xem cá nhân hóa lành mạnh, cân bằng cảm xúc và bền vững mà không làm giảm sự hài lòng của người dùng.

---

## 4. Project Scope (Phạm vi Dự án - Giới hạn cho Hackathon)
Vì team chỉ có 3 người và thời gian hackathon có hạn, chúng ta sẽ tập trung vào các phạm vi sau để đảm bảo tính khả thi (feasibility) và hoàn thành MVP:
- **Giới hạn thời gian & Nguồn lực:** Hoàn thành toàn bộ MVP và Demo trong khung thời gian của cuộc thi với 3 thành viên (cần phân chia rõ: 1 Frontend/Data, 1 Backend/Recommendation Logic, 1 DevOps/Presentation).
- **Nguồn dữ liệu (Data constraints):**
  - Sử dụng bộ Metadata video ngắn mẫu (Sample dataset).
  - Sử dụng bộ dữ liệu hành vi người dùng mô phỏng (Synthetic user interaction dataset) để tạo session log, thay vì lấy data thực tế từ TikTok/Reels do giới hạn API.
- **Phạm vi kỹ thuật (Technical constraints):**
  - Không train mô hình Machine Learning lớn. Sử dụng Lightweight heuristic AI và Embedding APIs (OpenAI Embedding hoặc sentence-transformers).
  - Tập trung sâu vào việc show-case công nghệ của MongoDB: **Atlas Vector Search**, **Atlas Search**, và **Aggregation Pipelines** để giải quyết logic.
- **Giao diện Demo:** 
  - Một UI mô phỏng app lướt video ngắn đơn giản.
  - Một Dashboard hiển thị Real-time Analytics (Fatigue Score, Adaptive State).

---

## 5. Product Scope (Phạm vi Sản phẩm)
Phạm vi sản phẩm sẽ bao gồm các tính năng chức năng (Functional) và phi chức năng (Non-functional) cốt lõi sau:

### 5.1. Các Module cốt lõi (Functional)
1. **Frontend Simulation & Behavioral Tracking:**
   - Giao diện người dùng mô phỏng lướt feed dọc (vuốt lên/xuống).
   - Hệ thống tracking ngầm các thao tác: *swipe speed* (tốc độ vuốt), *watch duration* (thời gian xem), *replay count* (số lần xem lại), *interaction frequency* (tần suất tương tác tim/share), *session duration* (độ dài phiên lướt).
2. **Fatigue Detection Engine:**
   - Nhận data từ tracking để tính toán **Fatigue Score** realtime (Điểm mệt mỏi từ 0-100).
   - Logic cấu hình được các mức độ mệt mỏi (bình thường -> cảnh báo -> kiệt sức).
3. **Mindful Recommendation Engine (Lõi MongoDB):**
   - **Gợi ý ban đầu:** Dựa trên Watch/Interaction history, vector similarity.
   - **Adaptive Feed Re-ranking (Tái xếp hạng feed thích ứng):** Khi Fatigue Score vượt ngưỡng, hệ thống tự động:
     - Giảm trọng số của nội dung cường độ cao.
     - Tăng trọng số (inject) nội dung chữa lành, làm dịu (calming, educational).
     - Đảm bảo tính đa dạng (Diversity) của creators và topics.
4. **Analytics Dashboard:**
   - Giao diện Admin/Monitor để ban giám khảo thấy quá trình chuyển đổi của Feed, chỉ số Fatigue theo session và cách MongoDB đang xử lý query phía dưới.

### 5.2. Yêu cầu hệ thống (Non-functional) & Business Rules
- **Performance:** Thời gian phản hồi gợi ý `< 300ms`, Feed adaptation phải phản hồi mượt mà gần như ngay lập tức (near real-time) để người dùng không cảm thấy khựng.
- **Usability:** Chuyển đổi nội dung phải cực kỳ tự nhiên, không hiển thị các thông báo ép buộc kiểu "Bạn đã xem quá lâu, hãy tắt máy đi" mà thay vào đó là điều chỉnh content một cách tinh tế.
- **Business Rules:**
  - Tính cá nhân hóa vẫn được giữ vững ngay cả khi đang trong chế độ chữa lành (vd: người dùng thích xe hơi đang mệt mỏi -> gợi ý quy trình rửa xe chậm, ASMR xe hơi thay vì đua xe tốc độ cao).
  - Fatigue Score chỉ ảnh hưởng đến ưu tiên xếp hạng (reranking), không chặn hoàn toàn nội dung giải trí.
