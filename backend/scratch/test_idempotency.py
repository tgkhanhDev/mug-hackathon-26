import asyncio
import logging
import sys
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# Configure logger to capture task execution logs
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# MongoDB configuration
MONGODB_URI = "mongodb+srv://nguyenhoangan03study_db_user:Cytr1NtuWnd4LLfY@cluster0.dzjbtvv.mongodb.net/gotouchgrass?retryWrites=true&w=majority&appName=Cluster0"
DATABASE_NAME = "gotouchgrass"

async def test_task_idempotency():
    print("🧪 Starting Task Idempotency Test...")
    
    # 1. Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    videos_collection = db["videos"]
    
    # 2. Insert a video document already marked as "completed"
    now = datetime.utcnow()
    completed_video = {
        "title": "Idempotent Video Test",
        "description": "Mock video already processed",
        "url": "http://localhost:9000/gotouchgrass-media/videos/mock-folder/playlist.m3u8",
        "thumbnail_url": "http://localhost:9000/gotouchgrass-media/videos/mock-folder/thumbnail.jpg",
        "tags": ["test"],
        "category": "nature",
        "intensity_level": "low",
        "status": "completed",
        "embedding": [0.1] * 384,
        "view_count": 10,
        "like_count": 5,
        "comment_count": 2,
        "trending_score": 35.0,
        "creator_id": "test_idempotent_creator",
        "duration": 15.0,
        "width": 1920,
        "height": 1080,
        "created_at": now,
        "updated_at": now,
    }
    
    insert_result = await videos_collection.insert_one(completed_video)
    video_id = str(insert_result.inserted_id)
    print(f"✅ Inserted completed video with ID: {video_id}")
    
    try:
        # Import the async task runner
        # Add root path to sys.path to enable app imports
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        
        from app.tasks import _process_video_async
        
        # 3. Call _process_video_async directly
        # We pass a non-existent path for temp_video_path. 
        # If the idempotency check fails, the function will attempt to read this file and raise an error or warning.
        # If idempotency check works, it should return early with none of those errors.
        print("Invoking _process_video_async directly...")
        
        # We wrap the invocation to verify it completes without errors or file access failures
        await _process_video_async(
            video_id=video_id,
            temp_video_path="/nonexistent/path/to/video.mp4",
            video_folder_id="mock-folder-id",
            title="Idempotent Video Test",
            description="Mock video already processed",
            creator_id="test_idempotent_creator",
            view_count=10,
            like_count=5,
            comment_count=2
        )
        
        print("🎉 Success! The task returned early without trying to process the nonexistent video file.")
        
    except Exception as e:
        print(f"❌ Failure! Task execution raised an exception: {e}")
        
    finally:
        # 4. Clean up MongoDB
        await videos_collection.delete_one({"_id": ObjectId(video_id)})
        print("Sweep completed. Cleaned up mock database record.")
        client.close()

if __name__ == "__main__":
    asyncio.run(test_task_idempotency())
