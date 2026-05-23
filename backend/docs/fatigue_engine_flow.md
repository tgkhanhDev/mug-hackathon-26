# Fatigue Engine Flow: Tính toán Mệt mỏi và Đổi Feed

Dưới đây là lời giải thích chi tiết về cách hệ thống tính toán điểm mệt mỏi (`fatigue_score`) và trạng thái feed (`adaptive_state`), giải đáp các thắc mắc của bạn về kiến trúc của Fatigue Engine.

---

## 1. Trả lời các thắc mắc của bạn

### Mục đích của `get_consecutive_topic_count` (Tại sao lại query 10 log gần nhất?)
Khi user lướt liên tục qua nhiều video có *cùng một topic* (VD: lướt qua 5 video "bóng đá" liên tiếp), não bộ sẽ nhanh chóng rơi vào trạng thái bão hòa (emotional saturation/topic fatigue). Dù video có hay, việc xem đi xem lại một chủ đề sẽ gây chán nản nhanh hơn.
- Việc query 10 log gần nhất để đếm `consecutive_same_topic` là nhằm phát hiện **ngay lập tức** dấu hiệu "bão hòa chủ đề" ngắn hạn này. Nếu lặp lại ≥ 3 lần, hệ thống sẽ cộng điểm phạt (penalty) để cảnh báo rằng: *"Nên đổi feed khác cho user đi, họ sắp chán rồi"*.

### Vấn đề tính sai ngữ nghĩa của `avg_watch_duration` và `avg_swipe_speed`
Bạn hoàn toàn chính xác! Lỗi logic ở đây là hàm `_update_session_fatigue_and_state` tính trung bình của **10 log gần nhất** (short-term moving average) nhưng lại lưu đè vào thuộc tính `avg_watch_duration` của cả **session** hiện tại. Việc này làm hỏng ngữ nghĩa của "trung bình toàn phiên".
- **Cách fix:** Tôi đã gỡ bỏ logic tính và lưu đè `avg_...` trong hàm này. Hiện tại, `avg_watch_duration` và `avg_swipe_speed` sẽ chỉ được tính tổng thể một lần duy nhất dựa trên *toàn bộ* log khi gọi hàm `end_session()`.

### Tại sao dùng `high_count` và `low_count` chung với 10 log?
`high_intensity_count` và `low_intensity_count` là tổng số video kích thích cao/thấp mà user đã xem trong **cả session**, không phải chỉ trong 10 log gần nhất. Việc dùng 10 log là để đánh giá *hành vi bề mặt* (vuốt nhanh, lướt nông), còn `high_count/low_count` dùng để đánh giá *tích lũy sinh học* (dopamine). Hệ thống gộp 2 yếu tố này lại để ra điểm mệt mỏi cuối cùng.

---

## 2. Hoạt động của `calculate_fatigue_score` và `determine_adaptive_state`

### Bước 1: Tính điểm phạt cho từng hành vi (`calculate_log_penalty`)
Với mỗi video trong 10 log gần nhất, hệ thống sẽ quy hành vi thành một điểm phạt (Penalty) từ 0 đến vô hạn. Càng có nhiều hành vi "tiêu cực", điểm phạt càng cao.
- **Thời lượng xem (`duration_penalty`):**
  - Xem < 2s (Doom-scrolling): Phạt **30đ**
  - Xem < 5s: Phạt **15đ**
  - Xem < 15s: Phạt **5đ**
- **Tốc độ vuốt (`swipe_penalty`):**
  - Vuốt quá nhanh (> 800px/s): Phạt **20đ**
  - Vuốt nhanh (> 400px/s): Phạt **10đ**
- **Không tương tác (`passive_penalty`):**
  - Xem thụ động (chỉ lướt, không like/comment): Phạt **15đ**
- **Trùng lặp chủ đề (`consecutive_penalty`):**
  - Gặp cùng 1 topic ≥ 5 lần liên tiếp: Phạt **25đ**
  - Gặp cùng 1 topic ≥ 3 lần liên tiếp: Phạt **15đ**

*Ví dụ:* Một user vuốt qua video sau 1s (30đ), tốc độ vuốt 900px/s (20đ), thụ động (15đ). Điểm phạt cho video này là **65đ**.

### Bước 2: Tổng hợp thành Điểm Mệt mỏi (`calculate_fatigue_score`)
Điểm số này (từ `0.0` đến `100.0`) được tổng hợp từ 2 yếu tố:
1. **Hành vi ngắn hạn (Average Log Points):** Trung bình cộng của điểm phạt (penalty) từ 10 video gần nhất.
2. **Dopamine tích lũy (Dopamine Penalty):** Càng xem nhiều video `high_intensity` trong session, não càng mệt. Điểm này tính bằng tỉ lệ: `(Số video high_intensity / Tổng video đã xem) * 10`.

`Fatigue Score` = *Trung bình hành vi 10 video gần nhất* + *Điểm Dopamine tích lũy*.

### Bước 3: Xác định Trạng thái Đề xuất (`determine_adaptive_state`)
Dựa vào `Fatigue Score` (0-100), hệ thống sẽ quyết định trạng thái (`adaptive_state`) để chuẩn bị cho các lệnh lấy video tiếp theo:
- **`normal` (Score < 40):** User đang tận hưởng tốt. Thuật toán gợi ý Feed sẽ tiếp tục trả về các video matching với `interest_vector` hoặc trending bình thường.
- **`warning` (Score từ 40 - 70):** Bắt đầu chán nản. Thuật toán sẽ chủ động đổi chủ đề (Explore mode) hoặc trộn video `low_intensity` vào để làm dịu não bộ (Calming content).
- **`exhausted` (Score > 70):** Doom-scrolling chạm đỉnh. Ứng dụng có thể hiện cảnh báo "Nghỉ ngơi chút nhé" hoặc chỉ suggest các video cực kỳ nhẹ nhàng (thiên nhiên, ASMR...).

Toàn bộ thông số này được lưu vào `feed_sessions` và sẽ được API `GET /feed` đọc ra để quyết định truy vấn video nào cho lần lướt tiếp theo của user.
