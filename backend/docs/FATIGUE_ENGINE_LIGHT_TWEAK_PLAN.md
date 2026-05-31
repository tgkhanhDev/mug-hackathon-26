# 🐛 Thảo Luận Sửa Lỗi Tối Giản (Light Tweak Plan) cho Fatigue Engine

**Phiên bản:** v2 (Light Tweak)
**Mục tiêu:** Cắt giảm sự phức tạp của bản plan ban đầu, tập trung fix dứt điểm lỗi bằng số lượng code ít nhất.

---

## 1. Vấn đề cốt lõi (Root Cause)

Bug xảy ra ở 2 bước Fallback trong file `backend/app/services/feed_service.py` khi hệ thống không tìm đủ số lượng video thư giãn cho user đang mệt mỏi:

*   **Fallback 1:** Hệ thống hoảng loạn và vứt bỏ hoàn toàn `intensity_filter` (mức độ mệt mỏi), chỉ giữ lại bộ lọc Deduplication (không xem lại video cũ). **👉 Đây là nguyên nhân khiến video Gaming/Sports lọt vào.**
*   **Fallback 2:** Nếu vẫn không tìm thấy video nào (do người dùng đã xem hết DB), hệ thống vứt nốt cả Deduplication.

---

## 2. Giải pháp rút gọn (The "Light Tweak")

Thay vì chia ra các logic phức tạp như "Nới lỏng dần (Relax)" hay `docs.extend()` như tài liệu trước, chúng ta chỉ cần giải quyết một nguyên lý duy nhất:
> **Tuyệt đối không bỏ `intensity_filter` trong bất kỳ tình huống nào khi người dùng đang mệt.**

Cách xử lý (Chỉ 1 Fallback):
1. Cứ chạy truy vấn như bình thường với `combined_filter` (Intensity + Dedup).
2. Nếu tìm được ít video (`len(docs) < limit`), cứ trả về ít video, không cố tìm thêm bằng cách bỏ `intensity`. (Xóa Fallback 1).
3. Nếu **không tìm được video nào** (`len(docs) == 0`), nghĩa là user đã xem cạn kho video thỏa mãn, ta cho phép xem lại video cũ (bỏ Dedup) **NHƯNG BẮT BUỘC giữ lại `intensity_filter`**.

---

## 3. Code Implementation

Chỉ cần sửa lại cụm Fallback (từ khoảng dòng 169-202) trong `feed_service.py` thành như sau:

```python
# [Step 1] Fetch lần đầu với kết hợp cường độ & video chưa xem
docs = await self._fetch_feed(
    interest_vector=interest_vector,
    user_id=user_id,
    limit=limit,
    adaptive_state=adaptive_state,
    search_weight=search_weight,
    trending_weight=trending_weight,
    filter_stage=combined_filter,
    num_exclude=len(seen_set),
    interest_tags=interest_tags,
)

# ====== FIX: FALLBACK DUY NHẤT ======
# Nếu hết sạch video mới thỏa mãn, cho phép xem lại video cũ (bỏ dedup)
# NHƯNG VẪN PHẢI giữ cường độ (intensity_filter) phù hợp với độ mệt!
if len(docs) == 0 and seen_ids_filter is not None:
    logger.info(
        f"♻️ Feed empty with combined filter "
        f"— dropping dedup filter but KEEPING intensity_filter for user: {user_id}"
    )
    
    # User mệt -> lấy intensity_filter. User bình thường -> thả cửa (None)
    fallback_filter = intensity_filter if intensity_filter is not None else None
    
    docs = await self._fetch_feed(
        interest_vector=interest_vector,
        user_id=user_id,
        limit=limit,
        adaptive_state=adaptive_state,
        search_weight=search_weight,
        trending_weight=trending_weight,
        filter_stage=fallback_filter,
        interest_tags=interest_tags,
    )
# ====================================
```

---

## 4. Tại sao cách này tốt hơn Bản Doc cũ?

1.  **Sửa đúng trọng tâm:** Không cho phép bất cứ video cường độ mạnh nào "lọt lưới" khi user đang uể oải, trực tiếp giải quyết bug.
2.  **Đơn giản, dễ maintain:** Chỉ 1 luồng fallback rất dễ hiểu thay vì phân nhánh rườm rà cho `warning`, `exhausted`, `normal`.
3.  **Hiệu năng:** Bỏ được 1 truy vấn DB vô ích của Fallback 1 cũ, giúp API phản hồi nhanh hơn một chút.
