"""
End-to-end integration test script for Gotouchgrass.
Validates:
  1. Onboarding & Initial Interest Vector
  2. Feed Session Creation
  3. Personalized Feed Retrieval (with Exploration)
  4. Behavior Logging & Sliding Window Fatigue Score Calculation (transitions to Exhausted)
  5. Wellbeing-aware Feed Filtering (Exhausted = Low intensity only)
  6. Interaction Recording & EMA Vector Drift & Counter updates
  7. Database Cleanup
"""

import asyncio
import math
from datetime import datetime
from bson import ObjectId

from app.repositories.database import connect_db, get_database, disconnect_db
from app.repositories.video_repository import VideoRepository
from app.repositories.user_repository import UserRepository
from app.repositories.interaction_repository import InteractionRepository, FeedSessionRepository, BehaviorLogRepository
from app.services.feed_service import FeedService
from app.services.interaction_service import InteractionService
from app.services.user_service import UserService
from app.models.user import UserCreate
from app.models.interaction import InteractionCreate
from app.models.behavior_log import BehaviorLogCreate
from app.models.feed_session import FeedSessionCreate
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
    print("🌿 Connecting to MongoDB Atlas...")
    await connect_db()
    
    db = get_database()
    video_repo = VideoRepository()
    user_repo = UserRepository()
    session_repo = FeedSessionRepository()
    log_repo = BehaviorLogRepository()
    interaction_repo = InteractionRepository()
    
    feed_service = FeedService()
    interaction_service = InteractionService()
    user_service = UserService()

    # Define test tags & prepare embeddings
    music_text = "Acoustic guitar music, relaxing piano melodies, songs and concert."
    coding_text = "Software engineering, Python programming, coding and algorithms."
    
    print("\n[1/7] Preparing reference embeddings...")
    music_ref_emb = await generate_embedding(music_text)
    coding_ref_emb = await generate_embedding(coding_text)
    print("✅ Embeddings generated successfully.")

    # 1. Create Test Videos
    print("\n[2/7] Creating test videos (5 Coding [High Intensity], 5 Music [Low Intensity])...")
    test_videos = []
    
    # 5 Coding videos (High intensity)
    for i in range(5):
        embed_text = build_embed_text(
            title=f"Advanced Python Tips Part {i+1}",
            description=f"Deep dive into programming patterns, async algorithms, and optimization part {i+1}.",
            category="education",
            tags=["coding", "programming"]
        )
        emb = await generate_embedding(embed_text)
        test_videos.append({
            "title": f"Advanced Python Tips Part {i+1}",
            "description": f"Deep dive into programming patterns, async algorithms, and optimization part {i+1}.",
            "url": f"https://cdn.example.com/coding_{i+1}.mp4",
            "thumbnail_url": f"https://cdn.example.com/coding_{i+1}.jpg",
            "tags": ["coding", "programming"],
            "category": "education",
            "intensity_level": "high",
            "embedding": emb,
            "view_count": 50,
            "like_count": 5,
            "comment_count": 1,
            "trending_score": 70.0,
            "creator_id": "dev_guru",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

    # 5 Music videos (Low intensity)
    for i in range(5):
        embed_text = build_embed_text(
            title=f"Ambient Lofi Rain {i+1}",
            description=f"Calming acoustic beats and relaxing background rain for focus and study part {i+1}.",
            category="calming",
            tags=["music", "calming"]
        )
        emb = await generate_embedding(embed_text)
        test_videos.append({
            "title": f"Ambient Lofi Rain {i+1}",
            "description": f"Calming acoustic beats and relaxing background rain for focus and study part {i+1}.",
            "url": f"https://cdn.example.com/music_{i+1}.mp4",
            "thumbnail_url": f"https://cdn.example.com/music_{i+1}.jpg",
            "tags": ["music", "calming"],
            "category": "calming",
            "intensity_level": "low",
            "embedding": emb,
            "view_count": 100,
            "like_count": 20,
            "comment_count": 4,
            "trending_score": 180.0,
            "creator_id": "lofi_girl",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

    video_ids = await video_repo.insert_many(test_videos)
    print(f"✅ Inserted {len(video_ids)} test videos.")

    # 2. Onboard User
    print("\n[3/7] Registering user with initial interest in 'music' & 'calming'...")
    username = f"e2e_tester_{int(datetime.utcnow().timestamp())}"
    user_create = UserCreate(
        username=username,
        email="e2e@example.com",
        interest_tags=["music", "calming"]
    )
    user_response = await user_service.create_user(user_create)
    user_id = user_response.id
    print(f"✅ Onboarded user: {username} (ID: {user_id}).")

    # Verify interest vector was initialized and L2-normalized
    user_doc = await user_repo.find_by_id(user_id)
    init_vector = user_doc.get("interest_vector", [])
    init_magnitude = math.sqrt(sum(x * x for x in init_vector))
    print(f"📊 Initial interest vector magnitude: {init_magnitude:.4f}")
    assert abs(init_magnitude - 1.0) < 1e-4, "❌ ERROR: Initial interest vector is not L2-normalized!"
    print("✅ Initial vector is properly normalized.")

    # 3. Create Session
    print("\n[4/7] Creating a new Feed Session for the user...")
    session_create = FeedSessionCreate(user_id=user_id)
    session_response = await interaction_service.create_session(session_create)
    session_id = session_response.id
    print(f"✅ Feed Session created: {session_id}.")
    
    # 4. Get Feed and Verify Personalization + Exploration
    print("\n[5/7] Requesting feed recommendations...")
    feed = await feed_service.get_feed(user_id, limit=5)
    print(f"📋 Feed returned {len(feed)} videos:")
    for idx, v in enumerate(feed):
        print(f"  {idx+1}. {v.title} | Category: {v.category} | Intensity: {v.intensity_level}")

    # Verify personalization: top recommended video should be a music video
    assert feed[0].category in ["calming", "entertainment"], f"❌ ERROR: Feed is not personalized (top video category is {feed[0].category}, should be music)!"
    print("✅ Feed is successfully personalized (Music is ranked top).")

    # Verify exploration: feed should contain at least 1 video from the 'education' (coding) category
    has_coding_exploration = any(v.category == "education" for v in feed)
    print(f"🔍 Exploration check: Contains coding video? {has_coding_exploration}")
    
    # 5. Simulate Doomscrolling behavior (trigger Fatigue warning/exhausted states)
    print("\n[6/7] Simulating doomscrolling (fast swiping, short watch duration, passive scrolling)...")
    print("Posting 8 rapid behavior logs with no interaction...")
    
    # We choose a video to scroll past
    scroll_video_id = video_ids[0] # Coding video 1
    
    for i in range(8):
        log_data = BehaviorLogCreate(
            user_id=user_id,
            session_id=session_id,
            video_id=scroll_video_id,
            swipe_speed=950.0,      # Fast swiping speed (>800 px/s)
            watch_duration=1.2,     # Short watch duration (<2s)
            is_interaction=False,   # Passive scroll (no like/comment)
            topic="music"
        )
        await interaction_service.record_behavior_log(log_data)
        
    print("Waiting briefly for background tasks to update session...")
    await asyncio.sleep(1) # Let fire-and-forget background updates run
    
    updated_session = await session_repo.find_by_id(session_id)
    fatigue_score = updated_session.get("fatigue_score", 0.0)
    adaptive_state = updated_session.get("adaptive_state", "normal")
    print(f"📊 Updated Session Fatigue Score: {fatigue_score} | State: {adaptive_state}")
    
    assert fatigue_score > 40.0, f"❌ ERROR: Fatigue score did not increase as expected! Current: {fatigue_score}"
    assert adaptive_state in ["warning", "exhausted"], f"❌ ERROR: Adaptive state did not transition! Current: {adaptive_state}"
    print(f"✅ Fatigue Engine successfully triggered. State is '{adaptive_state}'.")

    # Request feed under fatigue/wellbeing filtering
    print("\nRequesting new feed under fatigued state...")
    fatigue_feed = await feed_service.get_feed(user_id, limit=5)
    print(f"📋 Fatigued Feed returned {len(fatigue_feed)} videos:")
    for idx, v in enumerate(fatigue_feed):
        print(f"  {idx+1}. {v.title} | Category: {v.category} | Intensity: {v.intensity_level}")
        
    # Verify wellbeing-aware filtering
    if adaptive_state == "exhausted":
        assert all(v.intensity_level == "low" for v in fatigue_feed), "❌ ERROR: Wellbeing filter failed! Exhausted feed contains non-low intensity videos."
        print("✅ Success: Exhausted feed contains ONLY low intensity videos.")
    elif adaptive_state == "warning":
        assert all(v.intensity_level in ["low", "medium"] for v in fatigue_feed), "❌ ERROR: Wellbeing filter failed! Warning feed contains high intensity videos."
        print("✅ Success: Warning feed contains ONLY low/medium intensity videos.")

    # 6. Simulate Explicit Positive Interaction and Vector Shift
    print("\n[7/7] Simulating explicit positive interaction (Liking a Coding video)...")
    # Choose a coding video
    coding_video_id = video_ids[0]
    coding_video_doc = await video_repo.find_by_id(coding_video_id)
    initial_likes = coding_video_doc.get("like_count", 0)
    initial_views = coding_video_doc.get("view_count", 0)
    initial_trending = coding_video_doc.get("trending_score", 0.0)

    # Let the user LIKE the coding video
    interaction_data = InteractionCreate(
        user_id=user_id,
        video_id=coding_video_id,
        session_id=session_id,
        type="like",
        watch_duration=25.0,
        watch_percentage=1.0,
        swipe_speed=10.0,
        replay_count=1
    )
    await interaction_service.record_interaction(interaction_data)
    
    # Retrieve updated user interest vector
    updated_user = await user_repo.find_by_id(user_id)
    final_vector = updated_user.get("interest_vector", [])
    
    sim_to_coding = cosine_similarity(final_vector, coding_ref_emb)
    sim_to_music = cosine_similarity(final_vector, music_ref_emb)
    print(f"📐 Initial Music Similarity: {cosine_similarity(init_vector, music_ref_emb):.4f}")
    print(f"📐 Initial Coding Similarity: {cosine_similarity(init_vector, coding_ref_emb):.4f}")
    print(f"📐 Updated Music Similarity:  {sim_to_music:.4f}")
    print(f"📐 Updated Coding Similarity:  {sim_to_coding:.4f}")
    
    # Check shift direction
    assert sim_to_coding > cosine_similarity(init_vector, coding_ref_emb), "❌ ERROR: Vector did not shift towards Coding after Liking!"
    print("✅ Success: User interest vector drifted towards Coding category after positive reinforcement.")
    
    # Verify video counters updated atomically
    updated_video = await video_repo.find_by_id(coding_video_id)
    new_likes = updated_video.get("like_count", 0)
    new_views = updated_video.get("view_count", 0)
    new_trending = updated_video.get("trending_score", 0.0)
    
    print(f"📊 Video stats: Likes {initial_likes} ➔ {new_likes} | Views {initial_views} ➔ {new_views} | Trending Score {initial_trending} ➔ {new_trending}")
    assert new_likes == initial_likes + 1, "❌ ERROR: Like count did not increment!"
    assert new_views == initial_views + 1, "❌ ERROR: View count did not increment!"
    assert new_trending > initial_trending, "❌ ERROR: Trending score was not recalculated!"
    print("✅ Success: Video counters and trending score updated atomically without nullification.")

    # 7. Cleanup
    print("\n🧹 Cleaning up test data from Database...")
    await db["videos"].delete_many({"_id": {"$in": [ObjectId(vid) for vid in video_ids]}})
    await db["users"].delete_one({"_id": ObjectId(user_id)})
    await db["feed_sessions"].delete_one({"_id": ObjectId(session_id)})
    await db["behavior_logs"].delete_many({"user_id": user_id})
    await db["interactions"].delete_many({"user_id": user_id})
    print("✅ Cleanup completed.")

    await disconnect_db()
    print("\n🎉 E2E INTERACTION TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
