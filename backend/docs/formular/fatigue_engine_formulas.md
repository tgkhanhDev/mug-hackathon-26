# Hướng dẫn chi tiết: Fatigue Engine Formulas

Tài liệu này tổng hợp ý nghĩa của các từ khóa (keywords), các hằng số cấu hình (stats) và logic cốt lõi của các thuật toán trong file `fatigue.py`. Mục tiêu của hệ thống này là đo lường sự mệt mỏi của người dùng để điều tiết Feed, ngăn chặn tình trạng Burnout (kiệt sức) và Echo Chamber (buồng âm vang).

---

## 1. Từ khóa và Chỉ số Phạt Hành vi (Behavioral Penalties)

Các chỉ số này được dùng để đánh giá **10 log lướt video gần nhất** của người dùng (Window Size).

### `WATCH_DURATION_TIERS` (Phạt thời lượng xem)
- **Ý nghĩa:** Đánh giá độ kiên nhẫn của user thông qua thời gian dừng lại ở một video.
- **Cơ chế:**
  - `< 2s (+30 pts)`: Dấu hiệu rành rành của **Doom-scrolling** (cuộn vô thức). Não bộ đang tìm kiếm một "cú hích" nhưng không thỏa mãn. Hình phạt nặng nhất.
  - `< 5s (+15 pts)`: Lướt rất lướt, thiếu tập trung.
  - `< 15s (+5 pts)`: Mức độ thiếu kiên nhẫn nhẹ.
  - `≥ 15s (0 pts)`: Xem ổn định, không bị phạt.

### `SWIPE_SPEED_TIERS` (Phạt tốc độ vuốt)
- **Ý nghĩa:** Tốc độ ngón tay vuốt (tính bằng px/s) tỷ lệ thuận với sự cáu kỉnh hoặc sốt ruột. Tốc độ vuốt được đo bằng giá trị tuyệt đối (magnitude) nên áp dụng cho cả hành động vuốt lên và vuốt xuống.
- **Cơ chế:** 
  - `> 800 px/s (+20 pts)`: Vuốt giật cục, vội vã (Frantic scrolling).
  - `> 400 px/s (+10 pts)`: Vuốt nhanh hơn bình thường.
  - `≤ 400 px/s (0 pts)`: Lướt từ tốn.

### `PASSIVE_PENALTY` (Phạt thụ động)
- **Ý nghĩa:** Trạng thái "Zombie". User xem nhưng mắt lờ đờ, không thả tim, không comment, không share (`is_interaction = false`).
- **Cơ chế:** Cộng thẳng **15 pts** nếu không có bất kỳ tương tác chủ động nào.

---

## 2. Điểm Nhấn: Hai Lớp Pha Loãng (Dilution Layers)

Đây là 2 cơ chế đặc biệt quan trọng giúp hệ thống giữ được sự cân bằng, không bị "mù quáng" chạy theo sở thích của user.

### Lớp 1: Pha loãng Chủ đề (Topic Dilution) - `CONSECUTIVE_TOPIC_TIERS`
- **Keyword:** `consecutive_same_topic`
- **Vấn đề giải quyết:** "Echo Chamber" (Buồng âm vang). Thuật toán Recommendation thuần túy sẽ liên tục nhồi nhét nội dung user thích (VD: cứ xem mèo là trả về 100% video mèo). Hậu quả là user chán và bỏ app mà không rõ lý do.
- **Ý nghĩa:** Đảm bảo **Content Diversity** (Sự đa dạng nội dung). Dù user có thái độ cực kỳ tích cực với 1 chủ đề, hệ thống vẫn sẽ cưỡng ép họ dừng lại.
- **Cơ chế (Điểm phạt tăng vọt):**
  - Xem ≥ 3 video cùng topic liên tiếp: Phạt **15 pts**.
  - Xem ≥ 5 video cùng topic liên tiếp: Phạt **25 pts**.
- **Tác động:** Khi dính điểm phạt này, `Fatigue Score` sẽ tăng nhanh chóng. Feed tiếp theo bắt buộc phải gọi hàm **Explore** để chèn các chủ đề hoàn toàn mới nhằm "Reset" lại sự chú ý.

### Lớp 2: Pha loãng Cường độ Dopamine (Intensity Dilution) - `DOPAMINE_PENALTY_MULTIPLIER`
- **Keyword:** `high_intensity_count`, `total_intensity`
- **Vấn đề giải quyết:** "Dopamine Exhaustion" (Kiệt sức vì Dopamine). User xem rất nhiều chủ đề khác nhau (Game, Phim ảnh, Hài kịch), KHÔNG bị trùng topic, nhưng video nào cũng cắt ghép giật gân, âm thanh ồn ào.
- **Ý nghĩa:** Đóng vai trò là **Điểm phạt nền (Cumulative Baseline)**. Khác với các hình phạt ngắn hạn ở trên (chỉ tính 10 video gần nhất), điểm này tính dồn từ lúc user mở app đến hiện tại.
- **Cơ chế:** 
  - Tỷ lệ độc hại = `high_intensity_count / total_videos`
  - Điểm phạt nền = `Tỷ lệ độc hại * 10.0` (`DOPAMINE_PENALTY_MULTIPLIER`)
- **Tác động:** Lớp này không nhằm đổi Topic, mà nhằm **đổi Vibe**. Nếu điểm này cao, API sẽ chủ động tìm các video có `intensity_level = low` (như cảnh thiên nhiên, nhạc lo-fi, ASMR êm dịu) để làm dịu thần kinh user.

---

## 3. Các Thuật toán Cốt lõi (Core Algorithms)

Dưới đây là mô phỏng luồng dữ liệu (Data Flow) chảy qua các hàm, từ lúc nhận tín hiệu hành vi nhỏ nhất cho đến lúc ra quyết định phân phối video.

### 3.1. `calculate_log_penalty` (Chấm điểm Hành vi Vi mô)
- **Input:** 
  - `watch_duration` (float): Thời gian dừng ở video hiện tại.
  - `swipe_speed` (float): Tốc độ vuốt qua video.
  - `is_interaction` (bool): Có bấm like/comment/share không.
  - `consecutive_same_topic` (int): Chuỗi video cùng topic tính tới hiện tại.
- **Output:** `int` - Tổng điểm phạt (Penalty) của riêng 1 video này.
- **Vị trí trong Flow:** Hàm này nằm ở khâu "Tiền xử lý tín hiệu thô". Nó diễn dịch các thao tác tay lộn xộn của user thành những điểm số định lượng để chuẩn bị cho bước đánh giá tổng quát sức khỏe (bước 3.2).

### 3.2. `calculate_fatigue_score` (Đánh giá Sức khỏe Tổng quát)
- **Input:** 
  - `log_penalties` (List[int]): Mảng chứa 10 điểm phạt từ 10 video vừa lướt qua (Short-term window).
  - `high_intensity_count` (int): Tổng video giật gân đã xem từ đầu phiên (Long-term cumulative).
  - `low_intensity_count` (int): Tổng video êm dịu đã xem từ đầu phiên.
- **Output:** `float` - Con số định lượng mức độ Mệt mỏi (từ `0.0` đến `100.0`).
- **Vị trí trong Flow:** Hàm này đóng vai trò như "Bác sĩ chẩn đoán". Nó trộn lẫn tín hiệu bề mặt tức thời (10 logs) với "tiểu sử bệnh" (lượng dopamine từ đầu phiên) để ra được phác đồ chung (`Fatigue Score`). Thông số này được chuẩn bị để chuyển giao cho bộ phận phân phối.

### 3.3. `determine_adaptive_state` (Ra Mệnh lệnh Điều phối Feed)
- **Input:** 
  - `fatigue_score` (float): Điểm mệt mỏi từ bước 3.2.
- **Output:** `str` - Mệnh lệnh trạng thái (`"normal"`, `"warning"`, `"exhausted"`).
- **Vị trí trong Flow:** Đây là "Bộ Tổng Tham Mưu". Điểm mệt mỏi (vô tri) được phiên dịch thành Mệnh lệnh (có tính hành động). 
- **Ý nghĩa sống còn đối với API Gợi ý Video (Suggest Video):**
  - Mệnh lệnh này được ghi thẳng vào bảng `feed_sessions` trong Database.
  - Khi user vuốt tới cuối danh sách và gọi API **Get Next Feed**, thuật toán Recommendation sẽ đọc mệnh lệnh này đầu tiên:
    - Nếu là `"normal"`: API query thẳng vào Vector Database, lấy các video tương đồng nhất (Cosine Similarity cao nhất) với `interest_vector` của user. Chiều chuộng user tối đa.
    - Nếu là `"warning"`: Thuật toán Suggest Video bị ép đổi chiến thuật. Nó sẽ bỏ qua `interest_vector` một phần, chủ động query random các video khác Topic (để phá buồng âm vang) hoặc ép điều kiện query `{"intensity_level": "low"}` để làm dịu não user.
    - Nếu là `"exhausted"`: API Suggest Video có thể trả về thông điệp nhắc nhở hoặc chỉ toàn các video siêu nhẹ nhàng/bảo vệ sức khỏe tâm thần.
