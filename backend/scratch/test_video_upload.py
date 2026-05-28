import os
import httpx

def main():
    url = "http://localhost:8033/api/v1/videos"
    
    # Create a dummy video file
    dummy_file = "dummy_video.mp4"
    with open(dummy_file, "wb") as f:
        f.write(b"fake video content for testing S3 upload and MongoDB metadata saving")
        
    print(f"Created dummy file: {dummy_file}")
    
    payload = {
        "title": "Test direct upload video 🌿",
        "description": "This is a direct upload test from python script with omitted fields.",
        "tags": "test, upload, direct, python, optional",
        "category": "lifestyle",
        "intensity_level": "low",
        "creator_id": "6a0bdf9bc0d0a93bff883daa",
    }
    
    print("Sending POST request to direct upload endpoint...")
    try:
        with open(dummy_file, "rb") as f:
            files = {"file": (dummy_file, f, "video/mp4")}
            response = httpx.post(url, data=payload, files=files, timeout=60.0)
            
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        import json
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if os.path.exists(dummy_file):
            os.remove(dummy_file)
            print("Cleaned up dummy file.")

if __name__ == "__main__":
    main()
