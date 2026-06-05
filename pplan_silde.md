# 🗂️ SLIDE DECK: GOTOUCHGRASS - MINDFUL RECOMMENDATION ENGINE

---

## 🟦 Slide 1: Tiêu đề (Title Slide)
**Nội dung chính:**
* **Tên dự án:** GoTouchGrass
* **Subtitle:** Wellbeing-aware AI Recommendation Engine với MongoDB Atlas Vector Search
* **Thông điệp:** "Phá vỡ vòng lặp Doomscrolling - Vì cuộc sống không chỉ có màn hình"
* **Team:** [Tên Team của bạn]

> **Speaker Notes:** Chào ban giám khảo và mọi người, hôm nay chúng tôi mang đến GoTouchGrass – một giải pháp không chỉ thay đổi cách chúng ta xem video, mà còn thay đổi cách chúng ta sống trong kỷ nguyên số.

---

## 🟦 Slide 2: Thực trạng - "Cơn nghiện" Dopamine
**Nội dung chính:**
* **53% Gen Z** thừa nhận đang Doomscroll vô thức.
* **7h 43p/ngày** là thời gian dùng smartphone trung bình của Gen Z.
* **Hệ lụy:** Gần 50% Gen Z gặp vấn đề sức khỏe tâm thần do kiệt sức kỹ thuật số.

> **Speaker Notes:** Chúng ta đang sống trong một nghịch lý: Càng kết nối nhiều trên mạng xã hội, chúng ta càng dễ kiệt sức. Doomscrolling không còn là sở thích, nó là một vấn đề sức khỏe cộng đồng.

---

## 🟦 Slide 3: Vấn đề - Thuật toán "Vô cảm"
**Nội dung chính:**
* **Vấn đề:** Các Recommendation Engine hiện tại (TikTok, Facebook) chỉ tối ưu duy nhất 01 chỉ số: **Watch Time**.
* **Hậu quả:** 
    * Nhốt người dùng vào vòng lặp dopamine cao.
    * Chôn vùi các nhà sáng tạo nội dung giáo dục/chữa lành.
    * Tỷ lệ rời bỏ (Churn rate) tăng do người dùng cảm thấy "tội lỗi" sau khi xem.

> **Speaker Notes:** Tại sao TikTok hay Facebook lại gây nghiện? Vì thuật toán của họ "vô cảm". Họ chỉ quan tâm bạn ở lại app bao lâu, bất kể điều đó làm bạn mệt mỏi hay kiệt sức.

---

## 🟦 Slide 4: Tầm nhìn Sản phẩm - Khác biệt của GoTouchGrass
**Nội dung chính:**
* **Đối thủ (TikTok/FB):** Tối ưu Engagement bằng mọi giá.
* **GoTouchGrass:** Tối ưu Wellbeing thông qua Personalization.
* **Triết lý:** "Chúng tôi xây dựng hệ thống biết điểm dừng."
* **Thông điệp:** Đã đến lúc ra ngoài và xem cỏ thực sự có màu gì!

> **Speaker Notes:** GoTouchGrass không phải là một app chặn bạn dùng MXH. Chúng tôi là một Engine thông minh. Khác với đối thủ, chúng tôi bảo vệ sức khỏe người dùng bằng lời nhắc nhở: Hãy ra ngoài chạm vào cỏ (Touch Grass).

---

## 🟦 Slide 5: GoTouchGrass là gì? (Product Statement)
**Nội dung chính:**
* **Dành cho:** Gen Z và những người dùng bị quá tải thông tin.
* **Giải pháp:** Hệ thống gợi ý AI nhận thức sức khỏe tinh thần.
* **Điểm cốt lõi:** Tự động phát hiện Fatigue Score (Điểm mệt mỏi) để điều chỉnh Feed nội dung theo thời gian thực.

> **Speaker Notes:** Thay vì ép bạn tắt máy, GoTouchGrass sẽ tinh tế điều hướng bạn từ những nội dung gây hưng phấn quá đà sang những nội dung êm dịu hơn khi nhận thấy bạn bắt đầu mệt mỏi.

---

## 🟦 Slide 6: Các tính năng đột phá
**Nội dung chính:**
* **Real-time Fatigue Detection:** Theo dõi tốc độ vuốt và thời gian xem để tính điểm mệt mỏi.
* **Adaptive Reranking:** Khi Fatigue > 70, tự động ưu tiên nội dung "chữa lành" (Intensity thấp).
* **Creator Diversity:** Đảm bảo các nội dung tích cực không bị chôn vùi.

> **Speaker Notes:** Hệ thống của chúng tôi hoạt động như một người bạn đồng hành. Nếu bạn mê xe hơi và đang mệt, thay vì cho bạn xem đua xe, chúng tôi sẽ gợi ý video ASMR rửa xe cực kỳ thư giãn.

---

## 🟦 Slide 7: Kiến trúc hệ thống (Architecture)
**Nội dung chính:**
* **Frontend:** Tracking hành vi người dùng.
* **Core:** MongoDB Atlas.
    * **Vector Search:** Cá nhân hóa sở thích.
    * **Aggregation Pipeline:** Tính toán Fatigue Score & Collaborative Filtering.
* **Response:** Feed nội dung được tái xếp hạng (Reranked).

> **Speaker Notes:** Để làm được điều này với độ trễ cực thấp, chúng tôi tận dụng sức mạnh của MongoDB. Mọi tính toán phức tạp về điểm mệt mỏi đều được xử lý ngay tại lớp Database.

---

## 🟦 Slide 8: Tại sao lại là MongoDB?
**Nội dung chính:**
* **Atlas Vector Search:** Lưu trữ và truy vấn embeddings (1536-dim) siêu nhanh.
* **Aggregation Pipelines:** Xử lý logic Fatigue Score realtime mà không cần đẩy lên Application Layer.
* **Performance:** Latency < 300ms cho mỗi yêu cầu gợi ý.

> **Speaker Notes:** MongoDB Atlas không chỉ là nơi lưu trữ, nó là "bộ não" thực hiện việc so khớp vector và điều chỉnh luồng nội dung ngay tức thì, đảm bảo trải nghiệm người dùng luôn mượt mà.

---

## 🟦 Slide 9: Demo & Kết quả đạt được
**Nội dung chính:**
* Show video/hình ảnh Prototype lướt video.
* Dashboard hiển thị điểm Fatigue Score nhảy realtime.
* So sánh: Feed trước và sau khi kích hoạt chế độ "Chạm cỏ".

> **Speaker Notes:** Hãy nhìn vào Demo, khi người dùng lướt quá nhanh – dấu hiệu của việc Doomscroll – hệ thống lập tức nhận diện và thay đổi màu sắc cũng như thể loại nội dung êm dịu hơn.

---

## 🟦 Slide 10: Tổng kết & Kêu gọi hành động
**Nội dung chính:**
* **Win-Win-Win:** 
    * Người dùng: Khỏe mạnh hơn.
    * Creator: Nội dung đa dạng hơn.
    * Nền tảng: Phát triển bền vững hơn.
* **Thông điệp cuối:** "Technology that cares."

> **Speaker Notes:** Chúng tôi tin rằng công nghệ tương lai phải là công nghệ có tâm hồn. GoTouchGrass là bước đi đầu tiên để xây dựng một thế giới số lành mạnh hơn. Cảm ơn mọi người đã lắng nghe!