# 🐛 BUG FIX: New User Interest Vector Initialization

## Problem Identified

**User flow:**
1. User đăng ký với tags: `["game", "dancing"]`
2. Feed lại toàn show: `["nature"]` (đúng là sai!)

**Root Cause:**

Khi user mới đăng ký, hệ thống tính `interest_vector` như thế này:

```python
# app/services/user_service.py - _compute_initial_vector()

videos = await self._video_repo.find_by_tags(interest_tags, limit=20)
embeddings = [v["embedding"] for v in videos if v.get("embedding")]

if embeddings:
    # ✅ Use average of matching videos' embeddings
    return avg_embeddings
else:
    # ❌ FALLBACK BUG: Generate embedding from TEXT tag thôi
    tag_text = f"User interests: {', '.join(interest_tags)}"
    fallback_vector = await generate_embedding(tag_text)  # <-- ISSUE!
    return fallback_vector
```

### Vấn đề:

**Scenario 1 (Có videos matching tags):**
- ✅ Nếu DB có videos với tag "game" hoặc "dancing" → vector được tính từ embeddings của videos đó
- ✅ Vector này sẽ tương đồng cao với các video game/dancing khác

**Scenario 2 (KO có videos matching tags):** ← **ĐÂY LÀ BUG**
- `find_by_tags()` trả về empty list
- System generate embedding từ text: `"User interests: game, dancing"`
- LLM model convert text này thành 1536-dim vector
- **Problem:** Vector này có thể KO liên quan gì đến videos "game" hay "dancing" thực tế!
  - Nó chỉ là embedding của câu chữ tĩnh
  - Không capture được visual/audio patterns của actual videos
  - Có thể cosine similarity cao với "nature" videos vì lý do random!

---

## Solution: Tag-to-Vector Mapping Strategy

### ✨ Approach 1: Create Pre-Computed Tag Vectors (RECOMMENDED)

**Idea:** Mỗi tag (game, dancing, nature, etc.) có 1 canonical embedding vector được tính từ ALL videos với tag đó.

**Implementation:**
1. **Scheduler job** (chạy 1 lần khi setup, hoặc mỗi tuần):
   ```
   For each tag in all_videos:
       videos_with_tag = db.videos.find({tags: tag})
       embeddings = [v.embedding for v in videos_with_tag if v.embedding]
       
       tag_canonical_vector = average(embeddings)
       tag_canonical_vector = L2_normalize(tag_canonical_vector)
       
       db.tags_vectors.upsert({
           tag: tag,
           canonical_vector: tag_canonical_vector,
           video_count: len(embeddings),
           updated_at: now()
       })
   ```

2. **User onboarding** (use cached tag vectors):
   ```python
   async def _compute_initial_vector(self, interest_tags):
       tag_vectors = await self._tag_vector_repo.find_by_names(interest_tags)
       
       if tag_vectors:
           # Average the canonical vectors of selected tags
           vectors = [tv["canonical_vector"] for tv in tag_vectors if tv]
           if vectors:
               avg_vector = average_vectors(vectors)
               avg_vector = L2_normalize(avg_vector)
               return avg_vector
       
       # Fallback: if tag vectors not computed yet (rare)
       return generate_embedding(f"User interests: {', '.join(interest_tags)}")
   ```

**Pros:**
- ✅ Vector thực sự đại diện cho videos với tag đó
- ✅ Consistent across all new users with same interests
- ✅ No need to query all videos each time user registers

**Cons:**
- Cần 1 scheduler job tính sẵn

---

### ✨ Approach 2: Lazy Fallback with Weighted Tags

**Idea:** Nếu KO có pre-computed tag vectors, combine:
- Text embedding từ tags
- + Weight từ "most similar existing videos"

```python
async def _compute_initial_vector(self, interest_tags):
    # 1. Try to find real videos
    videos = await self._video_repo.find_by_tags(interest_tags, limit=50)
    embeddings = [v["embedding"] for v in videos if v.get("embedding")]
    
    if embeddings:
        return L2_normalize(average_vectors(embeddings))
    
    # 2. No exact videos found → try semantic search with tag text
    # Search for ALL videos containing these tag KEYWORDS in title/description
    related_videos = await self._video_repo.find_by_semantic_search(
        query=f"videos about {', '.join(interest_tags)}",
        limit=20
    )
    
    if related_videos:
        related_embeddings = [v["embedding"] for v in related_videos if v.get("embedding")]
        if related_embeddings:
            return L2_normalize(average_vectors(related_embeddings))
    
    # 3. Ultimate fallback (very rare)
    return generate_embedding(f"User interests: {', '.join(interest_tags)}")
```

**Pros:**
- Works even without pre-computed tag vectors
- ✅ Better than pure text fallback

**Cons:**
- Slower (semantic search required if no exact tag matches)

---

### ✨ Approach 3: Pre-seed Sample Videos During Setup

**Idea:** When app starts, make sure we have at least some videos for common tags:
- "game" (action, sports games, esports, etc.)
- "dancing" (dance, choreography, etc.)
- "nature" (animals, outdoors, landscapes, etc.)
- etc.

So `find_by_tags()` always returns something.

**Pros:**
- Simplest for hackathon
- Works immediately

**Cons:**
- Depends on having good sample videos in DB

---

## Investigation Checklist

Before implementing fix, verify:

- [ ] Run test: Register user with `["game", "dancing"]`
- [ ] Check if videos with tag "game" exist in DB:
  ```bash
  db.videos.countDocuments({tags: "game"})
  db.videos.countDocuments({tags: "dancing"})
  ```
- [ ] Check if those videos have `.embedding` field populated:
  ```bash
  db.videos.countDocuments({tags: "game", embedding: {$exists: true, $ne: []}})
  ```
- [ ] After user creation, check user's `interest_vector`:
  ```bash
  db.users.findOne({username: "test_user"}).interest_vector
  ```
- [ ] Use `/api/v1/users/{user_id}/vector-status` endpoint to check vector metadata

---

## Recommended Fix for Hackathon

**Priority: MEDIUM → HIGH (breaks UX for users)**

**Timeline:** ~2-3 hours

### Step 1: Create Tag Vector Repo + Model (30 min)
- Create `app/models/tag_vector.py`
- Create `app/repositories/tag_vector_repository.py`
- Add MongoDB collection: `db.createCollection("tag_vectors")`

### Step 2: Create Scheduler Job (45 min)
- `app/tasks.py` add task: `compute_tag_canonical_vectors()`
- Run on application startup + periodically (weekly)

### Step 3: Update User Service (30 min)
- Modify `_compute_initial_vector()` to use tag vectors
- Fallback remain unchanged

### Step 4: Test (30 min)
- Test: Register user → check vector → get feed
- Verify: Feed contains relevant videos to selected tags

---

## Commit Plan

```
1. [repo] Add TagVector model + repository
2. [scheduler] Add compute_tag_canonical_vectors task
3. [service] Update user_service._compute_initial_vector
4. [tests] Add e2e test for new user interest vector
5. [docs] Update onboarding flow documentation
```

---

## Fallback (Ultra-Quick Fix)

If no time for full implementation, band-aid:

```python
# In _compute_initial_vector, when fallback to text:
tag_text = f"User interests: {', '.join(interest_tags)}"

# INSTEAD OF GENERIC TEXT:
# Use a more specific description for each tag
tag_descriptions = {
    "game": "action games, video games, esports, gaming, interactive entertainment",
    "dancing": "dance, choreography, hip-hop, salsa, ballet, movement, music videos",
    "nature": "natural landscapes, animals, outdoor, forests, mountains, water",
    ...
}

detailed_text = ", ".join([
    tag_descriptions.get(tag, tag)
    for tag in interest_tags
])

fallback_vector = await generate_embedding(detailed_text)
```

This helps LLM generate a more relevant vector from text alone.

---

## Questions to Clarify

1. **Do you have videos in DB with tags "game" and "dancing"?** 
   - If yes → why aren't they being found?
   - If no → need to seed sample videos first

2. **Is the embedding generation working correctly?**
   - Test: `app/utils/embedding.py` - check if mock mode is active

3. **Did user onboarding actually save the computed vector?**
   - Check database directly to see if `interest_vector` field is populated
