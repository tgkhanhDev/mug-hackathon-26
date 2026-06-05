# 🎤 KỊCH BẢN THUYẾT TRÌNH HACKATHON: GOTOUCHGRASS
**Dự án:** GoTouchGrass - Mindful Recommendation Engine (Hệ thống gợi ý nhận thức sức khỏe tinh thần)
**Cấu trúc bám sát yêu cầu BGK:** Giới thiệu Use Case (2.5p) -> Demo Solution (5p) -> Kết quả đạt được (2.5p)
**Tổng thời lượng:** 10 Phút (Tối đa)

---

## PHẦN 1: GIỚI THIỆU USE CASE (2.5 Phút) 
*(Tiêu chí chấm: 30% Sáng tạo & 30% Tác động - Ý tưởng độc đáo, giải quyết vấn đề thực tế)*

### 🛝 SLIDE 1: Tiêu đề (30s)
* **Nội dung hiển thị:** Logo GoTouchGrass, Tag "MongoDB Hackathon", câu định vị: "A Wellbeing-Aware AI Recommendation Engine built on MongoDB Atlas."
* **Kịch bản nói:**
  > "Xin chào Ban giám khảo. Chắc hẳn 'Go touch grass' - 'Hãy ra ngoài hít thở không khí đi' là câu nói mạng rất quen thuộc nhắc nhở chúng ta ngừng dán mắt vào màn hình. Hôm nay, đội ngũ GoTouchGrass mang đến một giải pháp công nghệ hiện thực hóa câu nói đó: Một **Hệ thống gợi ý nội dung có khả năng nhận biết sức khỏe tinh thần**, được xây dựng hoàn toàn trên MongoDB Atlas."

### 🛝 SLIDE 2: Vấn đề & Tác động xã hội (1 phút)
* **Nội dung hiển thị:** 53% Gen Z bị hội chứng Doomscrolling, lướt 7.7 giờ/ngày. Bẫy Dopamine.
* **Kịch bản nói:**
  > "Hiện nay, các thuật toán MXH đang 'bị hỏng' ở một điểm: Chúng tối ưu hóa mù quáng cho thời gian xem (Watch Time) để tối đa hóa quảng cáo, đẩy người dùng vào trạng thái Doomscrolling (lướt vô định). Hậu quả là kiệt quệ tinh thần. Nền tảng cần người dùng ở lại, nhưng người dùng cần sự lành mạnh. Đó là một bài toán nhức nhối có tác động xã hội khổng lồ mà chúng tôi muốn giải quyết."

### 🛝 SLIDE 3: Cách tiếp cận mới mẻ (1 phút)
* **Nội dung hiển thị:** Sơ đồ so sánh: Dopamine-Driven (Cũ) vs Wellbeing-Aware (Mới - GoTouchGrass).
* **Kịch bản nói:**
  > "Giải pháp của GoTouchGrass vô cùng độc đáo: Thay vì chỉ tập trung vào tương tác (Engagement), chúng tôi đưa 'Sức khỏe tinh thần' thành một trọng số cốt lõi của thuật toán. Hệ thống đo lường độ mệt mỏi của bạn theo thời gian thực. Khi bạn kiệt sức, thuật toán tự động 'bẻ lái' sang các nội dung chữa lành, làm dịu tâm trí. Chúng ta có một hệ thống công nghệ thấu cảm."

---

## PHẦN 2: DEMO SOLUTION (5 Phút)
*(Tiêu chí chấm: 30% Kỹ thuật & 10% Trình bày - Code chất lượng, tích hợp MongoDB, Video Demo rõ ràng)*

### 🛝 SLIDE 4: Kiến trúc Kỹ thuật & Sự tích hợp MongoDB (1.5 phút)
* **Nội dung hiển thị:** Đoạn code Aggregation Pipeline tích hợp `$vectorSearch` và `$switch` xử lý tại Database.
  ```javascript
  db.videos.aggregate([
    // Bước 1: Khớp sở thích ngữ nghĩa bằng Vector
    { $vectorSearch: { queryVector: user_interest, path: "embedding", limit: 10 } },
    
    // Bước 2: Reranking bảo vệ người dùng bằng logic rẽ nhánh
    { $addFields: {
        intensity_rank: {
          $switch: {
            branches: [
              { case: { $eq: ["$intensity_level", "low"] }, then: 0 },
              { case: { $eq: ["$intensity_level", "medium"] }, then: 1 }
            ], default: 2
          }
        }
    }},
    { $sort: { intensity_rank: 1, total_score: -1 } }
  ]);
  ```
* **Kịch bản nói:**
  > "Để xử lý luồng logic này với tốc độ siêu tốc, kiến trúc của chúng tôi được thiết kế 100% tại tầng Database. Nhờ MongoDB Atlas, chúng tôi kết hợp **Vector Search** và **Aggregation Pipeline** (dùng toán tử `$switch` để tái xếp hạng theo cường độ nội dung) trong cùng một truy vấn duy nhất. Khả năng mở rộng (Scalability) của hệ thống cực cao vì chúng ta không phải kéo hàng ngàn dữ liệu về Backend để xử lý."

### 🛝 SLIDE 5: Video / Live Demo (3.5 phút)
* **Nội dung hiển thị:** Video hoặc chiếu trực tiếp màn hình lướt Feed trên App. Hiển thị Dashboard theo dõi chỉ số mệt mỏi (Fatigue Score).
* **Kịch bản thao tác & nói:**
  > *(Thao tác: Bắt đầu lướt feed từ tốn)* "Mời Ban giám khảo xem bản Demo. Ở góc nhìn người dùng, họ đang lướt nội dung bình thường. Ẩn bên dưới, thuật toán đang tính toán hành vi vuốt và thời gian xem để xuất ra Fatigue Score."
  > 
  > *(Thao tác: Lướt nhanh, vuốt liên tục mô phỏng lướt vô thức)* "Bây giờ, tôi mô phỏng việc lướt vô thức liên tục. Điểm mệt mỏi lập tức vượt ngưỡng 70. Lúc này, Pipeline MongoDB được kích hoạt..."
  > 
  > *(Thao tác: Feed bắt đầu hiện video thư giãn)* "...Không hề có cảnh báo thô bạo ép tắt ứng dụng, feed tự động mượt mà chuyển sang các nội dung thiên nhiên nhẹ nhàng (Low intensity) thuộc sở thích của tôi. Não bộ được 'thải độc' mà trải nghiệm lướt vẫn liền mạch."

---

## PHẦN 3: KẾT QUẢ ĐẠT ĐƯỢC (2.5 Phút)
*(Tiêu chí chấm: 30% Tác động & 30% Kỹ thuật - Kết quả thực tế, mở rộng)*

### 🛝 SLIDE 6: User Impact & Core Achievements (1.5 phút)
* **Nội dung hiển thị (Gợi ý thiết kế Layout):**
  * **Tiêu đề Slide:** User Impact & Core Achievements
  * **Bố cục (Layout):** Chia làm 3 cột (hoặc 3 khối ngang) tương ứng với 3 kết quả, sử dụng icon trực quan:
    1. 🧠 / 🛑 **Break the Dopamine Loop**
       * *Cơ chế:* Powered by **Fatigue Algorithm**
       * *Điểm nhấn:* Phát hiện & ngắt doomscrolling tự động.
    2. 🎨 / 🧩 **Maintain Content Diversity**
       * *Cơ chế:* Powered by **User Interest Algorithm**
       * *Điểm nhấn:* Cá nhân hóa cao, không gò bó.
    3. 📉 / 🛡️ **Zero Trending Bias**
       * *Cơ chế:* Powered by **Custom Ranking Algorithm**
       * *Điểm nhấn:* 100% hướng đến sức khỏe, nói không với toxic viral.
* **Kịch bản nói:**
  > "Về thành quả của MVP, thay vì chỉ nói về thông số kỹ thuật, chúng tôi muốn nhấn mạnh vào những tác động tích cực, trực tiếp đến người dùng. Chúng tôi đã chứng minh được ba kết quả cốt lõi:
  > 
  > Thứ nhất, chúng tôi thành công **phá vỡ vòng lặp dopamine**. Thông qua Thuật toán Fatigue, hệ thống phát hiện các hành vi lướt vô thức (doomscrolling) và mượt mà chuyển đổi feed sang các nội dung nhẹ nhàng, êm dịu hơn trước khi người dùng chạm ngưỡng kiệt quệ tinh thần.
  > 
  > Thứ hai, chúng tôi **duy trì được sự đa dạng nội dung**. Thuật toán User Interest đảm bảo rằng ngay cả khi đề xuất các video chữa lành, nội dung vẫn được cá nhân hóa cao độ và sát với sở thích cốt lõi của người dùng, giúp họ vẫn hứng thú mà không cảm thấy bị gò bó.
  > 
  > Cuối cùng, chúng tôi **không bị thiên lệch bởi xu hướng (zero trending bias)**. Khác với các nền tảng truyền thống luôn đẩy nội dung viral để tối đa hóa thời gian xem, thuật toán Ranking của chúng tôi hoàn toàn miễn nhiễm với các trending. Bảng tin được điều hướng 100% bởi sức khỏe tinh thần và sở thích cá nhân, chứ không phải vì lợi nhuận hay sự phổ biến. Chúng tôi tin rằng đây chính là nền móng cho một hệ sinh thái số bền vững và lành mạnh."

### 🛝 SLIDE 7: Tổng kết (1 phút)
* **Nội dung hiển thị:** Thông điệp: "Engineering Empathetic Systems" & QR Code trải nghiệm.
* **Kịch bản nói:**
  > "GoTouchGrass không chỉ là một ứng dụng, nó là một minh chứng kiến trúc (Proof of Concept) cho thế hệ Recommendation Engine tiếp theo: Thấu cảm, Minh bạch và Bảo vệ con người. 
  > 
  > Cảm ơn Ban giám khảo MongoDB Hackathon. Chúng tôi rất vinh hạnh được trình bày và mong nhận được câu hỏi từ quý vị!"