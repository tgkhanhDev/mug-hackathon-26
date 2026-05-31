# 🐛 Fatigue Engine Intensity Filter Bug Fix Plan

**Phiên bản:** v1  
**Ngày:** 31 Tháng 5, 2026  
**Priority:** HIGH  
**Status:** Pending Implementation

---

## 📋 Executive Summary

**Bug:** Khi fatigue_score >= 40% (state = "warning"), backend NẲY LẦN SẮP filter để lấy video `intensity_level: ["low", "medium"]` + category nhẹ nhàng, nhưng vẫn trả về **video high-intensity** (gaming, sports, etc.).

**Root Cause:** Progressive fallback logic trong `feed_service.py` **bỏ đi intensity filter** khi không tìm thấy đủ videos, thay vì giữ nguyên filter.

**Impact:** Người dùng uể (fatigue >= 40%) vẫn nhận được content nặng → fatigue tăng thêm → vòng lặp tiêu cực.

---

## 🔍 Root Cause Analysis

### Hiện tại (Line 192-215 in `backend/app/services/feed_service.py`)

```python
# Step 1: Fetch with intensity + dedup filters
if len(docs) == 0:
    docs = await self._fetch_feed(
        user_id=user_id,
        query_vector=interest_vector,
        limit=limit,
        filter_stage={"$and": [dedup_filter, intensity_filter]},  # ← intensity + dedup
    )

# Step 2: FALLBACK 1 - Nếu không đủ, BỎ intensity filter (⚠️ BUG!)
if len(docs) < limit and intensity_filter is not None:
    logger.warning(f"Insufficient with intensity filter, falling back...")
    docs = await self._fetch_feed(
        user_id=user_id,
        query_vector=interest_vector,
        limit=limit,
        filter_stage=seen_ids_filter,  # ← NỪ intensity_filter, chỉ còn dedup!
    )

# Step 3: FALLBACK 2 - Nếu vẫn không đủ, BỎ luôn filter (⚠️ CRITICAL BUG!)
if len(docs) == 0 and seen_ids_filter is not None:
    logger.warning(f"User has seen all available videos, showing unseen...")
    docs = await self._fetch_feed(
        user_id=user_id,
        query_vector=interest_vector,
        limit=limit,
        filter_stage=None,  # ← NO FILTER = CAN RETURN HIGH-INTENSITY GAMING VIDEOS!
    )
```

### Vấn đề

| Bước | Điều kiện | Filter được áp dụng | ⚠️ Vấn đề |
|------|-----------|-------------------|---------|
| 1 | `adaptive_state == "warning"` | `intensity: ["low", "medium"]` + dedup | ✅ Đúng |
| 2 | Không đủ videos từ Step 1 | Chỉ dedup (BỎ intensity) | ⚠️ Có thể trả high-intensity |
| 3 | Vẫn không đủ từ Step 2 | Không filter | 🔴 Chắc chắn trả high-intensity |

**Ví dụ kịch bản:**
```
1. User fatigue = 45% → state = "warning"
2. System tìm kiếm 5 videos với intensity: ["low", "medium"]
3. DB chỉ có 2 videos low-intensity (không đủ 5)
4. Fallback 1: Bỏ intensity filter, tìm 5 videos bất kỳ
5. Database trả: 3 low + 2 HIGH-INTENSITY (gaming) ❌
6. User nhận feed toàn gaming → fatigue tăng lên → vòng lặp tiêu cực
```

---

## 🎯 Solution Analysis

### Option A: Never Drop Intensity Filter (Recommended)

**Idea:** Thay vì drop intensity filter, luôn giữ nó. Nếu không tìm đủ, chỉ trả ít hơn.

```python
# Fallback 1: Không đủ?
if len(docs) < limit and intensity_filter is not None:
    # ❌ TRƯỚC: BỎ intensity filter
    # ✅ SAU: Giữ intensity filter, trả ít hơn
    logger.info(f"Found {len(docs)}/{limit} videos with intensity filter (OK)")
    # Không fetch lại. Trả những gì có.
    pass

# Fallback 2: Rỗng hoàn toàn?
if len(docs) == 0 and seen_ids_filter is not None:
    # ❌ TRƯỚC: BỎ luôn filter
    # ✅ SAU: Giữ intensity filter, fallback chỉ bỏ dedup (seen videos có thể được show lại)
    logger.warning(f"No unseen videos with intensity filter. Showing seen videos (same intensity)...")
    docs = await self._fetch_feed(
        user_id=user_id,
        query_vector=interest_vector,
        limit=limit,
        filter_stage=intensity_filter,  # ← KEEP intensity_level filter!
    )
```

**Pros:**
- Bảo vệ người dùng uể khỏi high-intensity content
- Logic rõ ràng: "intensity filter bao giờ cũng được giữ"

**Cons:**
- Có thể trả feed ít hơn (ví dụ 2 videos thay vì 5)
- Frontend cần xử lý trường hợp feed = 0

---

### Option B: Adaptive Intensity Relaxation

**Idea:** Thay vì drop intensity filter = bỏ ngay, giảm dần mức intensity.

```python
# Fallback 1: "warning" → relax thành inclusive (low + medium + high)
if len(docs) < limit and adaptive_state == "warning":
    relaxed_filter = {"intensity_level": {"$in": ["low", "medium", "high"]}}
    docs = await self._fetch_feed(
        user_id=user_id,
        query_vector=interest_vector,
        limit=limit,
        filter_stage={"$and": [dedup_filter, relaxed_filter]},  # ← relax, not drop
    )

# Fallback 2: "exhausted" → vẫn giữ low
if len(docs) < limit and adaptive_state == "exhausted":
    # KHÔNG fallback, giữ low-intensity filter nguyên
    logger.info(f"Exhausted state: keeping intensity=low filter")
    pass
```

**Pros:**
- Smooth gradient: low → (low+medium) → (low+medium+high)
- Theo state tự động relax

**Cons:**
- Phức tạp hơn Option A
- Vẫn có thể trả high-intensity nếu exhausted state relax quá

---

### ✅ Khuyến nghị

**Đề xuất: Option A + B kết hợp**

```
State = "warning" (fatigue 40-70%)
  → Fallback 1: Giữ intensity ["low", "medium"]
  → Fallback 2: Relax thành ["low", "medium", "high"] + kéo lại seen videos
  
State = "exhausted" (fatigue >= 80%)
  → Fallback 1: Giữ intensity ["low"]
  → Fallback 2: Không fallback, trả ít hơn
  
State = "critical" (fatigue >= 90%)
  → Fallback 1: Giữ intensity ["low"] + palette cleanser mandatory
  → Fallback 2: Không fallback, trả ít hơn
```

---

## 📌 Implementation Plan

### Bước 1: Cập nhật feed_service.py - Refactor fallback logic

**File:** `backend/app/services/feed_service.py`

**Hiện tại (Line 185-215):**

```python
# Step 1: Try with intensity filter + dedup
docs = await self._fetch_feed(...)

# Step 2: PROBLEMATIC - Drops intensity filter
if len(docs) < limit and intensity_filter is not None:
    docs = await self._fetch_feed(
        ...,
        filter_stage=seen_ids_filter,  # ⚠️ BUG
    )

# Step 3: PROBLEMATIC - No filter at all
if len(docs) == 0 and seen_ids_filter is not None:
    docs = await self._fetch_feed(
        ...,
        filter_stage=None,  # ⚠️ CRITICAL BUG
    )
```

**Thay đổi thành (Proposed):**

```python
# Step 1: Try with intensity filter + dedup
docs = await self._fetch_feed(
    user_id=user_id,
    query_vector=interest_vector,
    limit=limit,
    filter_stage=combined_filter,  # intensity_level + dedup
    search_weight=search_weight,
    trending_weight=trending_weight,
    adaptive_state=adaptive_state,
)

# Step 2: Adaptive Fallback - Keep intensity, but relax if needed
if len(docs) < limit and intensity_filter is not None:
    if adaptive_state == "warning":
        # Relax: allow medium-intensity too
        relaxed_intensity = {"intensity_level": {"$in": ["low", "medium", "high"]}}
        logger.info(f"Fallback Step 2 (warning): Relax intensity to include all levels")
        docs.extend(await self._fetch_feed(
            user_id=user_id,
            query_vector=interest_vector,
            limit=limit - len(docs),
            filter_stage={"$and": [dedup_filter, relaxed_intensity]},
            search_weight=search_weight,
            trending_weight=trending_weight,
            adaptive_state=adaptive_state,
        ))
    elif adaptive_state in ["exhausted", "critical"]:
        # Keep intensity=["low"], don't relax
        logger.info(f"Fallback Step 2 ({adaptive_state}): Keep intensity=low, show seen videos")
        docs.extend(await self._fetch_feed(
            user_id=user_id,
            query_vector=interest_vector,
            limit=limit - len(docs),
            filter_stage=intensity_filter,  # ← KEEP intensity filter
            search_weight=search_weight,
            trending_weight=trending_weight,
            adaptive_state=adaptive_state,
        ))
    else:  # "normal"
        # No intensity filter restriction
        logger.info(f"Fallback Step 2 (normal): No intensity filter")
        docs.extend(await self._fetch_feed(
            user_id=user_id,
            query_vector=interest_vector,
            limit=limit - len(docs),
            filter_stage=seen_ids_filter,
            search_weight=search_weight,
            trending_weight=trending_weight,
            adaptive_state=adaptive_state,
        ))

# Step 3: Enforce Palette Cleanser EVEN IF small feed
if len(docs) > 0 and adaptive_state in ["exhausted", "critical"]:
    cleanser = await self._video_repo.find_random_calming(
        exclude_ids=seen_set | {doc["id"] for doc in docs},
        calming_categories=["calming", "nature"],
        intensity_level="low",
    )
    if cleanser:
        # Insert at position 1 even if feed only has 1 video
        insert_pos = min(1, len(docs))
        docs.insert(insert_pos, cleanser)
        logger.info(f"Palette cleanser injected at position {insert_pos}")
```

---

### Bước 2: Thêm logging cho debugging

**File:** `backend/app/services/feed_service.py`

Thêm chi tiết logs tại mỗi fallback stage:

```python
# Before Step 1
logger.info(
    f"get_feed() START: "
    f"user={user_id}, "
    f"state={adaptive_state}, "
    f"fatigue={existing_fatigue_state.fatigue_score:.1f}%, "
    f"intensity_filter={intensity_filter}, "
    f"limit={limit}"
)

# After Step 1
logger.info(f"Step 1 result: {len(docs)} videos (intensity + dedup)")

# After Step 2
logger.info(f"Step 2 result: {len(docs)} videos total (after fallback)")

# After Step 3 (cleanser)
logger.info(f"Step 3 result: {len(docs)} videos (after cleanser injection)")

# Final
logger.info(f"get_feed() END: returning {len(docs)} videos")
```

---

### Bước 3: Thêm unit test

**File:** `backend/tests/test_feed_intensity_filter.py` (new)

```python
import pytest
from app.services.feed_service import FeedService
from app.utils.formula.fatigue import determine_adaptive_state

@pytest.mark.asyncio
async def test_feed_preserves_low_intensity_on_warning_state():
    """
    When fatigue = 45% (warning state), feed should:
    1. Prioritize low + medium intensity videos
    2. NEVER fallback to high-intensity videos
    """
    feed_service = FeedService()
    
    # Simulate user with warning fatigue
    user_id = "test_user_warning"
    fatigue_score = 45.0  # warning state
    adaptive_state = determine_adaptive_state(fatigue_score)
    
    assert adaptive_state == "warning"
    
    # Get feed
    docs = await feed_service.get_feed(
        user_id=user_id,
        adaptive_state=adaptive_state,
        limit=5,
    )
    
    # Assert: ALL videos should be low or medium intensity
    for doc in docs:
        intensity = doc.get("intensity_level", "unknown")
        assert intensity in ["low", "medium"], \
            f"Warning state returned high-intensity video: {doc['_id']}"

@pytest.mark.asyncio
async def test_feed_never_drops_intensity_on_exhausted():
    """
    When fatigue >= 80% (exhausted), feed should:
    1. Only return low-intensity videos
    2. Never fallback to medium/high
    """
    feed_service = FeedService()
    
    user_id = "test_user_exhausted"
    fatigue_score = 85.0  # exhausted state
    adaptive_state = determine_adaptive_state(fatigue_score)
    
    assert adaptive_state == "exhausted"
    
    docs = await feed_service.get_feed(
        user_id=user_id,
        adaptive_state=adaptive_state,
        limit=5,
    )
    
    # Assert: ALL videos should be low intensity only
    for doc in docs:
        intensity = doc.get("intensity_level", "unknown")
        assert intensity == "low", \
            f"Exhausted state returned non-low video: {doc['_id']}"

@pytest.mark.asyncio
async def test_palette_cleanser_injected_even_for_small_feed():
    """Palette cleanser should be injected even if main feed = 1 video"""
    feed_service = FeedService()
    
    user_id = "test_user_small_feed"
    fatigue_score = 85.0  # exhausted
    adaptive_state = "exhausted"
    
    docs = await feed_service.get_feed(
        user_id=user_id,
        adaptive_state=adaptive_state,
        limit=5,
    )
    
    # If we got any videos, check for palette cleanser at position 1
    if len(docs) >= 2:
        # docs[0] = main video
        # docs[1] = cleanser (if injected)
        cleanser_candidate = docs[1]
        assert cleanser_candidate.get("category") in ["calming", "nature"], \
            f"Palette cleanser at pos 1 should be calming, got: {cleanser_candidate}"
```

---

### Bước 4: Verify Database

**File:** `backend/docs/FATIGUE_ENGINE_INTENSITY_FILTER_BUG_FIX_PLAN.md`

Cần check MongoDB queries:

```javascript
// 1. Check có bao nhiêu videos has intensity_level
db.videos.aggregate([
  { $group: { _id: "$intensity_level", count: { $sum: 1 } } }
])

// Output expected:
// { _id: "low", count: 1000 }
// { _id: "medium", count: 500 }
// { _id: "high", count: 200 }

// 2. Check calming category videos
db.videos.aggregate([
  { $match: { category: { $in: ["calming", "nature"] } } },
  { $group: { _id: "$intensity_level", count: { $sum: 1 } } }
])

// 3. Check gaming/sports category (should be high intensity)
db.videos.aggregate([
  { $match: { category: { $in: ["gaming", "sports"] } } },
  { $group: { _id: "$intensity_level", count: { $sum: 1 } } }
])
```

Nếu:
- Low-intensity videos < 50 → database setup không tối ưu
- Gaming/sports videos = high intensity → Tốt
- Calming/nature = mostly low intensity → Tốt

---

## ✅ Acceptance Criteria

| Criteria | Trạng thái | Ghi chú |
|----------|-----------|--------|
| Fallback logic trong `feed_service.py` được refactor | ✅ Required | Line 185-220 |
| `adaptive_state == "warning"` KHÔNG drop intensity filter | ✅ Required | Fallback 1 relax thành all levels |
| `adaptive_state == "exhausted"` KHÔNG drop intensity filter | ✅ Required | Fallback 1 giữ nguyên low |
| Palette cleanser inject ngay cả nếu feed size = 1 | ✅ Required | Loại bỏ `len(docs) >= 2` guard |
| Unit tests pass (test_feed_intensity_filter.py) | ✅ Required | 3 test cases trên |
| E2E test: doomscroll tới exhausted state → verify intensity | ✅ Verification | DevTools Network |
| Logs rõ ràng khi fallback xảy ra | ✅ Required | Dùng cho debugging |

---

## 🔄 Verification Flow

### Bước 1: Trigger fatigue tới "warning" (40%)

```bash
# On frontend console (simulated doomscroll)
for (let i = 0; i < 50; i++) {
  // Simulate 50 quick skips
}
// Watch API: fatigue_score should be ~45%
```

Check DVT (Network) → `/feed` response:
- ✅ BEFORE: High-intensity videos (gaming, sports)
- ✅ AFTER: Low + medium-intensity videos (calming, comedy)

### Bước 2: Trigger tới "exhausted" (80%)

```bash
# Continue doomscroll
for (let i = 0; i < 100; i++) {
  // Simulate more skips
}
// fatigue_score should be ~85%
```

Check DevTools → `/feed` response:
- ✅ BEFORE: Any intensity videos
- ✅ AFTER: Only low-intensity videos + palette cleanser at position 1-2

### Bước 3: Verify no high-intensity in exhausted state

Run e2e test:
```bash
cd backend
pytest tests/test_feed_intensity_filter.py -v
```

Expected: ✅ All 3 tests pass

---

## 📊 Implementation Timeline

| Task | Complexity | Time | Dependencies |
|------|-----------|------|--------------|
| Refactor fallback logic (Step 1) | Medium | 1 hour | None |
| Add logging (Step 2) | Low | 15 min | Step 1 |
| Write unit tests (Step 3) | Medium | 45 min | Step 1-2 |
| Verify DB setup (Step 4) | Low | 20 min | None |
| E2E verification | Low | 30 min | All steps |
| **TOTAL** | | **~2.5 hours** | |

---

## 🛠️ Files to Modify

| File | Changes | Location |
|------|---------|----------|
| `backend/app/services/feed_service.py` | Refactor fallback logic + logging | Line 185-220 |
| `backend/tests/test_feed_intensity_filter.py` | New unit tests | New file |
| `backend/docs/FATIGUE_ENGINE_INTENSITY_FILTER_BUG_FIX_PLAN.md` | This file | New file |

---

## 🚀 Next Steps

1. ✅ Review implementation plan
2. ✅ Approve approach (Option A, Option B, or Hybrid)
3. 📝 Start from **Bước 1: Refactor fallback logic**
4. ✅ Run unit tests after each step
5. ✅ E2E verification on browser

---

## 📚 Related Documents

- [fatigue_engine_flow.md](fatigue_engine_flow.md) - Fatigue mechanics
- [aggregation_pipeline_guide.md](aggregation_pipeline_guide.md) - Vector search + trending
- [interaction_flow_guide.md](interaction_flow_guide.md) - Interaction tracking

