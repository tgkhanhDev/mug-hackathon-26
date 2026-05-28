import asyncio
import httpx
import os
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# MongoDB configuration
MONGODB_URI = "mongodb+srv://nguyenhoangan03study_db_user:Cytr1NtuWnd4LLfY@cluster0.dzjbtvv.mongodb.net/gotouchgrass?retryWrites=true&w=majority&appName=Cluster0"
DATABASE_NAME = "gotouchgrass"

async def test_rabbitmq_disconnection():
    print("🧪 Starting RabbitMQ Disconnection Test...")
    
    # 1. Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    videos_collection = db["videos"]
    
    # 2. Create a dummy file to upload
    dummy_filepath = "scratch/temp_test_video.mp4"
    os.makedirs("scratch", exist_ok=True)
    with open(dummy_filepath, "wb") as f:
        f.write(b"fake video data")
    
    try:
        # 3. Send upload request to FastAPI
        upload_url = "http://localhost:8033/api/v1/videos"
        print(f"Sending POST request to {upload_url}...")
        
        # Prepare form data and files
        data = {
            "title": "Test Broker Failure Video",
            "description": "Testing FastAPI 503 response when Celery broker is down",
            "creator_id": "test_broker_creator"
        }
        
        # Use httpx to send a multipart/form-data request
        async with httpx.AsyncClient() as http_client:
            with open(dummy_filepath, "rb") as video_file:
                files = {"file": ("temp_test_video.mp4", video_file, "video/mp4")}
                # Set a longer timeout in case RabbitMQ library has internal retry delays before failing
                response = await http_client.post(upload_url, data=data, files=files, timeout=15.0)
                
        print(f"Response status code: {response.status_code}")
        try:
            response_json = response.json()
            print(f"Response body: {response_json}")
        except Exception:
            response_json = {}
            print(f"Response text: {response.text}")
            
        # 4. Verify 503 Service Unavailable
        if response.status_code == 503:
            print("🎉 Success! API returned 503 Service Unavailable as expected.")
        else:
            print(f"❌ Failure! Expected 503 Service Unavailable, but got {response.status_code}.")

        # 5. Retrieve the video placeholder from MongoDB
        # We find the video by creator_id
        placeholder = await videos_collection.find_one({"creator_id": "test_broker_creator"})
        if placeholder:
            status = placeholder.get("status")
            print(f"Retrieved video status in database: '{status}'")
            if status == "failed_queue":
                print("🎉 Success! Placeholder video status in DB was updated to 'failed_queue'.")
            else:
                print(f"❌ Failure! Expected status='failed_queue', but got '{status}'.")
                
            # Clean up the document
            await videos_collection.delete_one({"_id": placeholder["_id"]})
            print("🧹 Cleaned up DB record for test video.")
        else:
            print("❌ Failure! Video placeholder was not found in MongoDB.")
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        
    finally:
        # Clean up temporary test file
        if os.path.exists(dummy_filepath):
            os.remove(dummy_filepath)
        client.close()

if __name__ == "__main__":
    asyncio.run(test_rabbitmq_disconnection())
