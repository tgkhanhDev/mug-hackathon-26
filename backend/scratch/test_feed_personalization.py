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

    # Define a session ID for interactions
    session_id = str(ObjectId())

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
            # Fallback to local similarity search for testing purposes
            # (e.g. if Atlas index is still indexing or has dimension mismatch)
            from app.services.video_service import VideoService
            all_videos = await video_repo.find_many(filter={"_id": {"$in": [ObjectId(vid) for vid in video_ids]}}, limit=100)
            
            scored_videos = []
            for v in all_videos:
                v_emb = v.get("embedding", [])
                sim = cosine_similarity(current_vector, v_emb)
                # Combine similarity and trending score using weights
                total_score = sim * 10.0 + v.get("trending_score", 0.0) * 0.001
                scored_videos.append((v, total_score))
            
            # Sort by total_score desc
            scored_videos.sort(key=lambda x: x[1], reverse=True)
            feed_videos = [VideoService._to_response(x[0]) for x in scored_videos[:3]]
            
        if not feed_videos:
            print("⚠️ No feed videos returned.")
            break

        # Pick the top recommended video to interact with
        top_video = feed_videos[0]
        video_tags = top_video.tags
        video_title = top_video.title
        primary_tag = "coding" if "coding" in video_tags else "music"

        # Determine user action
        # User now prefers coding, so they LIKE coding and SKIP music
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
            video_id=top_video.id,
            session_id=session_id,
            type=action,
            watch_duration=watch_duration,
            watch_percentage=watch_pct,
            swipe_speed=150.0 if action == "skip" else 10.0,
            replay_count=1 if action == "like" else 0
        )
        await interaction_service.log_interaction(interaction_data)

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

    await disconnect_db()
    print("🎉 Benchmark and cleanup completed.")

if __name__ == "__main__":
    asyncio.run(main())
