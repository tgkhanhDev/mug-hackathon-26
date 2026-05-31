# 🔄 Fatigue Engine Topic Diversification Fix Plan
**Ngày:** 31/05/2026  
**Vấn đề:** Khi fatigue ≥ 40%, nếu topic ưa thích của user không có video, feed không trả về video nào  
**Giải pháp:** Fallback topic diversification - ưu tiên topic user yêu thích trước, nếu không đủ thì fetch thêm từ các topic khác

---

## I. Phân Tích Bug Hiện Tại

### Root Cause
```
📍 Location: backend/app/services/feed_service.py (dòng 136-205)

Dòng 165: docs = await self._fetch_feed(
          interest_vector=interest_vector,  ← CHỈ dùng vector sở thích user
          filter_stage=combined_filter      ← Intensity + Dedup
)

❌ PROBLEM: 
- Nếu user's interest_vector không khớp với video nào có intensity thấp/trung bình
- hoặc topic ưa thích không có video nào
- → vector search trả về 0 kết quả
- → Fallback 1 (dòng 169): Xóa intensity_filter, chỉ giữ dedup
  → LẠI TÌM KHÔNG ĐƯỢC (vì vector search vẫn ưu tiên interest_vector)
- → Fallback 2 (dòng 181): Xóa cả dedup, trả video bất kỳ
  → GHI NHỀ: Video có thể là high-intensity gaming/sports (SAI với cách xử lý fatigue)
```

### Ứng xử Hiện Tại vs Mong Muốn

| Scenario | Hiện Tại | Mong Muốn |
|----------|----------|----------|
| **User yêu 'Nature' videos, fatigue=45%** | ✅ Fetch nature (low/medium intensity) | ✅ Same |
| **'Nature' topic hết video** | ❌ Trả high-intensity gaming | ✅ Fallback: Fetch trending (low/medium) từ topic khác |
| **User chưa có interest_vector (cold-start)** | ✅ Trending videos | ✅ Same |
| **Hết sạch video thỏa mãn** | ⚠️ Trả video cũ hoặc high-intensity | ✅ Trả video cũ nhưng luôn ≤ medium intensity |

---

## II. Giải Pháp: Topic Diversification Fallback

### 2.1 Chiến Lược Chính

```
┌─────────────────────────────────────────────────────────────┐
│ GET /feed (user_id, limit=5)                                │
└─────────────────────────────────────────────────────────────┘
              ↓
  ┌─ fatigue < 40%? → Normal feed (full vectorSearch)        │
  │                → No intensity filter                     │
  │                                                           │
  └─ fatigue ≥ 40%? → WARNING FEED (Topic Diversification)   │
                 ↓
        [STEP 1] Preferred Topics
        ┌──────────────────────────┐
        │ Vector Search with        │
        │ - interest_vector        │
        │ - intensity: [low, med]  │
        │ - dedup: seen videos     │
        └──────────────────────────┘
                 ↓
         Return < limit videos?
         ├─ NO: Return ✅
         └─ YES:  [STEP 2] Topic Diversification
                  ┌──────────────────────────────┐
                  │ Trending Videos (Other Topics)│
                  │ - EXCLUDE: Preferred Topics  │
                  │ - intensity: [low, med]      │
                  │ - EXCLUDE: Preferred results │
                  │ needed = limit - len(docs)   │
                  └──────────────────────────────┘
                           ↓
                  gap_count = 0?
                  ├─ NO: Merge + Return ✅
                  └─ YES: [STEP 3] Dedup Fallback
                         ┌──────────────────────┐
                         │ Repeat Step 1 + 2    │
                         │ WITHOUT dedup filter │
                         │ (allow seen videos)  │
                         └──────────────────────┘
                          ↓
                  Still gap? Return merged
```

### 2.2 Chi Tiết Các Bước

#### Step 1: Preferred Topics (Hiện tại)
```python
# Fetch từ user's interest_vector
docs_preferred = await self._fetch_feed(
    interest_vector=interest_vector,
    limit=limit,
    filter_stage=combined_filter,  # intensity + dedup
    adaptive_state=adaptive_state,
    ...
)
# Kết quả: 0-limit videos từ topic user yêu thích
```

#### Step 2: Topic Diversification (MỚI)
```python
if len(docs_preferred) < limit and adaptive_state in ["warning"]:
    needed = limit - len(docs_preferred)
    
    # Fetch trending videos NGOÀI preferred topics
    exclude_preferred_ids = extract_tags_from(docs_preferred)  # hoặc vector similarity threshold
    
    docs_diversified = await self._fetch_trending_diverse(
        limit=needed,
        exclude_category_tags=exclude_preferred_ids,  # Don't repeat user's topics
        intensity_filter=intensity_filter,  # ALWAYS keep intensity at warning state
        exclude_ids=seen_set,  # Dedup
    )
    
    docs = docs_preferred + docs_diversified
```

#### Step 3: Dedup Fallback (Nếu Step 2 vẫn không đủ)
```python
if len(docs) < limit:
    needed = limit - len(docs)
    
    # Repeat Step 1 + 2 nhưng WITHOUT dedup
    docs_repeat_preferred = await self._fetch_feed(
        interest_vector=interest_vector,
        limit=needed,
        filter_stage=intensity_filter,  # Drop dedup, keep intensity
        ...
    )
    
    if len(docs_repeat_preferred) < needed:
        docs_repeat_diverse = await self._fetch_trending_diverse(
            limit=needed - len(docs_repeat_preferred),
            exclude_category_tags=exclude_preferred_ids,
            intensity_filter=intensity_filter,
            exclude_ids=None,  # Allow repeats
        )
        docs.extend(docs_repeat_diverse)
    else:
        docs.extend(docs_repeat_preferred[:needed])
```

---

## III. Implementation Details

### 3.1 New Helper Method: `_fetch_trending_diverse()`

```python
async def _fetch_trending_diverse(
    self,
    limit: int,
    exclude_category_tags: Optional[List[str]],
    intensity_filter: Optional[Dict[str, Any]],
    exclude_ids: Optional[set],
) -> List[Dict[str, Any]]:
    """
    Fetch trending videos EXCLUDING user's preferred topics.
    Used for topic diversification when preferred topics are exhausted.
    
    Args:
        limit: Number of videos to fetch
        exclude_category_tags: Tags/categories to EXCLUDE (user's preferred topics)
        intensity_filter: Intensity level constraint ({"$in": ["low", "medium"]})
        exclude_ids: Videos to exclude (seen videos) - can be None for repeat fallback
    
    Returns:
        List of trending videos from other categories
    """
    match_filter = {"status": "completed"}
    
    # Keep intensity filter at warning state
    if intensity_filter:
        match_filter = {"$and": [match_filter, intensity_filter]}
    
    # Exclude preferred topics (e.g., if user watched 'nature', don't give more nature)
    if exclude_category_tags and len(exclude_category_tags) > 0:
        match_filter = {
            "$and": [
                match_filter,
                {"tags": {"$nin": exclude_category_tags}}  # Tags outside preferred
            ]
        }
    
    # Dedup if provided
    if exclude_ids:
        from bson import ObjectId
        valid_oids = [ObjectId(vid) for vid in exclude_ids if ObjectId.is_valid(vid)]
        if valid_oids:
            match_filter = {
                "$and": [match_filter, {"_id": {"$nin": valid_oids}}]
            }
    
    pipeline = [
        {"$match": match_filter},
        build_trending_score_pipeline_stage(),
        {"$sort": {"trending_score": -1}},
        {"$limit": limit}
    ]
    
    return await self.aggregate(pipeline)
```

### 3.2 Modify `get_feed()` to Use Topic Diversification

**Location:** `backend/app/services/feed_service.py` (Line 136-205)

```python
async def get_feed(self, user_id: str, limit: int = 5, exclude_ids: List[str] = None):
    """..."""
    # ... [Lines 75-155: Existing code unchanged] ...
    
    # 4. Generate feed with topic diversification for warning state (≥40% fatigue)
    interest_vector = user.get("interest_vector", [])
    interest_tags = user.get("interest_tags", [])
    search_weight, trending_weight = self._get_adaptive_weights(adaptive_state)

    # STEP 1: Fetch from preferred topics
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

    # STEP 2: Topic Diversification Fallback (NEW for warning state)
    if (
        len(docs) < limit
        and adaptive_state == "warning"
        and interest_vector  # Only if user has preferences
    ):
        needed = limit - len(docs)
        preferred_tags = interest_tags or []  # Extract tags from interest_vector if exists
        
        logger.info(
            f"🔄 Topic diversification (warning state): "
            f"Need {needed} more videos. excluding preferred_tags={preferred_tags}"
        )
        
        docs_diverse = await self._fetch_trending_diverse(
            limit=needed,
            exclude_category_tags=preferred_tags,
            intensity_filter={"intensity_level": {"$in": ["low", "medium"]}},
            exclude_ids=seen_set,  # Keep dedup
        )
        
        docs.extend(docs_diverse)
        logger.info(
            f"✨ Diversified feed: added {len(docs_diverse)}/{needed} diverse videos. "
            f"Total now: {len(docs)}/{limit}"
        )

    # STEP 3: Dedup Fallback (if still not enough)
    if len(docs) == 0 and seen_ids_filter is not None:
        logger.info(
            f"♻️ Feed empty - allowing seen videos but keeping intensity_filter: {user_id}"
        )
        
        # Repeat both steps 1 & 2 without dedup
        fallback_filter = intensity_filter if intensity_filter else None
        
        docs_repeat = await self._fetch_feed(
            interest_vector=interest_vector,
            user_id=user_id,
            limit=limit,
            adaptive_state=adaptive_state,
            search_weight=search_weight,
            trending_weight=trending_weight,
            filter_stage=fallback_filter,
            interest_tags=interest_tags,
        )
        docs.extend(docs_repeat)
        
        # Also try topic diversification without dedup
        if len(docs) < limit:
            needed = limit - len(docs)
            docs_diverse_repeat = await self._fetch_trending_diverse(
                limit=needed,
                exclude_category_tags=interest_tags or [],
                intensity_filter=intensity_filter,
                exclude_ids=None,  # Allow repeats
            )
            docs.extend(docs_diverse_repeat)

    # 5. Exploration Factor (existing code)
    if interest_vector and active_session and limit >= 3 and len(docs) > 0:
        # ... [existing code unchanged] ...

    # 6. Palette Cleanser Injection (existing code)
    if adaptive_state in ["exhausted", "critical"] and limit >= 3 and len(docs) >= 2:
        # ... [existing code unchanged] ...

    return [VideoService._to_response(doc) for doc in docs]
```

---

## IV. New VideoRepository Method

**Location:** `backend/app/repositories/video_repository.py`

```python
async def _fetch_trending_diverse(
    self,
    limit: int,
    exclude_category_tags: Optional[List[str]],
    intensity_filter: Optional[Dict[str, Any]],
    exclude_ids: Optional[set],
) -> List[Dict[str, Any]]:
    """Fetch trending videos excluding preferred topics (for topic diversification)."""
    match_filter = {"status": "completed"}
    
    if intensity_filter:
        match_filter = {"$and": [match_filter, intensity_filter]}
    
    if exclude_category_tags and len(exclude_category_tags) > 0:
        match_filter = {
            "$and": [
                match_filter,
                {"tags": {"$nin": exclude_category_tags}}
            ]
        }
    
    if exclude_ids:
        from bson import ObjectId
        valid_oids = [ObjectId(vid) for vid in exclude_ids if ObjectId.is_valid(vid)]
        if valid_oids:
            match_filter = {
                "$and": [
                    match_filter,
                    {"_id": {"$nin": valid_oids}}
                ]
            }
    
    pipeline = [
        {"$match": match_filter},
        build_trending_score_pipeline_stage(),
        {"$sort": {"trending_score": -1}},
        {"$limit": limit}
    ]
    
    return await self.aggregate(pipeline)
```

---

## V. Test Cases

### Test Case 1: Normal State (Fatigue < 40%)
```
Input: user_id, fatigue=35%, interest_vector=[...], preferred_topics=['nature']
Expected: Regular vector search → nature videos + 1 exploration video
Verify: Topic diversification NOT triggered
```

### Test Case 2: Warning State - Preferred Topics Available
```
Input: fatigue=50%, interest_vector=[...], preferred_topics=['nature']
DB: nature + low/medium intensity videos = 8
Expected: Return 5 nature videos
Verify: NO diversification needed, logs show no diversification triggered
```

### Test Case 3: Warning State - Preferred Topics Exhausted
```
Input: fatigue=50%, interest_vector=[...], preferred_topics=['nature']
DB: nature + low/medium = 2 videos (user seen both)
Other topics + low/medium = 10 videos (unseen)
Expected: 2 nature videos + 3 other topic videos (trending)
Verify: Step 2 triggered, diverse videos injected with correct intensity
```

### Test Case 4: Warning State - Zero Preferred Fallback
```
Input: fatigue=50%, interest_vector=[...], preferred_topics=['nature']
DB: nature + low/medium = 0 videos
Other topics + low/medium = 5 videos
Expected: 5 other topic videos
Verify: Both steps 1 & 2 triggered, returns diversified feed
```

### Test Case 5: Exhausted State (Fatigue > 70%)
```
Input: fatigue=75%, adaptive_state='exhausted'
Expected: NO topic diversification (only palette cleanser)
Verify: Diversification logic skipped for 'exhausted' state
```

---

## VI. Files to Modify

| File | Changes | Lines |
|------|---------|-------|
| `backend/app/services/feed_service.py` | Add topic diversification fallback in `get_feed()` | 136-205 |
| `backend/app/repositories/video_repository.py` | Add new method `_fetch_trending_diverse()` | New method |

---

## VII. Logging & Monitoring

Thêm logs để track topic diversification:

```python
logger.info(f"🔄 Topic diversification [step 2]: {needed} more videos from other topics")
logger.info(f"✨ Diversified: added {len(docs_diverse)} videos. Total: {len(docs)}/{limit}")
logger.info(f"📊 Feed composition: {len(docs_preferred)} preferred + {len(docs_diverse)} diverse")
```

---

## VIII. Edge Cases Handled

| Edge Case | Handling |
|-----------|----------|
| User has seen all videos | Fallback 3: Allow repeats with intensity filter |
| User has no interest_vector | Skip diversification (use interest_tags or trending) |
| Fatigue < 40% (normal state) | No diversification, regular vector search |
| Fatigue > 70% (exhausted) | No topic diversification, only palette cleanser |
| Preferred topics = "*" or empty | Treat as "no preference", use trending |
| Overlapping videos between steps | Already handled by `seen_set` dedup |

---

## IX. Performance Considerations

✅ **Optimizations:**
- Only trigger diversification at warning state (40-70%)
- Use single aggregation pipeline per fetch
- Combine filters early ($and) to reduce scan
- Limit diversification to `limit - len(docs)` (not extra)

⚠️ **Trade-offs:**
- 1-2 extra MongoDB queries at warning state (acceptable for user experience)
- Memory: Store `preferred_tags` in memory (negligible)

---

## X. Rollout Strategy

1. **Stage 1:** Deploy logic with detailed logging (no changes to user experience)
2. **Stage 2:** A/B test with 10% users → measure feed_empty rate
3. **Stage 3:** Full rollout if feed quality improves

---

## Tóm Tắt

✅ **Problem Solved:**
- At ≥40% fatigue, if preferred topics → exhausted, fallback to trending other topics
- Always maintain intensity filter for fatigue state
- Never return empty feed when diversification available

✅ **Backward Compatible:**
- Normal state (fatigue < 40%) unchanged
- Exhausted state (fatigue > 70%) unchanged
- Only warning state (40-70%) affected

✅ **User Experience:**
- More diverse content when preferred topics exhausted
- Better mental health support (respects fatigue state)
- Breaks filter bubble at right time
