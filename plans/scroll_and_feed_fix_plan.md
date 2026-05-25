# 📋 Kế hoạch Khắc phục Lỗi Scroll & Phân trang Feed

**Ngày lập:** 24 tháng 5, 2026
**Mục tiêu:** Khắc phục lỗi app bị treo khi scroll nhanh và lỗi feed ngừng tải thêm video sau vài lần cuộn.

---

## 🛑 Vấn đề 1: Feed ngừng tải thêm data sau 5 lần cuộn

### 🔍 Nguyên nhân gốc rễ
1. **Frontend Pagination sai cách:** Trong `App.tsx`, thay vì giữ nguyên limit và lấy trang tiếp theo, code đang liên tục cộng dồn `limit` (10 → 20 → 30 → 40 → 50).
2. **Backend thiếu Deduplication ở cấp độ Query:** Hàm `get_feed` trong `feed_service.py` lấy toàn bộ video ra mà **không hề có filter loại trừ các video đã xem** (`$nin: seen_video_ids`) trong pipeline `$vectorSearch`.
3. **Hiệu ứng domino:** Khi FE yêu cầu `limit=50`, BE trả về 50 video (có thể là max số lượng trong DB). Khi lướt tiếp, FE thấy mảng kết quả trả về không tăng thêm (vì DB hết video match), nên điều kiện `accumulatedVideos.length < prev` bị kích hoạt, làm biến `limit` không tăng nữa -> SWR ngừng fetch.

### 🛠️ Giải pháp (Cần sửa cả BE + FE)

**1. Sửa Backend (`backend/app/services/feed_service.py`)**
*   **Thu thập `seen_video_ids` sớm:** Dời logic query bảng `interactions` và `behavior_logs` lên ngay đầu hàm `get_feed`.
*   **Áp dụng filter `$nin`:** Thêm `{"_id": {"$nin": [ObjectId(id) for id in seen_video_ids]}}` vào biến `filter_stage`.
*   *Lợi ích:* Đảm bảo MongoDB `$vectorSearch` và `find_trending` luôn trả về các video **chưa từng xuất hiện** trong session này.

**2. Sửa Frontend (`frontend/src/App.tsx`)**
*   Giữ hằng số `const BATCH_SIZE = 5;`
*   **Thay đổi logic `onLoadMore`:** Thay vì `setFeedLimit(prev + 10)`, chỉ cần gọi `mutateFeed()`.
*   *Lợi ích:* Mỗi lần tới đáy, FE gọi `/feed?limit=5`. BE (đã được sửa ở trên) sẽ trả về 5 video **mới tinh**. FE chỉ việc append nối tiếp vào mảng `accumulatedVideos`.

---

## 🛑 Vấn đề 2: App bị treo (Freeze/Hang) khi vuốt nhanh

### 🔍 Nguyên nhân gốc rễ
1. **Tràn RAM do thẻ `<video>` (DOM Overload):** Khi mảng `accumulatedVideos` phình to lên 50 video, React âm thầm giữ 50 thẻ `<video src="...">` trong DOM. Trình duyệt tải trước (preload) và xử lý bộ nhớ cho 50 video cùng lúc dẫn đến tràn RAM và treo máy.
2. **Spam kết nối WebSocket:** Khi lướt qua nhanh 10 video, hook `useInView` trong `VideoCard` chớp tắt 10 lần, tạo ra hàng chục thông điệp `{"action": "subscribe"}` và `{"action": "unsubscribe"}` gửi qua WS, gây nghẽn cổ chai.
3. **Spam API Behavior Log:** Lướt nhanh 10 video đồng nghĩa với việc FE bắn liền 10 request `POST /behavior-logs`, làm kẹt Network Tab.

### 🛠️ Giải pháp (Sửa FE)

**1. Virtualization (Tối ưu DOM trong `VideoCard.tsx` & `Feed.tsx`)**
*   **Vấn đề: Tại sao `<video>` nặng hơn `<div>`? (Deep Dive Cơ chế cấp phát)** 
    *   **Video Decoder là gì?** Video (MP4, WebM) là dữ liệu bị nén phức tạp (H.264, VP9). Để hiển thị, hệ điều hành (OS) cần cấp phát một **Video Decoder** (chip chuyên dụng trên GPU hoặc phần mềm trên CPU) để giải nén liên tục thành từng khung hình.
    *   **Cơ chế Chunking / Segment:** Về mặt mạng (Network), trình duyệt tải video theo từng chunk nhỏ (VD: tải 10MB đầu của file 100MB). Nếu chỉ xét về Buffer, 50 thẻ video tải đoạn đầu cũng chỉ tốn vài trăm MB RAM.
    *   **Thủ phạm gây treo máy (OOM / Crash):** Dù thẻ `<video>` chỉ mới tải chunk đầu tiên, Trình duyệt vẫn bắt OS khởi tạo ngay lập tức **1 phiên Video Decoder**, **1 phân vùng VRAM (Texture Surface)** để chờ vẽ hình, và **1 Audio Context**. Nếu giữ 50 thẻ `<video>` trong DOM, thiết bị phải gánh 50 Decoder và 50 GPU Context cùng lúc, làm cạn kiệt phần cứng đồ họa (VRAM) dẫn tới đơ máy. Trái lại, `<div>` trống chỉ mất vài byte bộ nhớ cơ bản.
*   **Cơ chế Sliding Window (Cửa sổ trượt) trên DOM, không phải trên Dữ liệu:** 
    *   **Biến `accumulatedVideos`:** Là state lưu trữ dồn (append) danh sách metadata video sau mỗi lần gọi API. Nhờ nối thêm chứ không ghi đè, nó tạo ra trải nghiệm cuộn vô hạn (Infinite Scroll). Mảng này **vẫn lưu giữ toàn bộ dữ liệu** của các video đã fetch (có thể lên tới hàng trăm phần tử).
    *   Tuy nhiên ở tầng Render, truyền prop `index` và `activeIndex` vào `VideoCard` và dùng điều kiện: `Math.abs(index - activeIndex) <= 2`.
    *   *Ví dụ:* Bạn đang xem video số 8 (`activeIndex = 8`). Cửa sổ render sẽ là các index `6, 7, 8, 9, 10`. Chỉ 5 component này mới được render ra thẻ HTML `<video>`. Các component còn lại (như 1-5 hay 11-50) sẽ chỉ render thẻ `<div className="placeholder">` để giữ nguyên chiều cao (tránh bị nhảy scroll).
*   **Khi lướt ngược lại (Scroll up):** Nếu bạn vuốt ngược lên video số 6 (`activeIndex = 6`), thì cửa sổ dịch chuyển thành `4, 5, 6, 7, 8`. React sẽ tự động chuyển component 4 và 5 từ `<div>` trở lại thành thẻ `<video>` và video sẽ load/chạy bình thường.
*   **Khi nào gọi API tải thêm (Fetch Next Page)?** Khi mảng data đang có độ dài N, ta sẽ đặt một "cảm biến" (Intersection Observer) ở khoảng N-3 (cách đáy 3 video). Khi `activeIndex` chạm tới video này, FE sẽ tự động trigger API để fetch thêm batch mới (vd: 10 video) rồi đẩy tiếp vào cuối mảng `accumulatedVideos`. Nhờ có Virtualization, mảng data có to đến 1000 phần tử đi nữa thì DOM vẫn nhẹ tênh vì chỉ gánh 5 thẻ `<video>` thực thụ.

**2. Chống Spam WebSocket (`VideoCard.tsx`)**
*   Thay vì dùng biến `inView` (trigger ngay cả khi lướt lướt qua), hãy đổi sang dùng biến `isActive` (chỉ true khi video thực sự dừng lại ở màn hình) để truyền vào hook `useVideoStats`.
*   *Lợi ích:* Giảm 90% lượng message rác gửi qua WS khi cuộn nhanh.

**3. Debounce API Behavior Log (`VideoCard.tsx`)**
*   Trong hàm cleanup (khi rời khỏi 1 video), tính `duration = Date.now() - startTime`.
*   Thêm điều kiện: `if (duration < 0.2) return;` (Nếu thời gian xem dưới 0.2 giây tức là user vô tình cuộn ngang qua, không cần lưu log).
*   *Lợi ích:* Tránh dội bom API backend vô ích.

---

## 📅 Các bước thực hiện (Next Actions)

1. Mở `feed_service.py` và dời logic `seen_set` lên trên cùng.
2. Mở `App.tsx` và sửa lại hàm `onLoadMore` để không tăng `limit`.
3. Mở `Feed.tsx` để truyền prop `index` và `activeIndex` xuống `VideoCard`.
4. Mở `VideoCard.tsx` thêm logic Virtualization (giấu thẻ video) và chặn spam API.

---

## 📚 Phụ lục: Giải thích chuyên sâu về Network & Memory cho Video

Dưới đây là phần hỏi đáp chi tiết để làm rõ cơ chế đằng sau việc tối ưu DOM và Network.

### 1. Biến `accumulatedVideos` làm gì và đem lại hiệu ứng gì?
*   **Nó làm gì?** Đây là một mảng dữ liệu (Array State) ở Frontend (bên trong `App.tsx` hoặc `Feed.tsx`). Nhiệm vụ của nó là "gom" (accumulate) tất cả các video đã được fetch từ Backend về.
*   **Hiệu ứng đem lại:** Thay vì mỗi lần fetch trang mới (ví dụ gọi API lấy 5 video tiếp theo), mảng cũ bị xoá và thay thế bằng mảng mới (như bấm chuyển trang 1 sang trang 2 ở các web cũ), thì các video mới sẽ được **nối thêm (append)** vào đuôi mảng này. Nhờ vậy, user có được trải nghiệm **Cuộn vô hạn (Infinite Scroll)**. Dữ liệu các video cũ vẫn nằm trong mảng này ở trên RAM để khi user lướt ngược lên trên, thông tin video vẫn còn đó và hiển thị ngay lập tức không cần phải call API lại.

### 2. Video Decoder là gì?
*   Video (như MP4, WebM) không phải là những bức ảnh nối tiếp nhau một cách đơn giản, mà chúng được **nén (compress)** bằng những thuật toán cực kỳ phức tạp (như H.264, VP9) để giảm dung lượng từ vài chục GB xuống còn vài chục MB.
*   Để màn hình hiển thị được hình ảnh, thiết bị (điện thoại/máy tính) cần một **bộ giải mã (Decoder)**. Decoder có thể là một con chip chuyên biệt nằm bên trong GPU (Hardware Decoder) hoặc là một phần mềm dùng sức mạnh của CPU (Software Decoder).
*   Nhiệm vụ của Decoder là đọc luồng dữ liệu bị nén đó, giải nén nó thành từng khung hình (frame) theo thời gian thực (vd: 60 khung hình/giây) và quăng lên màn hình. Công việc này đòi hỏi rất nhiều tính toán.

### 3. Có phải thẻ `<video>` chỉ xin cấp phát 10MB cho mỗi Chunk tải về? Vì sao nó vẫn gây treo máy?
**Về việc tải Chunk (Segment):** Trình duyệt rất thông minh (thông qua HTTP Range Requests). Với video 100MB có 10 chunks, khi video được gắn vào thẻ HTML `<video>`, nó không tải 1 cục 100MB ngay. Nó tải chunk 1 (10MB), nằm trong bộ đệm (Buffer). Xem hết chunk 1, nó nối tiếp chunk 2 (thêm 10MB). **Về mặt Network và RAM lưu file buffer, nó rất tối ưu!**

**Tuy nhiên, lí do 50 thẻ `<video>` gây treo máy KHÔNG NẰM Ở BUFFER FILE TẢI VỀ, mà nằm ở hệ điều hành (OS) và GPU:**

Ngay khi bạn nhét 1 thẻ `<video>` vào DOM (dù nó chỉ mới tải 1MB dữ liệu), Trình duyệt sẽ yêu cầu Hệ Điều Hành (OS):
1. *"Ê OS, cấp cho tao 1 phiên giải mã Video Decoder đi."*
2. *"Cấp cho tao một phân vùng bộ nhớ VRAM của GPU (Texture Surface) để tao chuẩn bị vẽ các khung hình."*
3. *"Cấp cho tao một Audio Context để xử lý âm thanh."*

Bây giờ, bạn cuộn siêu nhanh, tạo ra 50 thẻ `<video>`.
*   **Về mặt File/Network:** 50 thẻ này chỉ tải mỗi cái 1MB đoạn đầu -> Bạn mới tốn 50MB RAM lưu file, quá nhỏ bé!
*   **Về mặt Hệ Điều Hành (OS):** Thiết bị phải cùng lúc mở **50 cái Video Decoder** và giam giữ **50 phân vùng GPU Texture**. Phần cứng của điện thoại hoặc máy tính (VRAM/Decode Engine) có giới hạn, nó không gánh nổi 50 cái context giải mã cùng lúc, dẫn đến bị quá tải, rò rỉ bộ nhớ đồ hoạ (GPU Memory Leak) và hệ quả là màn hình khựng lại hoặc Crash App!

**Đó là lý do ta phải dùng Div (Virtualization):**
Thẻ `<div>` thì chỉ là một cái hộp vuông chứa văn bản/màu nền. Nó mất khoảng 1KB RAM và CPU để vẽ. Khi trượt đi, ta giấu thẻ `<video>` thành `<div>`, hệ điều hành sẽ giải phóng cái "Video Decoder" và "GPU Memory" đó để nhường cho video đang chiếu.

### 4. Xử lý State khi chuyển đổi qua lại giữa `<video>` và `<div>`
Khi thay thế `<video>` bằng `<div>` (Virtualization), thẻ `<video>` thực chất bị hủy (unmount) khỏi DOM và mất hết bộ đệm. Để trải nghiệm mượt mà, ta xử lý như sau:

*   **Từ `<div>` về lại `<video>` (Làm sao biết fetch segment nào?):**
    Khi thẻ `<video>` bị hủy, nó sẽ quên mất mình đang phát tới đâu. Để giải quyết, ta làm như sau:
    *   **Lưu tọa độ thời gian (State/Ref):** Trước khi thẻ `<video>` biến mất (bị unmount), ta dùng React lưu lại thời gian đang xem của user. Ví dụ: `const savedTime = useRef(videoElement.currentTime)` (giả sử đang xem ở giây thứ 15.5).
    *   **Browser thông minh (HTTP Range Request):** Khi user cuộn lại, thẻ `<video>` mới được sinh ra. Ta gán ngay `video.currentTime = 15.5`. Lúc này, trình duyệt sẽ đọc cái "Mục lục" của file video (gọi là Metadata hay `moov atom`), nó tự tính toán: *"À, giây thứ 15.5 tương đương với byte thứ 5 triệu của file"*.
    *   **Fetch đúng chỗ:** Trình duyệt lập tức gửi một request lên Backend có chứa Header `Range: bytes=5000000-`. Nhờ vậy, Backend chỉ trả về đúng cái Chunk (Segment) chứa giây thứ 15.5 trở đi, chứ không tải lại từ đầu.

*   **Từ `<video>` sang `<div>` (Làm sao không bị đen màn hình?):**
    Nếu ta rút ngang thẻ `<video>` và để lại `<div>` trống, màn hình sẽ bị giật chớp đen. Để "đánh lừa" thị giác người dùng, có 2 cách phổ biến:
    *   **Cách 1 (Dễ nhất - Dùng Thumbnail):** Thẻ `<div>` đó thực chất chứa một thẻ `<img src={poster_url} />` bao phủ toàn bộ. Khi video biến mất, màn hình hiện bức ảnh bìa của video (giống hệt lúc bạn mới mở app TikTok mà mạng chậm, nó hiện cái ảnh tĩnh trước khi video chạy).
    *   **Cách 2 (Siêu mượt - Chụp ảnh Snapshot):** Ngay trước cái mili-giây mà thẻ `<video>` bị hủy, Javascript sẽ "chụp" lại chính xác khung hình đang dừng của video đó (bằng cách dùng một thẻ `<canvas>` ẩn để vẽ lại frame). Sau đó xuất ra một tấm ảnh tĩnh (`canvas.toDataURL()`) và ốp tấm ảnh tĩnh đó làm `background-image` cho cái `<div>`.
