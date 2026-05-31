# Hướng Dẫn MongoDB Aggregation Pipeline - Personalization & Recommendation Feed

Tài liệu này mô tả chi tiết thiết kế và cách thức hoạt động của các MongoDB Aggregation Pipelines được sử dụng trong hệ thống gợi ý video (Personalization & Recommendation Feed) của dự án. Hệ thống kết hợp tìm kiếm ngữ nghĩa (Semantic Search) và mức độ thịnh hành động (Dynamic Trending Score) để tối ưu hóa trải nghiệm người dùng.

---

## 1. Công Thức Tính Điểm Trending Động (Dynamic Trending Score)

Điểm trending của một video được tính toán động tại thời điểm truy vấn (query-time) theo công thức:

$$\text{trending\_score} = (\text{view\_count} \times 1) + (\text{like\_count} \times 3) + (\text{comment\_count} \times 5)$$

### Lý do tính toán động:
- Giúp dễ dàng điều chỉnh trọng số của `view`, `like`, `comment` mà không cần chạy lại dữ liệu lịch sử hoặc cập nhật thủ công toàn bộ DB.
- Tránh việc bị lệch điểm khi các tương tác tăng trưởng liên tục.

---

## 2. Chi Tiết Các Aggregation Pipelines

### 2.1. Pipeline Cho Video Nổi Bật (Trending Feed - `find_trending`)
Pipeline này được sử dụng để lấy danh sách các video thịnh hành nhất khi người dùng mới đăng nhập (Cold-start) hoặc truy cập trang khám phá chung.

```python
pipeline = [
    {
        "$addFields": {
            "trending_score": {
                "$add": [
                    {"$multiply": [{"$ifNull": ["$view_count", 0]}, 1]},
                    {"$multiply": [{"$ifNull": ["$like_count", 0]}, 3]},
                    {"$multiply": [{"$ifNull": ["$comment_count", 0]}, 5]}
                ]
            }
        }
    },
    {"$sort": {"trending_score": -1}},
    {"$limit": limit}
]
```

#### Giải thích các Stages:
1. **`$addFields`**: Thêm một trường tạm thời tên là `trending_score` vào mỗi document kết quả.
   - **`$ifNull`**: Đảm bảo nếu trường `view_count`, `like_count`, hoặc `comment_count` chưa tồn tại hoặc mang giá trị `null`, MongoDB sẽ tự động thay bằng số `0` để tránh lỗi tính toán.
   - **`$multiply`**: Nhân số lượng tương tác tương ứng với trọng số (`view * 1`, `like * 3`, `comment * 5`).
   - **`$add`**: Cộng tổng các tích trên lại để ra `trending_score`.
2. **`$sort`**: Sắp xếp các video theo `trending_score` giảm dần (`-1`).
3. **`$limit`**: Giới hạn số lượng video trả về (mặc định là 10-20 videos) để giảm tải cho API.

---

### 2.2. Pipeline Gợi Ý Cá Nhân Hóa (Personalized Feed - `vector_search`)
Pipeline lõi này kết hợp giữa **Atlas Vector Search** (độ tương đồng ngữ nghĩa giữa sở thích của người dùng và nội dung video) và **Dynamic Trending Score** (mức độ phổ biến của video).

```python
pipeline = [
    {
        "$vectorSearch": {
            "index": "video_embedding_index",
            "path": "embedding",
            "queryVector": query_vector,
            "numCandidates": vs_candidates,
            "limit": vs_limit # Over-fetch: bù trừ cho các video sẽ bị loại bỏ
        }
    },
    # Post-filter: Stage $match phải nằm NGAY SAU $vectorSearch (Quy chuẩn của Atlas)
    {
        "$match": {"$and": [{"status": "completed"}, filter_stage]}
    },
    {
        "$addFields": {
            "search_score": {"$meta": "vectorSearchScore"},
            "trending_score": {
                "$add": [
                    {"$multiply": [{"$ifNull": ["$view_count", 0]}, 1]},
                    {"$multiply": [{"$ifNull": ["$like_count", 0]}, 3]},
                    {"$multiply": [{"$ifNull": ["$comment_count", 0]}, 5]}
                ]
            }
        }
    },
    {
        "$addFields": {
            "total_score": {
                "$add": [
                    {"$multiply": ["$search_score", search_weight]},
                    {"$multiply": ["$trending_score", trending_weight]}
                ]
            }
        }
    },
    # Cơ Chế Chống Mệt Mỏi (Adaptive Fatigue Sorting)
    # Nếu người dùng ở trạng thái "exhausted", thêm trường intensity_rank
    {
        "$addFields": {
            "intensity_rank": {
                "$switch": {
                    "branches": [
                        {"case": {"$eq": ["$intensity_level", "low"]}, "then": 0},
                        {"case": {"$eq": ["$intensity_level", "medium"]}, "then": 1},
                    ],
                    "default": 2  # high
                }
            }
        }
    },
    # Sắp xếp ưu tiên cường độ thấp trước, sau đó mới xét đến tổng điểm
    {
        "$sort": {"intensity_rank": 1, "total_score": -1}
    },
    # Lọc lại kết quả cuối cùng theo limit ban đầu sau khi đã loại trừ
    {
        "$limit": limit
    }
]
```

#### Giải thích các Stages & Trọng Số:
1. **`$vectorSearch` (Stage đầu tiên bắt buộc)**:
   - Chạy trên Atlas Search Index (`video_embedding_index`).
   - So sánh vector sở thích người dùng (`queryVector`) với trường vector embedding của video (`path: "embedding"`).
   - **Over-fetch**: `limit` và `numCandidates` được cộng thêm số lượng video đã xem (`num_exclude`) để bù đắp kết quả, đảm bảo sau khi lọc bớt (post-filter), hệ thống vẫn trả đủ số lượng video được yêu cầu.
2. **`$match` (Post-filter Stage)**:
   - Nằm ngay sau `$vectorSearch` để loại trừ các video đã xem hoặc lọc theo thể loại, đồng thời luôn yêu cầu `status: "completed"`. Đây là quy chuẩn đúng đắn của MongoDB Atlas Vector Search để có hiệu suất tốt nhất.
3. **`$addFields` (Trích xuất score)**:
   - Thêm `search_score` lấy từ hệ số tương đồng vector của MongoDB (`{"$meta": "vectorSearchScore"}`). Hệ số này nằm trong khoảng `[0, 1]`.
   - Tính toán trường `trending_score` thông qua helper `build_trending_score_pipeline_stage()`.
4. **`$addFields` (Tính toán tổng điểm kết hợp - Hybrid Score)**:
   - Tính toán `total_score` theo công thức:
     $$\text{total\_score} = (\text{search\_score} \times \text{search\_weight}) + (\text{trending\_score} \times \text{trending\_weight})$$
   - Cấu hình trọng số (trong Codebase hiện tại):
     - `search_weight = 100.0` (Ưu tiên chính cho sở thích người dùng, do search score chỉ <= 1.0).
     - `trending_weight = 1.0` (Cân bằng tốt giữa độ tương đồng và mức độ phổ biến của video).
5. **Cơ Chế Chống Mệt Mỏi (Adaptive Fatigue Sorting)**:
   - Nếu hệ thống phát hiện người dùng đang "mệt mỏi" (`adaptive_state == "exhausted"`), một `$addFields` stage sẽ sử dụng toán tử `$switch` để xếp hạng mức độ căng thẳng của video (`intensity_rank`): `low = 0`, `medium = 1`, `high = 2`.
   - Toán tử `$sort` sau đó sẽ ưu tiên `intensity_rank` tăng dần (`1`), rồi mới tới `total_score` giảm dần (`-1`). Điều này ép các video `low` (nhẹ nhàng, thư giãn) luôn nằm trên cùng dù tổng điểm có thấp hơn. Nếu ở trạng thái bình thường, nó chỉ sort theo `total_score: -1`.
6. **`$limit` (Final Trim)**:
   - Cắt lại danh sách kết quả vừa đủ số lượng `limit` ban đầu sau khi đã loại bỏ qua `$match` để tối ưu kích thước response.

---

## 3. So Sánh Hiệu Năng (Benchmark): Cách Tĩnh vs. Cách Động

Chúng tôi đã chạy benchmark trên **10.000 documents** để so sánh hai hướng tiếp cận:
- **Cách tĩnh (Static Index Sort):** Lưu trữ sẵn trường `trending_score` và tạo index trên trường đó (`trending_score: -1`).
- **Cách động (Dynamic Aggregation):** Tính toán điểm bằng toán tử aggregation tại thời điểm query.

### Kết quả đo lường:
- 🚀 **Cách tĩnh (Static Index Sort):** **~132.54 ms** (Sử dụng Index Scan - `IXSCAN`, đọc trực tiếp từ B-Tree index, cực kỳ tối ưu).
- 🧠 **Cách động (Aggregation):** **~162.49 ms** (Phải quét toàn bộ collection - `COLLSCAN`, thực hiện phép nhân/cộng trên từng document rồi sắp xếp trên RAM).

### Khuyến nghị cho team:
1. **Giai đoạn Hackathon / Dữ liệu nhỏ (< 100,000 videos):** Sử dụng **Cách động (Dynamic Aggregation)** vì mang lại sự linh hoạt tối đa để thử nghiệm các trọng số công thức khác nhau mà không cần cấu trúc lại database.
2. **Giai đoạn Production / Dữ liệu lớn:**
   - Nên chuyển sang **Cách tĩnh (Static)**: Mỗi khi có tương tác (`like`, `view`, `comment`), chúng ta chạy update atomic `{"$inc": ...}` đồng thời tính toán lại lưu vào một trường tĩnh `trending_score` trên document đó, và đánh index cho trường này.
   - Thường xuyên chạy một cron job định kỳ (ví dụ: mỗi 1-2 tiếng) để giảm điểm trending theo thời gian (decay score) giúp các video cũ giảm độ hot tự nhiên.

---

## 4. Quy Trình Cập Nhật Sở Thích Người Dùng (Feedback Loop)

Bên cạnh Aggregation Pipeline, luồng xử lý tương tác của người dùng đóng vai trò cập nhật vector đầu vào cho pipeline:

```mermaid
graph TD
    User([Người dùng]) -->|Xem/Thả tim/Bình luận| API[POST /interactions]
    API -->|1. Cập nhật số đếm| VideoDB[(Video Collection)]
    API -->|2. Ghi log tương tác| InterDB[(Interactions Collection)]
    API -->|3. Tính toán EMA Vector| Adapt[EMA Update Logic]
    Adapt -->|4. Lưu Vector mới| UserDB[(User Collection)]
    UserDB -->|Cung cấp Vector cho| FeedAPI[GET /feed]
    FeedAPI -->|Chạy $vectorSearch + Trending| User
```

### Công thức cập nhật vector (Exponential Moving Average - EMA):
$$\vec{V}_{new} = \vec{V}_{current} \times (1 - \alpha) + \vec{V}_{video} \times \alpha \times W_{action}$$

Trong đó:
- $\alpha = 0.20$ (Tốc độ thích nghi 20%).
- $W_{action}$ là trọng số hành vi:
  - `like`: $+0.5$
  - `comment`: $+0.8$
  - `skip` (xem dưới 10%, vuốt nhanh): $-0.3$ (kéo vector sở thích ra xa khỏi video này).
  - `watch_percentage` trên 80% tự động nâng trọng số lên tối thiểu $+0.8$.
- Sau mỗi lần cập nhật, vector mới sẽ được chuẩn hóa về độ dài bằng $1$ (Unit Normalization) để phép tính Cosine Similarity trong `$vectorSearch` đạt độ chính xác cao nhất.
