"""
Test script to simulate 20 scrolls (user interactions) and verify personalized feed adaptation.
"""

import asyncio
import math
from datetime import datetime
from bson import ObjectId

from app.repositories.database import connect_db, get_database, disconnect_db
from app.repositories.video_repository import VideoRepository
from app.repositories.user_repository import UserRepository
from app.repositories.interaction_repository import InteractionRepository
from app.services.feed_service import FeedService
from app.services.interaction_service import InteractionService
from app.models.user import UserCreate
from app.models.video import VideoInDB
from app.models.interaction import InteractionCreate
from app.utils.embedding import generate_embedding, build_embed_text

# Cosine similarity helper
def cosine_similarity(v1, v2):
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm1 = math.sqrt(sum(x * x for x in v1))
    norm2 = math.sqrt(sum(y * y for y in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)

async def main():
    print("🌿 Connecting to MongoDB...")
    await connect_db()
    
    db = get_database()
    video_repo = VideoRepository()
    user_repo = UserRepository()
    interaction_repo = InteractionRepository()
    
    feed_service = FeedService()
    interaction_service = InteractionService()

    print("\n--- [1/5] Creating Test Videos (5 Coding, 5 Music) ---")
    # Generate vectors using configured embedding utility
    coding_text = "Software engineering, Python programming, coding and algorithms."
    music_text = "Acoustic guitar music, relaxing piano melodies, songs and concert."
    
    print("Generating reference embeddings...")
    coding_ref_emb = await generate_embedding(coding_text)
    music_ref_emb = await generate_embedding(music_text)
    dim = len(coding_ref_emb)
    print(f"✅ Generated embeddings ({dim} dimensions).")

    test_videos = []
    
    # 5 Coding videos
    for i in range(5):
        embed_text = build_embed_text(
            title=f"Coding Hack {i+1}",
            description=f"Learn clean code and Python programming tips part {i+1}.",
            category="technology",
            tags=["coding", "programming"]
        )
        emb = await generate_embedding(embed_text)
        test_videos.append({
            "title": f"Coding Hack {i+1}",
            "description": f"Learn clean code and Python programming tips part {i+1}.",
            "url": f"https://cdn.example.com/coding_{i+1}.mp4",
            "thumbnail_url": f"https://cdn.example.com/coding_{i+1}.jpg",
            "tags": ["coding", "programming"],
            "category": "technology",
            "intensity_level": "high",
            "embedding": emb,
            "view_count": 100,
            "like_count": 10,
            "comment_count": 2,
            "trending_score": 140.0,
            "creator_id": "dev_guru",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

    # 5 Music videos
    for i in range(5):
        embed_text = build_embed_text(
            title=f"Lo-Fi Beats {i+1}",
            description=f"Relaxing lofi tracks and acoustic melodies part {i+1}.",
            category="entertainment",
            tags=["music", "calming"]
        )
        emb = await generate_embedding(embed_text)
        test_videos.append({
            "title": f"Lo-Fi Beats {i+1}",
            "description": f"Relaxing lofi tracks and acoustic melodies part {i+1}.",
            "url": f"https://cdn.example.com/music_{i+1}.mp4",
            "thumbnail_url": f"https://cdn.example.com/music_{i+1}.jpg",
            "tags": ["music", "calming"],
            "category": "entertainment",
            "intensity_level": "low",
            "embedding": emb,
            "view_count": 200,
            "like_count": 30,
            "comment_count": 5,
            "trending_score": 315.0,
            "creator_id": "lofi_girl",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

    print("Inserting test videos into database...")
    video_ids = await video_repo.insert_many(test_videos)
    print(f"✅ Inserted {len(video_ids)} test videos.")

    print("\n--- [2/5] Creating Test User Profile ---")
    # Clean up existing test user if any
    existing_user = await user_repo.find_by_username("tester_sim_20")
    if existing_user:
        await user_repo.delete_one(existing_user["id"])
        await db["interactions"].delete_many({"user_id": existing_user["id"]})
        print("🗑️ Cleaned up pre-existing test user and interactions.")

    # User onboards with initial interest in "music" and "calming"
    user_doc = {
        "username": "tester_sim_20",
        "email": "tester@example.com",
        "interest_tags": ["music", "calming"],
        "interest_vector": music_ref_emb,  # Onboarded to like music
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    user_id = await user_repo.insert_one(user_doc)
    print(f"✅ Created test user: {user_id} with initial interest in 'music'.")

    # Create Feed Session to enable exploration mechanism
    from app.models.feed_session import FeedSessionCreate
    session_create = FeedSessionCreate(user_id=user_id)
    session_response = await interaction_service.create_session(session_create)
    session_id = session_response.id
    print(f"✅ Feed Session created: {session_id}.")

    # Mock vector search and find trending to query only our test videos (bypassing Atlas indexing latency)
    from typing import Optional, Dict, Any
    async def mock_vector_search(
        query_vector: list[float],
        limit: int = 10,
        num_candidates: int = 100,
        filter_stage: Optional[Dict[str, Any]] = None,
        search_weight: float = 100.0,
        trending_weight: float = 1.0,
    ) -> list[dict[str, Any]]:
        query_filter = {"_id": {"$in": [ObjectId(vid) for vid in video_ids]}}
        if filter_stage:
            query_filter.update(filter_stage)
        
        all_v = await video_repo.find_many(filter=query_filter, limit=100)
        
        scored = []
        for v in all_v:
            v_emb = v.get("embedding", [])
            sim = cosine_similarity(query_vector, v_emb)
            
            views = v.get("view_count", 0)
            likes = v.get("like_count", 0)
            comments = v.get("comment_count", 0)
            trending_score = views * 1 + likes * 3 + comments * 5
            
            search_score = sim
            total_score = search_score * search_weight + trending_score * trending_weight
            scored.append((v, total_score))
            
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored[:limit]]

    async def mock_find_trending(
        limit: int = 10,
        filter_stage: Optional[Dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        query_filter = {"_id": {"$in": [ObjectId(vid) for vid in video_ids]}}
        if filter_stage:
            query_filter.update(filter_stage)
        
        all_v = await video_repo.find_many(filter=query_filter, limit=100)
        
        scored = []
        for v in all_v:
            views = v.get("view_count", 0)
            likes = v.get("like_count", 0)
            comments = v.get("comment_count", 0)
            trending_score = views * 1 + likes * 3 + comments * 5
            scored.append((v, trending_score))
            
        scored.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored[:limit]]

    # Apply the mocks to feed_service's video repository instance
    feed_service._video_repo.vector_search = mock_vector_search
    feed_service._video_repo.find_trending = mock_find_trending

    print("\n--- [3/5] Starting 20-Scroll Feed Simulation ---")
    print("User is onboarded to 'music' but now wants to watch 'coding' videos.")
    print("We will like 'coding' videos (positive reinforcement) and skip 'music' videos (negative reinforcement).")
    print("-" * 80)
    print(f"{'Scroll':<8} | {'Recommended Top Video':<20} | {'Tag':<10} | {'Action':<6} | {'Sim to Coding':<13} | {'Sim to Music':<13}")
    print("-" * 80)

    current_vector = music_ref_emb

    for scroll in range(20):
        # 1. Fetch Feed (Fetch 3 candidate videos)
        feed_videos = await feed_service.get_feed(user_id, limit=3)
        if not feed_videos:
            print("⚠️ No feed videos returned.")
            break

        # Pick the video to interact with:
        # If there is any coding video in the feed, user scrolls to it and likes it.
        # Otherwise, they interact with the top video (music) and skip it.
        interacted_video = None
        for v in feed_videos:
            if "coding" in v.tags:
                interacted_video = v
                break
        
        if not interacted_video:
            interacted_video = feed_videos[0]

        video_tags = interacted_video.tags
        video_title = interacted_video.title
        primary_tag = "coding" if "coding" in video_tags else "music"

        # Determine user action
        if "coding" in video_tags:
            action = "like"
            watch_pct = 1.0
            watch_duration = 30.0
        else:
            action = "skip"
            watch_pct = 0.1
            watch_duration = 2.0

        # Log Interaction (This will update user's interest vector in real-time)
        interaction_data = InteractionCreate(
            user_id=user_id,
            video_id=interacted_video.id,
            session_id=session_id,
            type=action,
            watch_duration=watch_duration,
            watch_percentage=watch_pct,
            swipe_speed=150.0 if action == "skip" else 10.0,
            replay_count=1 if action == "like" else 0
        )
        await interaction_service.record_interaction(interaction_data)

        # Retrieve updated user profile to check vector drift
        updated_user = await user_repo.find_by_id(user_id)
        current_vector = updated_user.get("interest_vector", [])

        sim_to_coding = cosine_similarity(current_vector, coding_ref_emb)
        sim_to_music = cosine_similarity(current_vector, music_ref_emb)

        print(f"Scroll {scroll+1:02d} | {video_title:<20} | {primary_tag:<10} | {action.upper():<6} | {sim_to_coding:.4f}        | {sim_to_music:.4f}")

    print("-" * 80)

    print("\n--- [4/5] Final Vector Similarity Evaluation ---")
    final_user = await user_repo.find_by_id(user_id)
    final_vector = final_user.get("interest_vector", [])
    final_sim_coding = cosine_similarity(final_vector, coding_ref_emb)
    final_sim_music = cosine_similarity(final_vector, music_ref_emb)
    print(f"🏁 Final similarity to Coding Vector: {final_sim_coding:.4f}")
    print(f"🏁 Final similarity to Music Vector:  {final_sim_music:.4f}")
    
    if final_sim_coding > final_sim_music:
        print("\n🎉 SUCCESS: The feed has adapted correctly! The user's interest shifted from music to coding.")
    else:
        print("\n❌ FAILURE: The interest vector did not shift as expected.")

    print("\n--- [5/5] Cleaning Up Database ---")
    # Delete test videos
    video_collection = db["videos"]
    await video_collection.delete_many({"_id": {"$in": [ObjectId(vid) for vid in video_ids]}})
    print("🗑️ Cleaned up test videos.")

    # Delete test user
    await user_repo.delete_one(user_id)
    print("🗑️ Cleaned up test user.")

    # Delete test interactions
    await db["interactions"].delete_many({"user_id": user_id})
    print("🗑️ Cleaned up test interactions.")

    # Delete feed session
    await db["feed_sessions"].delete_one({"_id": ObjectId(session_id)})
    print("🗑️ Cleaned up feed session.")

    await disconnect_db()
    print("🎉 Benchmark and cleanup completed.")

if __name__ == "__main__":
    asyncio.run(main())
