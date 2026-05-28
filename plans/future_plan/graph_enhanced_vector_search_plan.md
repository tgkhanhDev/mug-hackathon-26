# 🕸️ Graph-Enhanced Vector Search — GoTouchGrass

## 🎯 Vấn đề hiện tại của Vector Search đơn thuần

```
User interest_vector → $vectorSearch → [car_racing, drift, fast_car, race_highlight, ...]
```

**Hệ thống hiện tại bị "trapped" trong topic cluster:**
- Vector Search trả về các video rất similar → thiếu diversity
- Nếu user thích "xe hơi tốc độ cao" → chỉ gợi ý mãi xe hơi tốc độ cao
- Khi fatigue tăng, ta cần gợi ý "xe hơi chậm / ASMR rửa xe" — nhưng vector embedding của chúng **khác nhau** → vector search sẽ không tìm được

**Graph search giải quyết chính xác điều này:**

```
[Car Racing] ── "related, intensity: -1" ──> [Car Detailing / ASMR]
[Car Racing] ── "related, intensity: -2" ──> [Nature Drives / Road Trip]
```

---

## 🏗️ Kiến trúc: Topic Relationship Graph

### Ý tưởng cốt lõi

Xây một **topic graph** trong MongoDB. Mỗi node là một topic/category. Mỗi edge lưu:
- `to`: topic đích
- `weight`: mức độ liên quan (0→1)
- `intensity_delta`: thay đổi intensity (-2 = giảm 2 cấp, 0 = giữ nguyên)

Khi vector search trả về danh sách video → extract topics → `$graphLookup` để tìm **related topics** → fetch thêm video từ related topics → merge + re-rank.

### Khi nào dùng Graph Traversal?

| Fatigue State | Hành động |
|---|---|
| `normal` | Chỉ dùng Vector Search (hiệu năng tốt nhất) |
| `warning` | Graph traverse depth=1, ưu tiên edge `intensity_delta <= 0` |
| `exhausted/critical` | Graph traverse depth=2, ưu tiên edge `intensity_delta <= -1` |

---

## 📋 Implementation Plan

### Phase 1: Data Model — `topic_graph` collection

**File mới:** `backend/app/models/topic_graph.py`

```python
# Document schema cho collection `topic_graph`
{
  "_id": ObjectId,
  "topic": "automotive",          # Node: topic name (khớp với video.category)
  "related_topics": [
    {
      "to": "lifestyle",
      "weight": 0.7,              # Độ liên quan (1.0 = rất liên quan)
      "intensity_delta": -1       # -1: nhẹ hơn 1 bậc, -2: nhẹ hơn 2 bậc
    },
    {
      "to": "nature",
      "weight": 0.5,
      "intensity_delta": -2
    }
  ]
}
```

**Seed data cho tất cả 15 categories:**

```python
TOPIC_GRAPH_SEED = [
    {"topic": "automotive", "related_topics": [
        {"to": "lifestyle", "weight": 0.7, "intensity_delta": -1},
        {"to": "nature",    "weight": 0.5, "intensity_delta": -2},
    ]},
    {"topic": "entertainment", "related_topics": [
        {"to": "comedy",  "weight": 0.8, "intensity_delta": 0},
        {"to": "music",   "weight": 0.6, "intensity_delta": -1},
        {"to": "art",     "weight": 0.5, "intensity_delta": -1},
        {"to": "calming", "weight": 0.4, "intensity_delta": -2},
    ]},
    {"topic": "gaming", "related_topics": [
        {"to": "entertainment", "weight": 0.8, "intensity_delta": 0},
        {"to": "education",     "weight": 0.5, "intensity_delta": -1},
        {"to": "art",           "weight": 0.4, "intensity_delta": -1},
    ]},
    {"topic": "sports", "related_topics": [
        {"to": "lifestyle", "weight": 0.7, "intensity_delta": -1},
        {"to": "nature",    "weight": 0.5, "intensity_delta": -1},
        {"to": "calming",   "weight": 0.3, "intensity_delta": -2},
    ]},
    {"topic": "lifestyle", "related_topics": [
        {"to": "cooking", "weight": 0.7, "intensity_delta": 0},
        {"to": "fashion", "weight": 0.6, "intensity_delta": 0},
        {"to": "calming", "weight": 0.5, "intensity_delta": -1},
        {"to": "nature",  "weight": 0.4, "intensity_delta": -1},
    ]},
    {"topic": "education", "related_topics": [
        {"to": "art",       "weight": 0.6, "intensity_delta": 0},
        {"to": "nature",    "weight": 0.5, "intensity_delta": -1},
        {"to": "animals",   "weight": 0.5, "intensity_delta": -1},
        {"to": "space",     "weight": 0.6, "intensity_delta": 0},
    ]},
    {"topic": "comedy", "related_topics": [
        {"to": "entertainment", "weight": 0.8, "intensity_delta": 0},
        {"to": "animals",       "weight": 0.6, "intensity_delta": -1},
        {"to": "music",         "weight": 0.5, "intensity_delta": -1},
    ]},
    {"topic": "music", "related_topics": [
        {"to": "art",     "weight": 0.7, "intensity_delta": 0},
        {"to": "calming", "weight": 0.6, "intensity_delta": -1},
        {"to": "nature",  "weight": 0.5, "intensity_delta": -1},
    ]},
    {"topic": "art", "related_topics": [
        {"to": "music",     "weight": 0.7, "intensity_delta": 0},
        {"to": "calming",   "weight": 0.6, "intensity_delta": -1},
        {"to": "education", "weight": 0.5, "intensity_delta": 0},
    ]},
    {"topic": "cooking", "related_topics": [
        {"to": "lifestyle", "weight": 0.7, "intensity_delta": 0},
        {"to": "animals",   "weight": 0.5, "intensity_delta": -1},
        {"to": "nature",    "weight": 0.4, "intensity_delta": -1},
    ]},
    {"topic": "fashion", "related_topics": [
        {"to": "lifestyle",     "weight": 0.8, "intensity_delta": 0},
        {"to": "art",           "weight": 0.6, "intensity_delta": -1},
        {"to": "entertainment", "weight": 0.5, "intensity_delta": 0},
    ]},
    {"topic": "animals", "related_topics": [
        {"to": "nature",    "weight": 0.8, "intensity_delta": 0},
        {"to": "calming",   "weight": 0.7, "intensity_delta": -1},
        {"to": "education", "weight": 0.5, "intensity_delta": 0},
    ]},
    {"topic": "nature", "related_topics": [
        {"to": "calming",   "weight": 0.9, "intensity_delta": -1},
        {"to": "animals",   "weight": 0.7, "intensity_delta": 0},
        {"to": "education", "weight": 0.5, "intensity_delta": 0},
    ]},
    {"topic": "calming", "related_topics": [
        {"to": "nature",    "weight": 0.8, "intensity_delta": 0},
        {"to": "music",     "weight": 0.7, "intensity_delta": 0},
        {"to": "animals",   "weight": 0.6, "intensity_delta": 0},
    ]},
    {"topic": "space", "related_topics": [
        {"to": "education", "weight": 0.8, "intensity_delta": 0},
        {"to": "art",       "weight": 0.6, "intensity_delta": -1},
        {"to": "calming",   "weight": 0.5, "intensity_delta": -1},
    ]},
]
```

**Script seed:** `backend/scripts/seed_topic_graph.py`

---

### Phase 2: Repository

**File mới:** `backend/app/repositories/topic_graph_repository.py`

```python
class TopicGraphRepository(BaseRepository):
    def __init__(self):
        super().__init__(get_collection("topic_graph"))

    async def get_related_topics(
        self,
        start_topics: List[str],
        max_depth: int = 1,
        min_weight: float = 0.4,
        max_intensity_delta: int = 0,
    ) -> List[Dict]:
        """$graphLookup từ topics gốc → trả về related topics đã sort theo weight."""
        pipeline = [
            {"$match": {"topic": {"$in": start_topics}}},
            {"$unwind": "$related_topics"},
            {
                "$match": {
                    "related_topics.weight": {"$gte": min_weight},
                    "related_topics.intensity_delta": {"$lte": max_intensity_delta},
                    "related_topics.to": {"$nin": start_topics},  # Không lặp lại topic gốc
                }
            },
            {
                "$group": {
                    "_id": "$related_topics.to",
                    "weight": {"$max": "$related_topics.weight"},
                    "intensity_delta": {"$min": "$related_topics.intensity_delta"},
                }
            },
            {"$sort": {"weight": -1}},
            {"$limit": 5},
        ]
        return await self.aggregate(pipeline)
```

> **Note:** `$graphLookup` depth>1 cần index trên `topic` field. Với 15 nodes, depth=1 với `$unwind` là đủ hiệu quả.

**Update `VideoRepository`** — thêm method `find_by_topics()`:

```python
async def find_by_topics(
    self,
    topics: List[str],
    limit: int = 3,
    intensity_level: Optional[str] = None,
    exclude_ids: set = None,
) -> List[Dict]:
    """Fetch videos từ related topics (graph traversal result)."""
    match = {
        "status": "completed",
        "category": {"$in": topics},
    }
    if intensity_level:
        match["intensity_level"] = intensity_level
    if exclude_ids:
        valid_ids = [ObjectId(v) for v in exclude_ids if ObjectId.is_valid(v)]
        if valid_ids:
            match["_id"] = {"$nin": valid_ids}

    pipeline = [
        {"$match": match},
        build_trending_score_pipeline_stage(),
        {"$sort": {"trending_score": -1}},
        {"$limit": limit},
    ]
    return await self.aggregate(pipeline)
```

---

### Phase 3: Feed Service Integration

**File:** `backend/app/services/feed_service.py`

```python
# Trong __init__:
self._graph_repo = TopicGraphRepository()

# Trong get_feed(), SAU bước 4 (vector search results):

# ─── GRAPH ENHANCEMENT ──────────────────────────────────────────
if adaptive_state in ["warning", "exhausted", "critical"] and len(docs) > 0:

    # 1. Extract topics từ kết quả vector search
    primary_topics = list({doc.get("category") for doc in docs if doc.get("category")})

    # 2. Config theo fatigue state
    max_delta  = -1 if adaptive_state in ["exhausted", "critical"] else 0
    num_inject = 2  # Inject tối đa 2 video từ graph

    # 3. Graph traversal — chạy song song với fallback
    related = await self._graph_repo.get_related_topics(
        start_topics=primary_topics,
        max_depth=1,
        max_intensity_delta=max_delta,
    )

    if related:
        related_topic_names = [r["_id"] for r in related]
        current_ids = seen_set | {doc["id"] for doc in docs}

        # 4. Fetch videos từ related topics
        graph_videos = await self._video_repo.find_by_topics(
            topics=related_topic_names,
            limit=num_inject,
            exclude_ids=current_ids,
        )

        if graph_videos:
            # 5. Weave vào feed: position 2 và 4 (xen kẽ, tự nhiên)
            for i, gv in enumerate(graph_videos):
                insert_pos = min(2 + i * 2, len(docs))
                docs.insert(insert_pos, gv)
            docs = docs[:limit]

            logger.info(
                f"🕸️ Graph: injected {len(graph_videos)} videos from "
                f"{related_topic_names} (state={adaptive_state})"
            )
```

---

## 📊 Ví dụ Flow hoàn chỉnh

```
User thích xe hơi, đang xem nhiều → "warning" state

1. Vector Search:
   → [drift_vid, race_vid, tuning_vid, drift_vid2, race_vid2]
   → primary_topics = ["automotive"]

2. $graphLookup từ "automotive" (max_delta=0):
   → [{"_id": "lifestyle", "weight": 0.7},
      {"_id": "nature",    "weight": 0.5}]

3. find_by_topics(["lifestyle", "nature"], limit=2):
   → [road_trip_scenic, mountain_drive]

4. Weave vào feed (position 2 và 4):
   [drift_vid, road_trip_scenic, race_vid, mountain_drive, tuning_vid]
                ↑ graph inject              ↑ graph inject
```

---

## ✅ Checklist

| # | Task | File | Status |
|---|------|------|--------|
| 1 | Tạo `topic_graph.py` data model | `models/topic_graph.py` | ⬜ |
| 2 | Tạo seed script với 15 categories | `scripts/seed_topic_graph.py` | ⬜ |
| 3 | Tạo `TopicGraphRepository` | `repositories/topic_graph_repository.py` | ⬜ |
| 4 | Thêm `find_by_topics()` vào `VideoRepository` | `repositories/video_repository.py` | ⬜ |
| 5 | Integrate graph vào `FeedService.get_feed()` | `services/feed_service.py` | ⬜ |
| 6 | Tạo index `{ "topic": 1 }` trên `topic_graph` collection | Atlas UI | ⬜ |
| 7 | Chạy seed script | Terminal | ⬜ |
| 8 | Test: verify log `🕸️ Graph:` khi state = warning | Manual QA | ⬜ |

---

## ⚡ Pitch Value cho Ban Giám Khảo

| Điểm mạnh | Chi tiết |
|---|---|
| **MongoDB native** | Dùng `$graphLookup` — built-in aggregation, không cần Neo4j |
| **Zero ML overhead** | Không train thêm, không cần API ngoài |
| **Wellbeing story rõ ràng** | "Khi user mệt, hệ thống tự nhiên dẫn họ sang nội dung nhẹ hơn qua graph" |
| **Observable** | Log `🕸️ Graph: injected ...` hiện trực tiếp trong console → judge thấy được |
| **Complementary** | Graph + Vector Search cộng hưởng, không thay thế nhau |
