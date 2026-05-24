import os
import sys
import json
import asyncio
from fastapi.testclient import TestClient

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

async def test_api_endpoints():
    print("==================================================")
    print("🧪 TESTING CLASSIFICATION & UPLOAD API ENDPOINTS 🧪")
    print("==================================================")

    # Use TestClient with lifespan context manager to auto-connect to DB
    with TestClient(app) as client:
        print("\n--- 1. Testing POST /api/v1/videos/train (Model Fine-Tuning) ---")
        response = client.post("/api/v1/videos/train")
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        assert response.status_code == 200, "Train endpoint failed!"
        train_data = response.json()
        if not train_data.get("success"):
            print(f"⚠️ Training skipped/not trained: {train_data.get('message')}")
        else:
            print("✅ Training succeeded!")

        print("\n--- 2. Creating Dummy File for Video Upload ---")
        dummy_file = "dummy_test_video.mp4"
        with open(dummy_file, "wb") as f:
            f.write(b"mock video bytes for testing auto-classification upload")

        try:
            # We omit 'category', 'tags', and 'intensity_level' to trigger the classifier model
            payload = {
                "title": "Making yummy chocolate chip cookies at home 🍪",
                "description": "Follow my step-by-step baking tutorial to cook the perfect crispy cookies. Chef level recipe details in description!",
                "creator_id": "baker_chef_99"
            }

            with open(dummy_file, "rb") as f:
                files = {"file": (dummy_file, f, "video/mp4")}
                # Send the multipart request
                response = client.post(
                    "/api/v1/videos",
                    data=payload,
                    files=files
                )

            print(f"Status Code: {response.status_code}")
            print("Response JSON:")
            response_data = response.json()
            print(json.dumps(response_data, indent=2, ensure_ascii=False))

            assert response.status_code == 201, "Video creation endpoint failed!"
            
            # Category, tags, and intensity should be predicted
            predicted_category = response_data.get("category")
            predicted_tags = response_data.get("tags")
            predicted_intensity = response_data.get("intensity_level")
            
            print(f"\n🔮 Predicted Category: {predicted_category}")
            print(f"🏷️ Predicted Tags: {predicted_tags}")
            print(f"⚡ Predicted Intensity Level: {predicted_intensity}")
            
            assert predicted_category == "cooking", f"Expected category 'cooking', got '{predicted_category}'"
            assert isinstance(predicted_tags, list) and len(predicted_tags) > 0, "No tags predicted!"
            assert "cooking" in predicted_tags or "food" in predicted_tags or "recipe" in predicted_tags or "cookies" in predicted_tags, "Expected relevant tags!"
            assert predicted_intensity == "medium", f"Expected intensity level 'medium', got '{predicted_intensity}'"

            # 4. Verify inside Database using a dedicated connection on our own event loop
            print("\n--- 4. Verifying DB Persistence ---")
            from motor.motor_asyncio import AsyncIOMotorClient
            from app.config import settings
            from bson import ObjectId

            db_client = AsyncIOMotorClient(settings.MONGODB_URI)
            db = db_client[settings.DATABASE_NAME]
            video_id = response_data["id"]
            
            # Query db
            db_doc = await db["videos"].find_one({"_id": ObjectId(video_id)})
            
            print(f"Document in MongoDB:")
            print(f"  ID: {db_doc['_id']}")
            print(f"  Title: {db_doc['title']}")
            print(f"  Category: {db_doc['category']}")
            print(f"  Tags: {db_doc['tags']}")
            print(f"  Intensity Level: {db_doc['intensity_level']}")
            
            assert db_doc["category"] == "cooking", "Category in DB does not match prediction!"
            assert len(db_doc["tags"]) > 0, "Tags list in DB is empty!"
            assert db_doc["intensity_level"] == "medium", "Intensity level in DB does not match prediction!"
            print("\n🎉 DB Persistence Verified successfully!")
            
            db_client.close()

        finally:
            if os.path.exists(dummy_file):
                os.remove(dummy_file)
                print("\nCleaned up dummy file.")

if __name__ == "__main__":
    asyncio.run(test_api_endpoints())
