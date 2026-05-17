"""
GoTouchGrass — MongoDB Setup & Seed Script
==========================================
Mục đích:
  1. Tạo database `gotouchgrass` và 5 collections với đúng schema
  2. Tạo các indexes cần thiết
  3. Seed 100 videos mẫu với đầy đủ metadata
  4. Seed 5 users mẫu với interest_tags
  5. Generate embedding cho videos & users qua OpenAI API
  6. Tạo Vector Search Index definition (JSON) để import trên Atlas UI

Yêu cầu:
  pip install motor pymongo openai python-dotenv

Biến môi trường (.env):
  MONGODB_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net/
  OPENAI_API_KEY=sk-...
"""

import asyncio
import json
import os
import random
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
import motor.motor_asyncio
from pymongo import IndexModel, ASCENDING, DESCENDING

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DB_NAME = "gotouchgrass"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

openai_client = OpenAI(api_key=OPENAI_API_KEY)
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = mongo_client[DB_NAME]

# ─── Collections ──────────────────────────────────────────────────────────────
COLLECTIONS = {
    "videos": None,          # Regular collection
    "users": None,           # Regular collection
    "interactions": None,    # Regular collection
    "feed_sessions": None,   # Regular collection
    "behavior_logs": {       # Time-Series collection
        "timeseries": {
            "timeField": "timestamp",
            "metaField": "session_id",
            "granularity": "seconds"
        }
    }
}

# ─── Seed Data Definitions ────────────────────────────────────────────────────
CATEGORIES = ["lifestyle", "education", "entertainment", "sports", "calming", "nature", "gaming", "cooking"]
INTENSITY_DISTRIBUTION = (
    ["high"] * 50 +    # 50%
    ["medium"] * 30 +  # 30%
    ["low"] * 20       # 20%
)

VIDEO_TEMPLATES = [
    # HIGH intensity
    {"title": "Sigma Male Morning Routine 💪", "tags": ["sigma", "motivation", "morning"], "category": "lifestyle", "intensity": "high"},
    {"title": "10 Coding Memes Only Devs Understand 😂", "tags": ["coding", "meme", "programmer"], "category": "entertainment", "intensity": "high"},
    {"title": "Football Edit - Best Goals 2026 🔥", "tags": ["football", "goals", "edit"], "category": "sports", "intensity": "high"},
    {"title": "Dark Humor Compilation Vol.12", "tags": ["dark_humor", "comedy", "meme"], "category": "entertainment", "intensity": "high"},
    {"title": "Extreme Gym Fails 😅", "tags": ["gym", "fails", "funny"], "category": "entertainment", "intensity": "high"},
    {"title": "Relationship Drama Explained ☕", "tags": ["drama", "relationship", "tea"], "category": "lifestyle", "intensity": "high"},
    {"title": "Ragebait: Top 10 Most Controversial Takes", "tags": ["controversy", "ragebait", "opinion"], "category": "entertainment", "intensity": "high"},
    {"title": "CS:GO Clutch Moments That Broke the Internet", "tags": ["gaming", "csgo", "clutch"], "category": "gaming", "intensity": "high"},
    {"title": "AI is Taking Over Your Job (And It's YOUR Fault)", "tags": ["ai", "tech", "controversy"], "category": "education", "intensity": "high"},
    {"title": "NPC Compilation — These People Are Real 💀", "tags": ["npc", "meme", "cringe"], "category": "entertainment", "intensity": "high"},
    # MEDIUM intensity
    {"title": "How I Built a SaaS in 7 Days 🚀", "tags": ["startup", "coding", "saas"], "category": "education", "intensity": "medium"},
    {"title": "Morning Routine of a Minimalist", "tags": ["minimalism", "morning", "lifestyle"], "category": "lifestyle", "intensity": "medium"},
    {"title": "Python Tips You Wish You Knew Earlier", "tags": ["python", "coding", "tips"], "category": "education", "intensity": "medium"},
    {"title": "Street Food Tour - Tokyo Night Markets", "tags": ["food", "travel", "japan"], "category": "cooking", "intensity": "medium"},
    {"title": "Top 5 Books That Changed My Life", "tags": ["books", "self-improvement", "reading"], "category": "education", "intensity": "medium"},
    {"title": "Football Tactics Explained for Beginners", "tags": ["football", "tactics", "education"], "category": "sports", "intensity": "medium"},
    {"title": "My Honest Review: MacBook Pro M3", "tags": ["tech", "review", "apple"], "category": "education", "intensity": "medium"},
    {"title": "Home Workout - No Equipment Needed", "tags": ["gym", "workout", "health"], "category": "lifestyle", "intensity": "medium"},
    # LOW intensity
    {"title": "Rain on Window - 3 Hours Ambience 🌧️", "tags": ["rain", "ambience", "sleep"], "category": "calming", "intensity": "low"},
    {"title": "Slow Travel in Kyoto - Cherry Blossom Season", "tags": ["travel", "japan", "slow_travel"], "category": "nature", "intensity": "low"},
    {"title": "Bread Baking ASMR - Sourdough Process", "tags": ["asmr", "cooking", "bread"], "category": "cooking", "intensity": "low"},
    {"title": "Night Forest Sounds - Deep Sleep Aid", "tags": ["nature", "sleep", "forest"], "category": "nature", "intensity": "low"},
    {"title": "Calming Piano - Lofi Study Session", "tags": ["music", "lofi", "study"], "category": "calming", "intensity": "low"},
    {"title": "Watercolor Painting Timelapse 🎨", "tags": ["art", "painting", "timelapse"], "category": "calming", "intensity": "low"},
    {"title": "Ocean Waves at Sunrise - Meditation Background", "tags": ["ocean", "meditation", "sunrise"], "category": "nature", "intensity": "low"},
]

USER_TEMPLATES = [
    {"username": "sigma_dev_01", "email": "user1@demo.com", "interest_tags": ["coding", "sigma"]},
    {"username": "football_fan_99", "email": "user2@demo.com", "interest_tags": ["football", "sports"]},
    {"username": "chill_vibes_only", "email": "user3@demo.com", "interest_tags": ["calming", "nature"]},
    {"username": "learn_everyday", "email": "user4@demo.com", "interest_tags": ["education", "books"]},
    {"username": "meme_lord_2026", "email": "user5@demo.com", "interest_tags": ["meme", "dark_humor"]},
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_embedding(text: str) -> list[float]:
    """Gọi OpenAI API để lấy embedding vector cho text."""
    print(f"   → Embedding: '{text[:50]}...'")
    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding


def fake_embedding(dim: int = EMBEDDING_DIM) -> list[float]:
    """Tạo vector ngẫu nhiên (dùng khi không có OPENAI_API_KEY)."""
    import math
    vec = [random.gauss(0, 1) for _ in range(dim)]
    magnitude = math.sqrt(sum(x * x for x in vec))
    return [x / magnitude for x in vec]  # normalize to unit vector


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def build_video_doc(template: dict, idx: int, use_real_embedding: bool) -> dict:
    """Tạo một video document theo template."""
    title = template["title"]
    tags = template["tags"]
    # Dùng title + description + category + tags để embedding giàu ngữ nghĩa hơn (như TikTok)
    description = template.get("description", f"Video about {' '.join(tags)} in the {template['category']} category")
    embed_text = f"{title}. {description}. Category: {template['category']}. Tags: {', '.join(tags)}"

    embedding = get_embedding(embed_text) if use_real_embedding else fake_embedding()

    # Simulate engagement numbers based on intensity
    intensity = template["intensity"]
    if intensity == "high":
        views = random.randint(5000, 50000)
        likes = random.randint(500, 8000)
        comments = random.randint(50, 1200)
    elif intensity == "medium":
        views = random.randint(1000, 10000)
        likes = random.randint(100, 2000)
        comments = random.randint(10, 300)
    else:  # low
        views = random.randint(200, 3000)
        likes = random.randint(20, 500)
        comments = random.randint(2, 80)

    trending_score = views * 1 + likes * 3 + comments * 5

    return {
        "title": title,
        "description": f"Auto-generated description for: {title}",
        "url": f"https://cdn.gotouchgrass.demo/videos/video-{idx:03d}.mp4",
        "thumbnail_url": f"https://cdn.gotouchgrass.demo/thumbs/thumb-{idx:03d}.jpg",
        "tags": tags,
        "category": template["category"],
        "intensity_level": intensity,
        "embedding": embedding,
        "view_count": views,
        "like_count": likes,
        "comment_count": comments,
        "trending_score": float(trending_score),
        "creator_id": f"creator_{template['category']}_{idx:03d}",
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }


def build_user_doc(template: dict, tag_video_embeddings: dict[str, list[float]], use_real_embedding: bool) -> dict:
    """Tạo user document với interest_vector từ trung bình embedding của interest_tags."""
    interest_tags = template["interest_tags"]

    # Tính interest_vector = trung bình embedding của các video thuộc interest_tags
    relevant_embeddings = []
    for tag in interest_tags:
        if tag in tag_video_embeddings:
            relevant_embeddings.extend(tag_video_embeddings[tag])

    if relevant_embeddings:
        dim = len(relevant_embeddings[0])
        avg_vector = [
            sum(vec[i] for vec in relevant_embeddings) / len(relevant_embeddings)
            for i in range(dim)
        ]
    else:
        avg_vector = fake_embedding()

    return {
        "username": template["username"],
        "email": template["email"],
        "interest_tags": interest_tags,
        "interest_vector": avg_vector,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }


# ─── Setup Functions ──────────────────────────────────────────────────────────

async def setup_collections():
    """Tạo collections với cấu hình phù hợp."""
    print("\n📦 Setting up collections...")
    existing = await db.list_collection_names()

    for name, options in COLLECTIONS.items():
        if name in existing:
            print(f"   ✅ Collection '{name}' already exists — skipping")
            continue

        if options and "timeseries" in options:
            # Time-series collection cho behavior_logs
            await db.create_collection(name, **options)
            print(f"   ⏱️  Created time-series collection: '{name}'")
        else:
            # Regular collection (implicit creation via insert, but explicit for clarity)
            await db.create_collection(name)
            print(f"   📁 Created collection: '{name}'")


async def setup_indexes():
    """Tạo các regular indexes (Vector Search Index cần tạo thủ công trên Atlas UI)."""
    print("\n🔑 Creating indexes...")

    # videos
    await db.videos.create_indexes([
        IndexModel([("trending_score", DESCENDING)], name="idx_videos_trending"),
        IndexModel([("tags", ASCENDING), ("category", ASCENDING)], name="idx_videos_tags_category"),
        IndexModel([("intensity_level", ASCENDING)], name="idx_videos_intensity"),
    ])
    print("   ✅ videos: trending_score, tags+category, intensity_level")

    # interactions
    await db.interactions.create_indexes([
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_interactions_user_ts"),
        IndexModel([("session_id", ASCENDING)], name="idx_interactions_session"),
        IndexModel([("video_id", ASCENDING)], name="idx_interactions_video"),
    ])
    print("   ✅ interactions: (user_id, timestamp), session_id, video_id")

    # feed_sessions
    await db.feed_sessions.create_indexes([
        IndexModel([("user_id", ASCENDING), ("started_at", DESCENDING)], name="idx_sessions_user_ts"),
        IndexModel([("user_id", ASCENDING), ("ended_at", ASCENDING)], name="idx_sessions_active"),
    ])
    print("   ✅ feed_sessions: (user_id, started_at), (user_id, ended_at)")

    # behavior_logs — only non-ts indexes (ts field is auto-indexed)
    await db.behavior_logs.create_indexes([
        IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_behavior_user_ts"),
    ])
    print("   ✅ behavior_logs: (user_id, timestamp)")


async def seed_videos(use_real_embedding: bool) -> dict[str, list[float]]:
    """Seed 100 video documents. Trả về mapping tag -> [embeddings] cho user seeding."""
    print("\n🎬 Seeding videos...")

    existing_count = await db.videos.count_documents({})
    if existing_count > 0:
        print(f"   ⚠️  Videos collection already has {existing_count} docs — skipping seed")
        # Load existing embeddings cho user seed
        tag_embeddings: dict[str, list[float]] = {}
        async for doc in db.videos.find({}, {"tags": 1, "embedding": 1}):
            for tag in doc.get("tags", []):
                if tag not in tag_embeddings:
                    tag_embeddings[tag] = []
                tag_embeddings[tag].append(doc["embedding"])
        return tag_embeddings

    # Tạo đủ 100 video từ templates (lặp vòng nếu cần)
    video_docs = []
    tag_embeddings: dict[str, list[float]] = {}

    for i in range(100):
        template = VIDEO_TEMPLATES[i % len(VIDEO_TEMPLATES)]
        # Thêm variation vào title để không bị trùng
        varied_template = dict(template)
        varied_template["title"] = f"{template['title']} (Part {i // len(VIDEO_TEMPLATES) + 1})" if i >= len(VIDEO_TEMPLATES) else template["title"]

        doc = build_video_doc(varied_template, i + 1, use_real_embedding)
        video_docs.append(doc)

        # Thu thập embeddings theo tag
        for tag in doc["tags"]:
            if tag not in tag_embeddings:
                tag_embeddings[tag] = []
            tag_embeddings[tag].append(doc["embedding"])

        if (i + 1) % 10 == 0:
            print(f"   📹 Prepared {i + 1}/100 videos...")

    result = await db.videos.insert_many(video_docs)
    print(f"   ✅ Inserted {len(result.inserted_ids)} videos")

    return tag_embeddings


async def seed_users(tag_video_embeddings: dict[str, list[float]], use_real_embedding: bool):
    """Seed 5 user documents."""
    print("\n👥 Seeding users...")

    existing_count = await db.users.count_documents({})
    if existing_count > 0:
        print(f"   ⚠️  Users collection already has {existing_count} docs — skipping seed")
        return

    user_docs = []
    for template in USER_TEMPLATES:
        doc = build_user_doc(template, tag_video_embeddings, use_real_embedding)
        user_docs.append(doc)
        print(f"   👤 Prepared user: {template['username']} | tags: {template['interest_tags']}")

    result = await db.users.insert_many(user_docs)
    print(f"   ✅ Inserted {len(result.inserted_ids)} users")


def print_atlas_vector_index_guide():
    """In hướng dẫn tạo Vector Search Index trên Atlas UI."""
    vector_index_config = {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": EMBEDDING_DIM,
                "similarity": "cosine"
            },
            {
                "type": "filter",
                "path": "intensity_level"
            },
            {
                "type": "filter",
                "path": "category"
            },
            {
                "type": "filter",
                "path": "tags"
            }
        ]
    }

    print("\n" + "=" * 60)
    print("🔍 ATLAS VECTOR SEARCH INDEX — Tạo thủ công trên Atlas UI")
    print("=" * 60)
    print("Vào: Atlas → Search → Create Search Index → JSON Editor")
    print(f"Collection: {DB_NAME}.videos")
    print(f"Index Name: vector_index_videos")
    print("\nJSON Config:")
    print(json.dumps(vector_index_config, indent=2))
    print("=" * 60)

    # Lưu ra file để tiện copy
    with open("vector_search_index.json", "w") as f:
        json.dump(vector_index_config, f, indent=2)
    print("✅ Đã lưu config vào: vector_search_index.json")


async def verify_setup():
    """Kiểm tra kết quả sau khi setup."""
    print("\n✅ Verification:")
    collections = await db.list_collection_names()
    print(f"   Collections: {sorted(collections)}")

    for col_name in ["videos", "users", "interactions", "feed_sessions", "behavior_logs"]:
        if col_name in collections:
            count = await db[col_name].count_documents({})
            indexes = await db[col_name].index_information()
            print(f"   📊 {col_name}: {count} docs | {len(indexes)} indexes")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    use_real_embedding = bool(OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"))

    print("🌱 GoTouchGrass — MongoDB Setup & Seed Script")
    print(f"   Database  : {DB_NAME}")
    print(f"   MongoDB   : {MONGODB_URI[:30]}...")
    print(f"   Embedding : {'OpenAI API (real)' if use_real_embedding else '⚠️  Fake random vectors (set OPENAI_API_KEY)'}")

    try:
        # 1. Tạo collections
        await setup_collections()

        # 2. Tạo indexes
        await setup_indexes()

        # 3. Seed videos (trả về tag→embeddings map)
        tag_embeddings = await seed_videos(use_real_embedding)

        # 4. Seed users
        await seed_users(tag_embeddings, use_real_embedding)

        # 5. Hướng dẫn Vector Search Index
        print_atlas_vector_index_guide()

        # 6. Verify
        await verify_setup()

        print("\n🎉 Setup hoàn tất! Bước tiếp theo:")
        print("   1. Tạo Vector Search Index trên Atlas UI (xem hướng dẫn trên)")
        print("   2. BE Dev: Viết Pydantic models mapping với schema")
        print("   3. FE Dev: Gọi GET /feed/{user_id} với user_id từ seed users")

    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        raise
    finally:
        mongo_client.close()


if __name__ == "__main__":
    asyncio.run(main())
