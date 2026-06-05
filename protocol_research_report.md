# Báo cáo Nghiên cứu Kỹ thuật: Ứng dụng các Giao thức Giao tiếp trong GoTouchGrass

## Tổng quan
Trong quá trình xây dựng **GoTouchGrass**, thách thức lớn nhất của chúng tôi là phải đảm bảo trải nghiệm lướt video mượt mà (Infinite Scroll) nhưng đồng thời hệ thống ẩn bên dưới phải tính toán và phân tích sức khỏe tinh thần (Fatigue Score) theo thời gian thực. Để giải quyết bài toán hiệu năng và trải nghiệm, chúng tôi đã áp dụng đa dạng các giao thức giao tiếp (Communication Protocols). 

Dưới đây là báo cáo tổng kết những vấn đề (issues) đã gặp phải và cách chúng tôi sử dụng từng giao thức để giải quyết bài toán cụ thể trong dự án.

---

## 1. REST (FastAPI)
### 🚨 Vấn đề (Issue)
Hệ thống cần cung cấp các điểm chạm (endpoints) cơ bản để thực hiện xác thực người dùng (Login/Register) và đặc biệt là "nạp" (fetch) lô video ban đầu để hiển thị trên màn hình chính. Việc dùng các giao thức realtime ngay từ đầu để lấy data tĩnh là quá cồng kềnh, khó quản lý bộ nhớ đệm (cache) ở Frontend.

### 💡 Giải pháp & Use-case trong dự án
- Dùng REST API cho các tác vụ CRUD thông thường và API `GET /feed`.
- **Lessons Learned:** REST kết hợp với chuẩn HTTP Status Codes vô cùng phù hợp để tích hợp với thư viện SWR phía Frontend. Nó giải quyết triệt để bài toán phân trang (pagination) và deduplication ban đầu. REST đảm bảo kiến trúc Stateless (không lưu trạng thái) ở tầng API, dễ dàng mở rộng (scale).

---

## 2. Apache Kafka (Event Streaming)
### 🚨 Vấn đề (Issue): "The Doomscrolling Bottleneck"
Khi người dùng rơi vào trạng thái *lướt vô thức (doomscrolling)*, họ lướt qua video rất nhanh (có thể 2-3 video mỗi giây). Frontend phải liên tục bắn các gói `Behavior Log` (chứa tốc độ vuốt, thời lượng xem, thể loại). 
Ban đầu, khi dùng API REST đồng bộ (lưu trực tiếp vào MongoDB, sau đó tính toán điểm mệt mỏi rồi mới trả response), Database liên tục bị quá tải (Write Bottleneck). API phản hồi chậm kéo theo việc UI Frontend bị giật lag (freeze) khi lướt.

### 💡 Giải pháp & Use-case trong dự án
- Chúng tôi tích hợp **Kafka** làm Message Broker. API lúc này chỉ đóng vai trò **Producer**, đẩy Log vào Kafka và lập tức trả về HTTP 201 cho Frontend (Fire-and-forget). UI không bị block.
- Ở phía sau, một **Kafka Consumer** (background worker) sẽ từ từ "nuốt" các message này, tính toán lại Fatigue Score và lưu xuống Database một cách tuần tự.
- **Lessons Learned:** Kafka giúp chúng tôi **tách rời (decouple)** luồng ghi nhận dữ liệu (ingestion) và luồng xử lý tính toán tốn kém (processing). Nhờ đó, hệ thống GoTouchGrass có thể dễ dàng hấp thụ các đợt "bão" vuốt video (traffic spikes) mà không làm sập Database.

---

## 3. Server-Sent Events (SSE)
### 🚨 Vấn đề (Issue): Quá tải mạng do Polling
Để thanh trạng thái sức khỏe (Fatigue Gauge) trên app có thể đổi màu và modal Touch Grass hiện lên đúng lúc, Frontend cần biết điểm Fatigue Score mới nhất. Ban đầu, chúng tôi dùng cơ chế **Polling** (Frontend gọi API `GET /sessions/events` mỗi 3 giây). Điều này tạo ra hàng ngàn request rác (Overhead), lãng phí băng thông và tài nguyên Server dù người dùng không hề tương tác gì thêm.

### 💡 Giải pháp & Use-case trong dự án
- Chúng tôi gỡ bỏ Polling và thay bằng **SSE**. Đây là kết nối mở 1 chiều từ Server xuống Client.
- Khi Kafka tính toán xong điểm Fatigue mới, Server sẽ **chủ động "bắn" (push)** điểm số này xuống Frontend. 
- **Lessons Learned:** Đối với các use-case chỉ cần nhận dữ liệu từ Server (Unidirectional) như luồng cảnh báo sức khỏe, SSE nhẹ hơn WebSocket rất nhiều và còn hỗ trợ cơ chế tự động kết nối lại (auto-reconnect) từ trình duyệt. Nó giảm thiểu 90% lượng request vô ích.

---

## 4. Redis Pub/Sub
### 🚨 Vấn đề (Issue): Giao tiếp chéo giữa Background Worker và HTTP Server
Phát sinh một vấn đề hóc búa về kiến trúc: Kafka Consumer là một tiến trình chạy ngầm xử lý Log. Khi nó tính ra điểm mệt mỏi (Fatigue Score) mới, làm sao nó có thể "báo" cho API Server đang giữ kết nối SSE của người dùng để đẩy dữ liệu xuống Frontend? Nếu chạy nhiều server (Load Balancing), worker sẽ không biết user đang kết nối tới server nào.

### 💡 Giải pháp & Use-case trong dự án
- Tích hợp **Redis Pub/Sub** làm trạm trung chuyển tín hiệu. 
- Kafka Consumer sau khi tính toán xong sẽ **Publish** (phát thanh) sự kiện lên Redis channel `session:{id}:events`.
- Mọi máy chủ API Server đều **Subscribe** (đăng ký nghe) kênh này. Ngay khi có tin nhắn từ Redis, Server đang giữ kết nối với Client đó sẽ chuyển tiếp data xuống qua luồng SSE.
- **Lessons Learned:** Redis Pub/Sub đóng vai trò như một chiếc cầu nối (Bridge) vô hình, lưu trữ trên RAM với độ trễ cực thấp (Sub-millisecond). Nó giúp giải quyết triệt để bài toán đồng bộ trạng thái (State synchronization) trong hệ thống phân tán.

---

## 5. WebSocket
### 🚨 Vấn đề (Issue): Tương tác đa chiều (Collaborative Interactions)
Để tăng tính sinh động, ứng dụng cần hiển thị số lượng View, Like, và Comment thay đổi liên tục khi có người khác cùng tương tác với video (hiệu ứng nhảy số live). 
Nếu dùng REST, dữ liệu luôn bị cũ. Nếu dùng SSE, nó chỉ giải quyết được chiều Server -> Client, còn Client bấm Like thì vẫn phải gọi qua một kênh khác gây bất đồng bộ.

### 💡 Giải pháp & Use-case trong dự án
- Tích hợp **WebSocket** (`/ws/stats`) để mở kết nối 2 chiều (Bidirectional).
- Khi người dùng xem một video, WebSocket sẽ kết nối vào room của video đó. Bất kỳ ai bấm Like, tín hiệu gửi lên Server qua WS và lập tức Server broadcast về cho mọi người trong room.
- **Lessons Learned:** Dù WebSocket tốn tài nguyên duy trì kết nối hơn các giao thức khác, nhưng nó là mảnh ghép bắt buộc đối với các tính năng đòi hỏi tương tác đa chiều thời gian thực với độ trễ dưới 50ms, mang lại cảm giác sống động (living app) cho ứng dụng.
