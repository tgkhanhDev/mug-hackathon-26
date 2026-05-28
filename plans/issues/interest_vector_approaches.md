# 📊 So Sánh 3 Cách Cập Nhật Interest Vector

> **Tài liệu**: So sánh 3 cách tiếp cận update `users.interest_vector`  
> **Quyết định**: Cách 2 - Cập nhật hàng loạt khi kết thúc session  
> **Trạng thái**: Sẵn sàng triển khai  
> **Cập nhật**: 21/05/2026

---

## 🎯 Vấn đề đặt ra

Thời điểm nào nên update `users.interest_vector`?

- **Cách 1**: Real-time (ngay sau mỗi like/skip/replay)
- **Cách 2**: Hàng loạt khi session kết thúc (user đóng app)
- **Cách 3**: Hybrid - Chạy background async

Mỗi cách có trade-off khác nhau về:
- Tốc độ response API
- Tải DB
- Độ tươi mới của recommendation
- Độ phức tạp code

---

## ⚡ Cách 1: Real-Time Update (Mỗi Interaction)

### Luồng hoạt động

```
User LIKE video → POST /interactions
    ↓
record_interaction():
    ① INSERT interactions document
    ② Tăng counters video
    ③ ⚠️ UPDATE users.interest_vector ← CHẶN response
    ④ Broadcast WebSocket
    ↓
Response 201 (sau khi vector update xong)
```

### Ưu điểm ✅

| Lợi ích | Chi tiết |
|---|---|
| **Cá nhân hóa real-time** | Feed update ngay khi user thích video mới |
| **Mỗi signal được tính** | Like/skip/replay mỗi cái đều ảnh hưởng tới recommendation |
| **Client stateless** | Frontend không cần track interactions |
| **Logic đơn giản** | Dễ hiểu: interaction = update ngay |

### Nhược điểm ❌

| Hạn chế | Chi tiết | Tác động |
|---|---|---|
| **API response chậm** | Phải chờ vector update xong mới trả kết quả | UX: User chờ 200-500ms |
| **DB tải nặng** | 1 session = 10-20 interactions = 10-20 lần update vector | DB: Write pressure cao |
| **I/O nhiều** | Mỗi update = read user + read video + normalize + write | Performance: 20+ queries/session |
| **Công việc lặp lại** | Like 5 video "coding" = update 5 lần cùng signal | Lãng phí: Tính toán dư thừa |
| **Network chậm** | Mỗi update phải qua network | Latency: Cộng dồn nếu DB ở xa |

### Ví dụ: 1 Session với 20 Interactions

```
Thời gian:

T0: User like video A (coding)
    → Query user.interest_vector (1 query)
    → Query video A embedding (1 query)
    → Tính EMA: new_vec = 0.85 * old + 0.15 * 1.0 * embedding_A
    → Normalize
    → Write DB (1 write)
    → Response 201 [200ms latency]

T1: User like video B (coding)
    → Query user.interest_vector (1 query) ← Kết quả y hệt, lặp lại
    → Query video B embedding (1 query)
    → Tính EMA: new_vec = 0.85 * (đã update T0) + 0.15 * 1.0 * embedding_B
    → Normalize
    → Write DB (1 write)
    → Response 201 [200ms latency]

... (lặp 18 lần nữa)

Total: ~40 DB reads + 20 DB writes trong 1 session
Average response time: ~200ms per interaction
```

### Khi nào dùng

- ❌ **Không khuyến nghị** cho hackathon (có vấn đề performance)
- ✅ Chỉ khi:
  - Interaction rate rất thấp (< 5 per session)
  - DB local (< 10ms latency)
  - Có đủ tài nguyên server
  - Cần instant vector update cho A/B testing

---

## ✅ Cách 2: Cập Nhật Hàng Loạt Khi Kết Thúc Session (KHUYẾN NGHỊ)

### Luồng hoạt động

```
User LIKE video → POST /interactions
    ↓
record_interaction():
    ① INSERT interactions document
    ② Tăng counters video
    ③ ❌ BỎ QUA interest_vector update
    ④ Broadcast WebSocket
    ↓
Response 201 (nhanh ⚡)

---

User đóng app → PUT /api/v1/sessions/{id}/end
    ↓
end_session():
    ① Lấy toàn bộ interactions trong session
    ② Tính new_vector = EMA từ [int1, int2, ..., int20]
    ③ UPDATE users.interest_vector (1 lần duy nhất)
    ④ UPDATE feed_sessions với fatigue_score
    ↓
Response 200
```

### Ưu điểm ✅

| Lợi ích | Chi tiết |
|---|---|
| **API response nhanh** | POST /interactions = 80-120ms (không tính toán vector) |
| **DB tải nhẹ** | 1 read + 1 write per session-end, không per interaction |
| **Hiệu quả batch** | 1 function tích lũy thay vì N lần EMA riêng biệt |
| **Giảm lặp lại** | Signal tương tự (5x coding) xử lý cùng lúc |
| **Có quy mô** | Xử lý được 100 interactions/session mà không giảm performance |
| **Tối ưu network** | 1 round-trip DB per session, không per interaction |
| **Clustering ngữ nghĩa** | Tất cả interactions kết hợp trước tính hướng |

### Nhược điểm ❌

| Hạn chế | Chi tiết | Giải pháp |
|---|---|---|
| **Vector cũ trong session** | Trong phiên, vector = hôm qua | Chấp nhận được: session tiếp theo dùng vector tươi |
| **Feed delay** | Like 20 "football" → recommendation còn "coding" cho tới hết session | Chấp nhận được: chút delay là OK cho MVP |
| **Session timeout phức tạp** | Xử lý: kết thúc tường minh + timeout ngầm | Thêm background job auto-end sessions cũ |
| **Overhead development** | Code nhiều hơn: session lifecycle + batch logic | Xứng đáng cho performance gain |

### Ví dụ: 1 Session với 20 Interactions

```
Thời gian:

T0-T45 (45 phút session):
  ├─ T0: User like video A → Response 201 [80ms] ← NHANH
  ├─ T2: User like video B → Response 201 [80ms]
  ├─ T5: User skip video C → Response 201 [80ms]
  ├─ ...
  └─ T45: User like video T → Response 201 [80ms]
  
  [Tất cả 20 interactions được lưu, KHÔNG update vector]

T45 (User đóng app):
  ├─ PUT /api/v1/sessions/{id}/end
  ├─ Backend: Lấy 20 interactions cùng lúc
  ├─ Tính: accumulated_vec = Σ(weight_i * embedding_i) cho all 20
  ├─ Tính: new_vec = 0.85 * old + 0.15 * (accumulated / 20)
  ├─ Normalize
  ├─ UPDATE users.interest_vector [1 write]
  └─ Response 200 [150ms]

Total: ~4 DB reads + 1 DB write
Average response time per interaction: 80ms (không chờ vector)
Session end: 150ms (batch operation 1 lần)

RESULT: 10x faster per interaction + DB tải ít hơn nhiều!
```

### Khi nào dùng

✅ **KHUYẾN NGHỊ** (Đây là lựa chọn của chúng ta!)

- Hackathon MVP (performance quan trọng)
- Cần API response nhanh
- High interaction volume per session (10+)
- Chấp nhận personalization lag nhỏ

---

## 🔄 Cách 3: Hybrid - Async Background Update

### Luồng hoạt động

```
User LIKE video → POST /interactions
    ↓
record_interaction():
    ① INSERT interactions document
    ② Tăng counters video
    ③ asyncio.create_task(update_vector_async()) ← Non-blocking
    ④ Broadcast WebSocket
    ↓
Response 201 (ngay lập tức ⚡⚡)
    ↓
[Background, async]:
    Read user.interest_vector + video.embedding
    → Tính EMA
    → UPDATE users.interest_vector
    (xảy ra khi user vẫn còn dùng app)
```

### Ưu điểm ✅

| Lợi ích | Chi tiết |
|---|---|
| **Ultra-fast response** | 30-50ms (không chặn ở đâu) |
| **Background vector updates** | Update vector khi user lướt, không chặn |
| **Real-time personalization** | Vector update khi session active (eventual consistency) |
| **Best of both worlds** | Nhanh + vector còn tương đối tươi |

### Nhược điểm ❌

| Hạn chế | Chi tiết | Mức độ |
|---|---|---|
| **Eventual consistency** | Vector update có thể không xong trước request tiếp theo | Trung bình: Race condition có thể xảy ra |
| **Multiple updates in flight** | User like 3 videos nhanh → 3 async tasks cạnh tranh write | Cao: Khó debug |
| **State inconsistency** | Feed có thể hiển thị trước khi vector updates xong | Trung bình: Feed hơi stale |
| **Resource overhead** | Nhiều small async tasks thay vì 1 batch | Trung bình: Overhead thread/task cao hơn |
| **Error handling khó** | Background task fail → silent failure (user không biết) | Cao: Khó debug production |
| **Retry complexity** | Nếu DB write fail, khó retry mà không duplicate updates | Cao: Có thể mất/hỏng vector |

### Ví dụ: 1 Session với 20 Interactions

```
Thời gian:

T0: User like video A
    POST /interactions → Response 201 [40ms] ← ngay lập tức
    asyncio.create_task(update_vector_async)
    [Background: đang read/compute/write... (200ms)]

T1: User like video B
    POST /interactions → Response 201 [40ms] ← ngay lập tức
    asyncio.create_task(update_vector_async)
    [Background: có thể race với T0 task]

T2: User gọi GET /feed
    → ⚠️ Chỉ có 1 trong 2 async updates hoàn thành
    → recommendations có thể còn cũ

...

Vấn đề: Vector nào là "source of truth"?
        Có thể xảy ra race conditions.
```

### Khi nào dùng

⚠️ **Dùng với cảnh báo**

- Chỉ khi cần response dưới 50ms AND eventual consistency chấp nhận được
- Cần robust error handling + logging
- Không khuyến nghị cho MVP/hackathon (complexity > benefit)

---

## 📊 Bảng So Sánh

| Tiêu chí | Cách 1: Real-Time | Cách 2: Batch End | Cách 3: Async |
|---|---|---|---|
| **Response time** | 150-300ms ❌ | 80-120ms ✅ | 30-50ms ✨ |
| **DB reads/session** | 20 reads ❌ | 5 reads ✅ | 20 reads ❌ |
| **DB writes/session** | 20 writes ❌ | 1 write ✅ | 20 writes ❌ |
| **Vector freshness** | Instant 🔄 | 1 session delay ⏳ | Eventual 🔄 |
| **Consistency** | Strong ✅ | Strong ✅ | Eventual ⚠️ |
| **Implementation** | Simple ✅ | Medium 🟡 | Complex ❌ |
| **Bug risk** | Low ✅ | Low ✅ | High ❌ |
| **Scalability** | Poor ❌ | Excellent ✅ | Good 🟡 |
| **Hackathon fit** | ❌ | ✅✅✅ | ⚠️ |

---

## 🎯 Quyết Định: Chọn Cách 2

### Tại sao chọn Batch Update Khi Session End?

1. **Performance**: API response 10x nhanh hơn (80ms vs 300ms)
2. **DB efficiency**: 1 write per session vs 20 writes
3. **Simplicity**: Semantics rõ ràng (session end = update point)
4. **Scalability**: Xử lý được interaction volume cao
5. **Alignment with vision**: "Disconnect to Reflect" → session end là natural update trigger
6. **Time-series benefits**: Có thể tính fatigue_score cùng lúc
7. **Batch semantics**: Sophisticated hơn: có thể apply ML transformations lên toàn bộ interactions cùng lúc

### Không phải mất mát lớn

Việc "vector lag" (delay 1 session) chấp nhận được vì:
- Recommendation đã being personalized via initial `interest_tags` + `interest_vector`
- First session dùng semantic similarity vẫn hữu ích
- Session thứ 2 trở đi có fully fresh vector (từ interactions session trước)
- User thường ở app > 5-10 phút, nên cảm giác "real-time"

---

## ⏱️ Lịch triển khai

| Phase | Task | Ước tính | Phụ thuộc |
|---|---|---|---|
| 1 | Bỏ real-time `_update_interest_vector()` từ `record_interaction()` | 15 min | interactions_service.py |
| 2 | Implement `_batch_update_interest_vector()` | 30 min | interactions_service.py |
| 3 | Update `end_session()` để call batch update | 20 min | interactions_repo.py |
| 4 | Test: create interaction → end session → verify vector updated | 45 min | integration test |
| 5 | Performance benchmark: đo API response times | 30 min | load test |
| **Tổng cộng** | | **2.5 hours** | |

---

## 📚 Tài liệu liên quan

- [User Interaction Flow](./user_interaction_flow.md) — Chi tiết từng bước luồng
- [ERD Schema](./erd_schema.md) — Cấu trúc database
- [Interaction API Design](../backend/docs/interaction_api_design.md) — API contracts


