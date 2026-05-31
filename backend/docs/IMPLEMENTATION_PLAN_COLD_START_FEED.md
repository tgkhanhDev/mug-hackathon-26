# Implementation Plan: New User Cold-Start Feed (Updated)

## Problem Summary

User mới đăng ký với tags `["game", "dancing"]` nhưng feed lại show `["nature"]` toàn.

**Root Cause (Revised):** Không phải từ `_compute_initial_vector()` fallback, mà từ **Frontend flow**:
- User mới vừa submit form register
- FE **chưa** lưu `interest_tags` vào local state
- FE gọi GET `/feed` với user mới (hoặc token mới)
- Backend thấy `interest_vector = []` (chưa kịp compute)
- Backend trả về `find_trending()` - **trending chung chung**, không phải trending của tags user vừa chọn
- FE nhận feed → show nature videos (vô tình!)

---

## Solution: Feed Service Cold-Start Optimization

### Component 1 (UPDATED): Feed Service - `_fetch_feed()`

**Current behavior:**
```python
async def _fetch_feed(self, interest_vector, user_id, limit, ...):
    if not interest_vector:
        # ❌ Returns trending videos for ALL users
        return await self._video_repo.find_trending(limit=limit, filter_stage=filter_stage)
    else:
        # ✅ Returns personalized feed
        return await self._video_repo.vector_search(...)
```

**New behavior:**
```python
async def _fetch_feed(self, interest_vector, user_id, limit, interest_tags, ...):
    if not interest_vector:
        # ✅ NEW: Check if user has interest_tags → use them for Cold-Start
        if interest_tags and len(interest_tags) > 0:
            logger.info(
                f"❄️ Cold-start feed for user {user_id} using interest_tags: {interest_tags}"
            )
            return await self._video_repo.find_by_tags(
                tags=interest_tags,
                limit=limit,
                filter_stage=filter_stage
            )
        else:
            # Last resort: no vector, no tags → generic trending
            logger.info(f"❄️ Generic trending feed for anonymous user {user_id}")
            return await self._video_repo.find_trending(
                limit=limit,
                filter_stage=filter_stage
            )
    else:
        # ✅ Personalized feed
        return await self._video_repo.vector_search(...)
```

**What changed:**
- Add `interest_tags` parameter to `_fetch_feed()`
- Before falling back to generic `find_trending()`, check if user has `interest_tags`
- If yes → use `find_by_tags(interest_tags)` instead
- If no → use generic trending (true anonymous user or edge case)

---

### Component 2: Feed Service - `get_feed()` (pass tags down)

**Current:**
```python
async def get_feed(self, user_id: str, limit: int = 5, exclude_ids: List[str] = None):
    user = await self._user_repo.find_by_id(user_id)
    ...
    interest_vector = user.get("interest_vector", [])
    ...
    docs = await self._fetch_feed(
        interest_vector=interest_vector,
        user_id=user_id,
        limit=limit,
        ...
    )
```

**Updated:**
```python
async def get_feed(self, user_id: str, limit: int = 5, exclude_ids: List[str] = None):
    user = await self._user_repo.find_by_id(user_id)
    ...
    interest_vector = user.get("interest_vector", [])
    interest_tags = user.get("interest_tags", [])  # ← NEW: Extract tags
    ...
    docs = await self._fetch_feed(
        interest_vector=interest_vector,
        user_id=user_id,
        limit=limit,
        interest_tags=interest_tags,  # ← NEW: Pass tags to _fetch_feed
        ...
    )
```

**What changed:**
- Extract `interest_tags` from user document
- Pass it to `_fetch_feed()` 

---

### Component 3: Auth Service - `_compute_initial_vector()` (NO CHANGE)

**Kept as-is:**
```python
async def _compute_initial_vector(self, interest_tags: List[str]) -> List[float]:
    videos = await self._video_repo.find_by_tags(interest_tags, limit=20)
    embeddings = [v["embedding"] for v in videos if v.get("embedding")]
    
    if embeddings:
        # Average vectors from matching videos
        return L2_normalize(avg_vector)
    else:
        # Fallback: Text embedding (fine as fallback, not primary issue)
        return L2_normalize(generate_embedding(f"User interests: {', '.join(interest_tags)}"))
```

**Why kept:**
- This eventually computes a proper vector, but it's async
- Takes time for scheduler to run
- Current issue is immediate: user gets wrong feed BEFORE vector is computed

---

### Component 4: Fatigue Score & Palette Cleanser (NO CHANGE)

Both kept as-is:
- `_get_adaptive_weights()` - returns (search_weight, trending_weight) based on fatigue state
- Palette cleanser injection logic - injects calming videos when exhausted/critical

**Why:**
- These address a different problem (wellbeing)
- No side effects on cold-start flow
- Fatigue score updates independently

---

## Data Flow (After Fix)

```
User registers with tags: ["game", "dancing"]
    ↓
BE saves: user { interest_tags: ["game", "dancing"], interest_vector: [] }
    ↓
FE calls: GET /api/v1/feed
    ↓
get_feed(user_id):
  - Fetch user document
  - Extract: interest_tags = ["game", "dancing"], interest_vector = []
  - Call _fetch_feed(..., interest_tags=["game", "dancing"], ...)
    ↓
_fetch_feed():
  - Check: interest_vector empty? YES
  - Check: interest_tags non-empty? YES
  - Call: find_by_tags(["game", "dancing"])
    ↓
find_by_tags():
  - Query: db.videos.find({tags: {$in: ["game", "dancing"]}})
  - Sort by trending_score DESC
  - Return top 5 videos
    ↓
FE receives CORRECT recommendations ✅ (game/dancing videos)
```

---

## Files to Modify

### 1️⃣ `/app/services/feed_service.py`

**Lines to change:** ~160-270 (get_feed + _fetch_feed methods)

**Changes:**
- Line ~162: Extract `interest_tags = user.get("interest_tags", [])`
- Line ~165-175: Pass `interest_tags` to `_fetch_feed()` call
- Line ~245-260: Update `_fetch_feed()` signature to accept `interest_tags`
- Line ~265-275: Add conditional logic:
  ```python
  if not interest_vector:
      if interest_tags:
          # Use tags-based cold-start
          return await self._video_repo.find_by_tags(...)
      else:
          # Generic trending
          return await self._video_repo.find_trending(...)
  ```

---

## Implementation Steps

### Step 1: Update `get_feed()` method
- Extract `interest_tags` from user document
- Add `interest_tags` to `_fetch_feed()` calls (including all fallback paths)

### Step 2: Update `_fetch_feed()` method signature
- Add parameter: `interest_tags: List[str] = None`
- Add logic to check `interest_tags` before falling back to generic trending

### Step 3: Test
- Register new user with `["game", "dancing"]`
- Get feed immediately (before vector computation finishes)
- Verify: Feed contains game/dancing videos, not nature
- Verify: Existing behavior unchanged for users with non-empty `interest_vector`

### Step 4: Verify no regression
- Users with existing vectors still get personalized feed ✅
- Fatigue score still works independently ✅
- Palette cleanser still injects appropriately ✅

---

## Code Changes Summary

| File | Method | Change Type | Impact |
|------|--------|------------|--------|
| `feed_service.py` | `get_feed()` | Extract + Pass tags | Non-breaking |
| `feed_service.py` | `_fetch_feed()` | Add conditional logic | Non-breaking |
| `user_service.py` | `_compute_initial_vector()` | None | - |
| `interaction_service.py` | All methods | None | - |

---

## Risk Assessment

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| Breaking existing personalized feed | ✅ Very Low | Logic only triggers when vector is empty (new users) |
| `find_by_tags()` returns no results | 🟡 Medium | Falls back to generic trending (same as before) |
| Memory/performance | ✅ Very Low | Same DB query complexity as before |

---

## Edge Cases Handled

| Scenario | Current | After Fix |
|----------|---------|-----------|
| New user, has tags, no vector | ❌ Generic trending | ✅ Tags-based cold-start |
| New user, no tags, no vector | ✅ Generic trending | ✅ Generic trending (unchanged) |
| User with vector | ✅ Vector search | ✅ Vector search (unchanged) |
| Videos with matching tags don't exist | ✅ find_by_tags() returns empty | ✅ Falls back to generic trending |
| Fatigue state = exhausted | ✅ Applies intensity filter + palette cleanser | ✅ Still works (applied after cold-start) |

---

## Timeline

- **Implementation:** ~1 hour
- **Testing:** ~30 minutes
- **Total:** ~1.5 hours

---

## Why This Approach?

✅ **Minimal change:** Only 2 methods modified  
✅ **Non-breaking:** Doesn't affect existing users or logic  
✅ **Quick fix:** Immediate improvement for new users  
✅ **Doesn't block:** Scheduler continues to compute proper vectors in background  
✅ **Addresses root cause:** Uses user's own tags for cold-start, not generic trending  

---

## Approval Checklist

- [ ] Review implementation plan above
- [ ] Confirm changes look correct
- [ ] Ready to implement?
