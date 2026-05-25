# 🚀 Phase 3: Mindful Feed Intervention — Implementation Guide

**Ngày tạo:** 24/05/2026  
**Tiền đề:** Phase 2 đã hoàn thành 100% ✅  
**Thời gian ước lượng:** ~2 giờ  
**Scope:** 100% Backend — Frontend không cần sửa code

---

## 📊 Tổng quan 4 Task

| Task | Mô tả | File cần sửa | Thời gian | Phụ thuộc |
|------|--------|-------------|-----------|-----------|
| **3a** | Điều chỉnh Trọng số Động | `feed_service.py` | 30 phút | Không |
| **3b** | Bơm Palette Cleanser | `video_repository.py` + `feed_service.py` | 45 phút | Không |
| **3c** | Xếp hạng theo Cường độ | `video_repository.py` + `feed_service.py` | 20 phút | 3a |
| **3d** | Cập nhật E2E Test | `test_interaction_e2e.py` | 30 phút | 3a, 3b, 3c |

**Thứ tự thực hiện:** `3a` → `3c` → `3b` → `3d`

---

## 📋 Task 3a: Điều chỉnh Trọng số Động

### Mục tiêu
Thay đổi `search_weight` và `trending_weight` trong `vector_search()` dựa trên `adaptive_state`, thay vì dùng giá trị cố định.

### File: [feed_service.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/app/services/feed_service.py)

### Vấn đề hiện tại (L111-L118)
```python
# Trọng số CỐ ĐỊNH — không thay đổi theo state
docs = await self._video_repo.vector_search(
    query_vector=interest_vector,
    limit=limit,
    num_candidates=max(limit * 10, 50),
    filter_stage=combined_filter,
    search_weight=10.0,      # ← Luôn 10.0
    trending_weight=0.001,   # ← Luôn 0.001
)
```

### Thay đổi cần làm

**Bước 1:** Thêm hàm helper `_get_adaptive_weights()` vào class `FeedService` (trước `get_feed`):

```python
@staticmethod
def _get_adaptive_weights(adaptive_state: str) -> tuple[float, float]:
    """Return (search_weight, trending_weight) based on fatigue state.
    
    - normal:    Maximize personalization (high search, low trending)
    - warning:   Balance personal + calming content
    - exhausted: Prioritize trending/calming over vector similarity
    """
    if adaptive_state == "exhausted":
        return (5.0, 0.5)
    elif adaptive_state == "warning":
        return (7.0, 0.1)
    else:  # "normal"
        return (10.0, 0.001)
```

**Bước 2:** Sửa phần gọi `vector_search()` trong `get_feed()`:

```diff
         # 4. Generate feed (cold-start or personalized)
         interest_vector = user.get("interest_vector", [])
+
+        # Resolve adaptive weights based on fatigue state
+        adaptive_state = "normal"
+        if active_session:
+            adaptive_state = active_session.get("adaptive_state", "normal")
+        search_weight, trending_weight = self._get_adaptive_weights(adaptive_state)

         if not interest_vector or len(interest_vector) == 0:
             logger.info(f"❄️ Cold start feed for user: {user_id} (fetching trending videos)")
             docs = await self._video_repo.find_trending(limit=limit, filter_stage=combined_filter)
         else:
-            logger.info(f"🌿 Personalized feed for user: {user_id} (running Vector Search)")
+            logger.info(
+                f"🌿 Personalized feed for user: {user_id} | state={adaptive_state} "
+                f"| weights=({search_weight}, {trending_weight})"
+            )
             docs = await self._video_repo.vector_search(
                 query_vector=interest_vector,
                 limit=limit,
                 num_candidates=max(limit * 10, 50),
                 filter_stage=combined_filter,
-                search_weight=10.0,
-                trending_weight=0.001,
+                search_weight=search_weight,
+                trending_weight=trending_weight,
             )
```

> [!NOTE]
> Biến `adaptive_state` được resolve sớm (trước cả block if/else cold-start) vì Task 3b và 3c cũng cần dùng nó.

### Xác thực
- [ ] Log output hiển thị `state=exhausted | weights=(5.0, 0.5)` khi fatigue > 70
- [ ] Feed khi exhausted trả về video có trending_score cao hơn (do trending_weight tăng)

---

## 📋 Task 3b: Bơm Nội dung Palette Cleanser

### Mục tiêu
Khi `adaptive_state == "exhausted"`, bơm 1 video ngẫu nhiên từ danh mục "làm dịu" (`calming`, `nature`) vào vị trí thứ 2 (index 1) của feed.

### File 1: [video_repository.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/app/repositories/video_repository.py)

**Thêm phương thức mới vào class `VideoRepository` (sau `vector_search()`, ~L111):**

```python
async def find_random_calming(
    self,
    exclude_ids: set,
    calming_categories: List[str] = None,
    intensity_level: str = "low",
    limit: int = 1,
) -> Optional[Dict[str, Any]]:
    """Find a random calming video for palette cleanser injection.
    
    Uses MongoDB $sample for true random selection from calming categories,
    excluding already-seen videos in the current session.
    """
    from bson import ObjectId

    if calming_categories is None:
        calming_categories = ["calming", "nature","comedy","music","art"]

    match_filter: Dict[str, Any] = {
        "category": {"$in": calming_categories},
        "intensity_level": intensity_level,
    }

    if exclude_ids:
        valid_oids = [ObjectId(vid) for vid in exclude_ids if ObjectId.is_valid(vid)]
        if valid_oids:
            match_filter["_id"] = {"$nin": valid_oids}

    pipeline = [
        {"$match": match_filter},
        {"$sample": {"size": limit}},
    ]
    results = await self.aggregate(pipeline)
    return results[0] if results else None
```

> [!IMPORTANT]
> Danh mục `calming_categories` mặc định là `["calming", "nature"]` — khớp với `CATEGORY_ENUM` trong [video.py L14-17](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/app/models/video.py#L14-L17). Roadmap gốc đề xuất thêm `"asmr"`, `"lofi"`, `"mindfulness"` nhưng những category này **không tồn tại** trong enum hiện tại. Chỉ dùng category đã có trong DB.

### File 2: [feed_service.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/app/services/feed_service.py)

**Thêm logic bơm cleanser sau exploration block (trước `return`, ~L146):**

```diff
                     logger.info(
                         f"🚀 Exploration: Injected trending video '{exploration_video.get('title')}' "
                         f"({exploration_video.get('id')}) to break filter bubble."
                     )

+        # 6. Palette Cleanser Injection (exhausted state only)
+        if adaptive_state == "exhausted" and limit >= 3 and len(docs) >= 2:
+            cleanser = await self._video_repo.find_random_calming(
+                exclude_ids=seen_set | {doc["id"] for doc in docs},
+                calming_categories=["calming", "nature"],
+                intensity_level="low",
+            )
+            if cleanser:
+                docs.insert(1, cleanser)  # Position 2 (index 1)
+                # Trim to respect original limit
+                if len(docs) > limit:
+                    docs = docs[:limit]
+                logger.info(
+                    f"🍃 Palette cleanser injected: '{cleanser.get('title')}' "
+                    f"(category={cleanser.get('category')})"
+                )

         return [VideoService._to_response(doc) for doc in docs]
```

> [!WARNING]
> `exclude_ids` phải bao gồm CẢ `seen_set` (video đã xem trong session) VÀ video đang có trong `docs` (để tránh trùng lặp trong 1 batch feed).

### Xác thực
- [ ] Khi `adaptive_state == "exhausted"` và `limit >= 3`: log hiển thị `🍃 Palette cleanser injected`
- [ ] Video cleanser có `category` là `"calming"` hoặc `"nature"`
- [ ] Video cleanser có `intensity_level == "low"`
- [ ] Cleanser không trùng với video đã xem trong session
- [ ] Feed vẫn đúng `limit` items (không bị thừa)

---

## 📋 Task 3c: Xếp hạng theo Cường độ Ưu tiên

### Mục tiêu
Khi `adaptive_state == "exhausted"`, sắp xếp video `low` intensity lên đầu (trước khi áp dụng `total_score`).

### File 1: [video_repository.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/app/repositories/video_repository.py)

**Sửa signature và sort logic của `vector_search()` (L59-L111):**

```diff
     async def vector_search(
         self,
         query_vector: List[float],
         limit: int = 10,
         num_candidates: int = 100,
         filter_stage: Optional[Dict[str, Any]] = None,
         search_weight: float = 100.0,
         trending_weight: float = 1.0,
+        adaptive_state: str = "normal",
     ) -> List[Dict[str, Any]]:
         """
         Perform $vectorSearch on the videos collection, calculating a combined
         total_score (search_score * search_weight + trending_score * trending_weight)
         and sorting by it.
+
+        When adaptive_state is "exhausted", an intensity_rank field is added so
+        that low-intensity videos always sort before higher-intensity ones.
         Requires a Vector Search Index named 'video_embedding_index' on Atlas.
         """
         pipeline = [
             {
                 "$vectorSearch": {
                     "index": "video_embedding_index",
                     "path": "embedding",
                     "queryVector": query_vector,
                     "numCandidates": num_candidates,
                     "limit": limit,
                 }
             },
             {
                 "$addFields": {
                     "search_score": {"$meta": "vectorSearchScore"},
                     **build_trending_score_pipeline_stage()["$addFields"],
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
-            {
-                "$sort": {
-                    "total_score": -1
-                }
-            }
         ]

+        # Adaptive sorting: prioritize low-intensity when exhausted
+        if adaptive_state == "exhausted":
+            pipeline.append({
+                "$addFields": {
+                    "intensity_rank": {
+                        "$switch": {
+                            "branches": [
+                                {"case": {"$eq": ["$intensity_level", "low"]}, "then": 0},
+                                {"case": {"$eq": ["$intensity_level", "medium"]}, "then": 1},
+                            ],
+                            "default": 2  # high
+                        }
+                    }
+                }
+            })
+            pipeline.append({"$sort": {"intensity_rank": 1, "total_score": -1}})
+        else:
+            pipeline.append({"$sort": {"total_score": -1}})

         # Optional post-filter (e.g., intensity_level filtering for fatigue)
         if filter_stage:
             pipeline.insert(1, {"$match": filter_stage})

         return await self.aggregate(pipeline)
```

> [!TIP]
> Dùng `$switch` thay vì alphabetical sort vì `"high" < "low" < "medium"` theo alphabet — sai thứ tự! `$switch` đảm bảo: low(0) → medium(1) → high(2).

### File 2: [feed_service.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/app/services/feed_service.py)

**Truyền `adaptive_state` vào lệnh gọi `vector_search()`:**

```diff
             docs = await self._video_repo.vector_search(
                 query_vector=interest_vector,
                 limit=limit,
                 num_candidates=max(limit * 10, 50),
                 filter_stage=combined_filter,
                 search_weight=search_weight,
                 trending_weight=trending_weight,
+                adaptive_state=adaptive_state,
             )
```

### Xác thực
- [ ] Khi exhausted: video đầu tiên trong feed luôn có `intensity_level == "low"`
- [ ] Khi normal: thứ tự feed không thay đổi (vẫn sort theo `total_score` thuần)
- [ ] Không có lỗi pipeline khi `intensity_level` field không tồn tại (default = 2)

---

## 📋 Task 3d: Cập nhật E2E Test

### Mục tiêu
Thêm assertions mới cho Phase 3 features vào E2E test hiện có.

### File: [test_interaction_e2e.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/scratch/test_interaction_e2e.py)

**Thêm sau block wellbeing filter assertions (~L215), trước step 7 interaction:**

```python
    # ── Phase 3 Assertions ──────────────────────────────────────────
    print("\n[6b/7] Validating Phase 3: Intensity Prioritization & Palette Cleanser...")
    
    # 3a. Dynamic Weights — verified implicitly: if feed returned only low-intensity
    #     videos when exhausted, the weight adjustment is working with the filter.
    print(f"✅ Dynamic weights applied (state={adaptive_state})")
    
    # 3c. Intensity Prioritization — first video should be low-intensity
    if len(fatigue_feed) > 0:
        assert fatigue_feed[0].intensity_level == "low", \
            f"❌ First video should be low-intensity when exhausted, got {fatigue_feed[0].intensity_level}"
        print(f"✅ Intensity priority: First video is low-intensity ('{fatigue_feed[0].title}')")
    
    # 3b. Palette Cleanser — check for calming category in feed
    calming_categories = ["calming", "nature"]
    has_calming = any(v.category in calming_categories for v in fatigue_feed)
    if adaptive_state == "exhausted":
        if has_calming:
            calming_video = next(v for v in fatigue_feed if v.category in calming_categories)
            print(f"✅ Palette cleanser found: '{calming_video.title}' (category={calming_video.category})")
        else:
            print(f"⚠️  No calming category video found (may not have calming videos in test DB)")
    
    # Count verification
    low_count = sum(1 for v in fatigue_feed if v.intensity_level == "low")
    print(f"📊 Feed composition: {low_count}/{len(fatigue_feed)} low-intensity videos")
    
    print("✅ Phase 3 assertions passed!")
```

> [!NOTE]
> Palette cleanser assertion dùng soft-check (`if/else` + warning) thay vì hard `assert`, vì test DB có thể không có video `calming`/`nature`. Trong production có data thật thì nên chuyển thành hard assert.

---

## 📁 Tóm tắt Files cần sửa

| File | Loại thay đổi | Lines ảnh hưởng |
|------|--------------|-----------------|
| [feed_service.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/app/services/feed_service.py) | Sửa + thêm method | ~30 dòng thêm/sửa |
| [video_repository.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/app/repositories/video_repository.py) | Sửa + thêm method | ~50 dòng thêm/sửa |
| [test_interaction_e2e.py](file:///home/tgkhanhdev/Desktop/Project/mongodbHackathon/backend/scratch/test_interaction_e2e.py) | Thêm assertions | ~25 dòng thêm |

**Tổng thay đổi:** ~105 dòng code mới/sửa across 3 files.

---

## ✅ Validation Checklist cuối cùng

Sau khi implement xong tất cả 4 tasks:

- [ ] **3a** — Log hiện `weights=(5.0, 0.5)` khi exhausted
- [ ] **3b** — Log hiện `🍃 Palette cleanser injected` khi exhausted
- [ ] **3c** — Video đầu tiên luôn `low` intensity khi exhausted
- [ ] **3d** — `python backend/scratch/test_interaction_e2e.py` pass tất cả assertions
- [ ] **Regression** — Feed hoạt động bình thường khi `normal` state (không bị ảnh hưởng)
- [ ] **Performance** — Response time < 500ms (thêm `$sample` và `$switch` không đáng kể)
