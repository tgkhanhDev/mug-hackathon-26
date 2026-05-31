# 🔧 Code Changes: Before vs After

## File 1: `backend/app/services/feed_service.py`

### BEFORE (Current Implementation) - Lines 136-205

```python
# 4. Generate feed with progressive fallback strategy
# Fallback ladder: full filter → dedup-only → no filter (avoid total empty)
interest_vector = user.get("interest_vector", [])
interest_tags = user.get("interest_tags", [])
search_weight, trending_weight = self._get_adaptive_weights(adaptive_state)

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

# Fallback 1: intensity filter too strict → drop it, keep dedup only
if len(docs) < limit and intensity_filter is not None:
    logger.info(
        f"⚠️ Feed too small ({len(docs)}/{limit}) with intensity filter "
        f"— relaxing to dedup-only for user {user_id}"
    )
    docs = await self._fetch_feed(
        interest_vector=interest_vector,
        user_id=user_id,
        limit=limit,
        adaptive_state=adaptive_state,
        search_weight=search_weight,
        trending_weight=trending_weight,
        filter_stage=seen_ids_filter,  # dedup only, no intensity constraint
        num_exclude=len(seen_set),
        interest_tags=interest_tags,
    )

# Fallback 2: still empty → user has seen everything → drop dedup filter too
if len(docs) == 0 and seen_ids_filter is not None:
    logger.info(
        f"♻️ Feed empty after relaxing intensity filter "
        f"— dropping dedup filter (user has seen all available videos): {user_id}"
    )
    docs = await self._fetch_feed(
        interest_vector=interest_vector,
        user_id=user_id,
        limit=limit,
        adaptive_state=adaptive_state,
        search_weight=search_weight,
        trending_weight=trending_weight,
        filter_stage=None,  # no filter at all
        interest_tags=interest_tags,
    )
```

### AFTER (New Implementation with Topic Diversification)

```python
# 4. Generate feed with topic diversification for warning state
interest_vector = user.get("interest_vector", [])
interest_tags = user.get("interest_tags", [])
search_weight, trending_weight = self._get_adaptive_weights(adaptive_state)

# STEP 1: Fetch from user's preferred topics
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

# STEP 2: Topic Diversification Fallback (NEW)
# At warning state (40-70% fatigue), if preferred topics don't have enough videos,
# fetch from OTHER topics to diversify instead of breaking intensity constraints
if (
    len(docs) < limit
    and adaptive_state == "warning"
    and interest_vector  # Only if user has personalization
):
    needed = limit - len(docs)
    preferred_tags = interest_tags or []
    
    logger.info(
        f"🔄 Topic diversification (warning state): Need {needed} more videos. "
        f"Excluding preferred_tags={preferred_tags}"
    )
    
    docs_diverse = await self._video_repo._fetch_trending_diverse(
        limit=needed,
        exclude_category_tags=preferred_tags,
        intensity_filter={"intensity_level": {"$in": ["low", "medium"]}},
        exclude_ids=seen_set,
    )
    
    docs.extend(docs_diverse)
    logger.info(
        f"✨ Diversified feed: added {len(docs_diverse)}/{needed} diverse videos. "
        f"Total now: {len(docs)}/{limit}"
    )

# STEP 3: Dedup Fallback (if still not enough)
# Allow repeating seen videos but always maintain intensity filter for fatigue safety
if len(docs) == 0 and seen_ids_filter is not None:
    logger.info(
        f"♻️ Feed empty with all constraints — allowing seen videos "
        f"but KEEPING intensity_filter for fatigue safety: {user_id}"
    )
    
    # Allow repeating videos but keep intensity constraint
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
        logger.info(
            f"🔄 Topic diversification fallback (without dedup): Need {needed} more videos"
        )
        
        docs_diverse_repeat = await self._video_repo._fetch_trending_diverse(
            limit=needed,
            exclude_category_tags=interest_tags or [],
            intensity_filter=intensity_filter,
            exclude_ids=None,  # Allow repeats
        )
        docs.extend(docs_diverse_repeat)
        logger.info(
            f"✨ Fallback diversification: added {len(docs_diverse_repeat)} videos"
        )
```

### Key Differences

| Aspect | BEFORE | AFTER |
|--------|--------|-------|
| **Step 1** | Vector search + intensity | Same |
| **Step 2** | ❌ Drops intensity | ✅ Fetch OTHER topics, keep intensity |
| **Step 3** | ❌ Drops all filters | ✅ Drops dedup only, keeps intensity |
| **Branching** | `if len(docs) < limit` | ✅ Only at `adaptive_state == "warning"` |
| **Safety** | ⚠️ Can leak high-intensity | ✅ Never breaks fatigue constraint |
| **Diversity** | ❌ Stuck repeating preferred topics | ✅ Naturally diversifies to other topics |

---

## File 2: `backend/app/repositories/video_repository.py`

### AFTER (New Method - Add to VideoRepository class)

**Location:** Add after existing methods like `find_random_calming()` (~line 90)

```python
async def _fetch_trending_diverse(
    self,
    limit: int,
    exclude_category_tags: Optional[List[str]],
    intensity_filter: Optional[Dict[str, Any]],
    exclude_ids: Optional[set],
) -> List[Dict[str, Any]]:
    """
    Fetch trending videos EXCLUDING user's preferred topics for topic diversification.
    
    Used when user's preferred topics are exhausted but need more content.
    This prevents the feed from becoming stuck or returning high-intensity content
    during warning/exhausted fatigue states.
    
    Args:
        limit: Number of videos to fetch
        exclude_category_tags: Tags to EXCLUDE (e.g., ['nature', 'meditation'])
        intensity_filter: Intensity constraint (e.g., {"$in": ["low", "medium"]})
        exclude_ids: Video IDs to exclude from search (can be None for repeat fallback)
    
    Returns:
        List[Dict] of trending videos from different topics
        
    Example:
        >>> docs = await repo._fetch_trending_diverse(
        ...     limit=3,
        ...     exclude_category_tags=["nature", "meditation"],
        ...     intensity_filter={"intensity_level": {"$in": ["low", "medium"]}},
        ...     exclude_ids=seen_video_ids
        ... )
    """
    from bson import ObjectId
    
    # Build match filter - always required
    match_filter: Dict[str, Any] = {"status": "completed"}
    
    # Add intensity constraint (never skip this in warning/exhausted states)
    if intensity_filter:
        match_filter = {"$and": [match_filter, intensity_filter]}
    
    # Exclude preferred topics to diversify
    if exclude_category_tags and len(exclude_category_tags) > 0:
        match_filter = {
            "$and": [
                match_filter,
                {"tags": {"$nin": exclude_category_tags}}  # Tags NOT in preferred list
            ]
        }
    
    # Dedup if provided (exclude already-seen videos)
    if exclude_ids:
        valid_oids = [ObjectId(vid) for vid in exclude_ids if ObjectId.is_valid(vid)]
        if valid_oids:
            match_filter = {
                "$and": [
                    match_filter,
                    {"_id": {"$nin": valid_oids}}
                ]
            }
    
    # Build pipeline: match → trending score → sort → limit
    pipeline = [
        {"$match": match_filter},
        build_trending_score_pipeline_stage(),
        {"$sort": {"trending_score": -1}},
        {"$limit": limit}
    ]
    
    return await self.aggregate(pipeline)
```

---

## Summary of Changes

### `feed_service.py` Changes:
- ✏️ **Lines 136-205:** Replace Fallback 1 & 2 logic with new 3-step strategy
- ✏️ Add STEP 2 (topic diversification) for warning state
- ✏️ Fix STEP 3 to keep intensity filter instead of dropping it

### `video_repository.py` Changes:
- ➕ Add new method `_fetch_trending_diverse()` after `find_random_calming()`
- Total: ~35 lines of new code

### Lines Changed:
- **feed_service.py:** ~70 lines (replacing old fallback logic)
- **video_repository.py:** +35 lines (new method)
- **Total:** ~105 lines

### Complexity:
- ✅ Added: 1 new method in VideoRepository
- ✅ Modified: 1 method in FeedService
- ✅ Backward compatible: No API changes
- ✅ Easy to maintain: Clear logging at each step

---

## Testing the Changes

### Unit Test Template

```python
# Test Case 1: Topic diversification triggers correctly
async def test_topic_diversification_at_warning_state():
    """At fatigue=50%, if preferred topic empty, should fetch from other topics."""
    # Arrange
    user_id = "test_user_1"
    user = {
        "interest_vector": [0.1, 0.2, ...],  # Has personalization
        "interest_tags": ["nature"]  # Preferred topic
    }
    # Mock: nature topics have NO videos, other topics have 5 trending videos
    
    # Act
    docs = await feed_service.get_feed(user_id, limit=5, exclude_ids=[])
    
    # Assert
    assert len(docs) == 5, "Should return 5 videos despite no nature videos"
    assert all(doc.intensity_level in ["low", "medium"] for doc in docs), \
        "All videos must respect intensity constraint"
    assert not all(doc.category == "nature" for doc in docs), \
        "Should have diversified topics, not just nature"

# Test Case 2: Critical state unaffected
async def test_no_diversification_at_critical_state():
    """At fatigue=75%+, diversification should NOT trigger."""
    # Arrange
    user_id = "test_user_2"
    adaptive_state = "critical"  # Should use palette cleanser, not diversification
    
    # Act
    docs = await feed_service.get_feed(user_id, limit=5)
    
    # Assert: Should follow critical state logic (palette cleanser only, no diversification)
```

---

## Deployment Checklist

- [ ] Deploy `video_repository.py` with new `_fetch_trending_diverse()` method
- [ ] Deploy updated `feed_service.py` with topic diversification logic
- [ ] Run unit tests for all 5 test cases
- [ ] Monitor logs for "🔄 Topic diversification" messages
- [ ] Check feed_empty rate before/after in metrics dashboard
- [ ] A/B test with 10% users first
- [ ] Full rollout if metrics improve

---

## Monitoring & Observability

### New Log Messages to Track

```python
# When diversification triggers
"🔄 Topic diversification (warning state): Need X more videos"

# When videos are successfully added
"✨ Diversified feed: added X/Y diverse videos. Total now: Z/limit"

# When fallback is needed
"♻️ Feed empty with all constraints — allowing seen videos..."

# Success metric
"✨ Fallback diversification: added X videos"
```

### Metrics to Monitor

- `feed_generation.empty_count` → Should decrease
- `feed_generation.diversification_triggered` → Should increase at warning states
- `feed_generation.diversity_success_ratio` → Target: >95%
- `feed_generation.latency_ms` → Should remain <500ms

---

## Rollback Plan

If issues arise:
1. Revert `feed_service.py` to previous version
2. Keep `video_repository.py` (only adds method, doesn't break anything)
3. Feature flag `ENABLE_TOPIC_DIVERSIFICATION = False` in config if needed
