import asyncio
import httpx
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# MongoDB configuration
MONGODB_URI = "mongodb+srv://nguyenhoangan03study_db_user:Cytr1NtuWnd4LLfY@cluster0.dzjbtvv.mongodb.net/gotouchgrass?retryWrites=true&w=majority&appName=Cluster0"
DATABASE_NAME = "gotouchgrass"

async def test_stuck_video_cleanup():
    print("🧪 Starting Stuck Video Cleanup Job Test...")
    
    # 1. Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    videos_collection = db["videos"]
    
    # 2. Insert a fake video document that was created 20 minutes ago and is still "processing"
    now = datetime.utcnow()
    twenty_mins_ago = now - timedelta(minutes=20)
    
    test_video = {
        "title": "Test Stuck Video",
        "description": "This is a mock video for testing robustness cleanup",
        "url": "",
        "thumbnail_url": "",
        "tags": [],
        "category": "",
        "intensity_level": "",
        "status": "processing",
        "embedding": [],
        "view_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "trending_score": 0.0,
        "creator_id": "test_robustness_creator",
        "duration": None,
        "width": None,
        "height": None,
        "created_at": twenty_mins_ago,
        "updated_at": twenty_mins_ago,
    }
    
    insert_result = await videos_collection.insert_one(test_video)
    video_id = str(insert_result.inserted_id)
    print(f"✅ Inserted mock processing video with ID: {video_id}, created_at: {twenty_mins_ago.isoformat()}")
    
    try:
        # 3. Call the FastAPI endpoint to manually trigger the cleanup scheduler job
        cleanup_url = "http://localhost:8033/api/v1/scheduler/cleanup/trigger"
        print(f"Triggering cleanup job via POST {cleanup_url}...")
        
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(cleanup_url)
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.json()}")
            
        # 4. Fetch the video again and verify status is now "failed"
        updated_video = await videos_collection.find_one({"_id": ObjectId(video_id)})
        status = updated_video.get("status")
        print(f"Retrieved video status after cleanup: '{status}'")
        
        if status == "failed":
            print("🎉 Success! The stuck video was correctly updated to status='failed'.")
        else:
            print(f"❌ Failure! Expected status='failed', but got '{status}'.")
            
    finally:
        # 5. Clean up the database record
        delete_result = await videos_collection.delete_one({"_id": ObjectId(video_id)})
        print(f"🧹 Cleaned up DB record for test video. Deleted count: {delete_result.deleted_count}")
        client.close()

if __name__ == "__main__":
    asyncio.run(test_stuck_video_cleanup())
