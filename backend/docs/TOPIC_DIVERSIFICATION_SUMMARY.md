# 📋 Implementation Plan Summary: Topic Diversification Fallback

## Bug Description
```
At fatigue ≥ 40%:
  User prefers "Nature" videos → all exhausted/seen
  ❌ Current: Feed returns EMPTY or HIGH-INTENSITY gaming videos (WRONG)
  ✅ Expected: Feed returns LOW/MEDIUM intensity videos from OTHER topics
```

## Root Cause Analysis
```
feed_service.get_feed()
  ↓
[Step 1] Vector search with user's interest_vector
  + intensity_filter  
  + dedup (seen videos)
  ↓
  No videos found (Nature topic empty)
  ↓
[Fallback 1] Drop intensity_filter (WRONG!) ← THIS BREAKS FATIGUE LOGIC
  → Might return high-intensity gaming
  ✗ Violates wellbeing constraints
```

## Proposed Solution (Topic Diversification Fallback)

### Three-Step Strategy

```
Step 1: PREFERRED TOPICS
┌─────────────────────────────────┐
│ Vector Search (User's Topics)   │
│ + Interest Vector               │
│ + Intensity: [low, medium]      │
│ + Dedup: Exclude seen           │
└─────────────────────────────────┘
         ↓ Got < limit videos?
         
Step 2: TOPIC DIVERSIFICATION (NEW)
┌──────────────────────────────────────┐
│ Fetch Trending OTHER Topics          │
│ - EXCLUDE: User's preferred topics   │
│ - Intensity: [low, medium] (always)  │
│ - Dedup: Exclude seen                │
│ - Gap: limit - step1_count           │
└──────────────────────────────────────┘
         ↓ Still need more?
         
Step 3: DEDUP FALLBACK
┌──────────────────────────────────────┐
│ Repeat Steps 1+2 WITHOUT dedup       │
│ (allow repeating seen videos)        │
│ But KEEP intensity_filter            │
│ (never show high-intensity at warning)
└──────────────────────────────────────┘
```

## Code Changes Required

### 1. FeedService (`feed_service.py`)
```python
# After Step 1 (line ~170), ADD:

if len(docs) < limit and adaptive_state == "warning":
    needed = limit - len(docs)
    docs_diverse = await self._fetch_trending_diverse(
        limit=needed,
        exclude_category_tags=interest_tags,  # Skip user's preferred topics
        intensity_filter=intensity_filter,    # Always keep this!
        exclude_ids=seen_set,
    )
    docs.extend(docs_diverse)
    logger.info(f"✨ Added {len(docs_diverse)} diverse videos from other topics")
```

### 2. VideoRepository (`video_repository.py`)
```python
# Add new method:

async def _fetch_trending_diverse(
    self,
    limit: int,
    exclude_category_tags: List[str],
    intensity_filter: Dict[str, Any],
    exclude_ids: set,
) -> List[Dict]:
    """Fetch trending videos excluding preferred topics."""
    # Build filter to avoid preferred topics
    # Apply intensity_filter (never skip this!)
    # Exclude seen videos (dedup)
    # Sort by trending_score
```

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Exhausted preferred topic** | ❌ Empty feed or wrong intensity | ✅ Diverse content, correct intensity |
| **Fatigue respect** | ❌ High-intensity gaming might slip in | ✅ Always respects fatigue state |
| **User experience** | ❌ Feed keeps getting same content | ✅ Varied content keeps user engaged |
| **DB queries** | 1-2 queries | 2-3 queries (acceptable) |
| **Filter bubble** | ❌ Can get stuck in one topic | ✅ Naturally breaks filter bubble |

## Test Scenarios

| Case | Input | Expected Output |
|------|-------|-----------------|
| **Case 1: Preferred available** | fatigue=50%, nature has 5 videos | 5 nature videos ✅ |
| **Case 2: Preferred empty** | fatigue=50%, nature has 0 videos | 5 trending other-topic videos (low/med) ✅ |
| **Case 3: Both empty** | fatigue=50%, all prefer topics empty | Fall back to repeats (seen videos allowed) ✅ |
| **Case 4: Normal state** | fatigue=30%, nature preference | Regular vector search (no diversification) ✅ |
| **Case 5: Exhausted state** | fatigue=75%, nature preference | Palette cleanser only (no diversification) ✅ |

## Affected States

```
fatigue: 0%                                          100%
         ├─ Normal (0-40%)    ├─ Warning (40-70%)   ├─ Critical (70-100%)
         │  No changes        │  ← TOPIC DIVERSITY  │  No changes
         │  Vector search     │     TRIGGERS HERE   │  Low-intensity only
         │  (full freedom)    │                     │  (strict filter)
         └────────────────────┴─────────────────────┴──────────────────
```

## Files Modified

- ✏️ `backend/app/services/feed_service.py` → `get_feed()` method
- ✏️ `backend/app/repositories/video_repository.py` → new `_fetch_trending_diverse()` method

## Backward Compatibility

✅ Fully backward compatible:
- States below 40% fatigue: No changes
- States above 70% fatigue: No changes  
- Existing fallback strategy still works as safety net
- Only warning state (40-70%) affected with new behavior

## QA Checklist

- [ ] Topic diversification only triggers at warning state
- [ ] Intensity filter ALWAYS maintained at ≥40% fatigue
- [ ] No video in "other topics" is high-intensity when fatigue ≥ 40%
- [ ] Dedup respected in all steps
- [ ] Preferred topics prioritized before diverse topics
- [ ] Empty feed never returned when diverse topics available
- [ ] Logging shows topic diversification flow clearly
- [ ] Normal/Exhausted states unaffected

---

**Full detailed plan available in:** `FATIGUE_ENGINE_TOPIC_DIVERSIFICATION_PLAN.md`
