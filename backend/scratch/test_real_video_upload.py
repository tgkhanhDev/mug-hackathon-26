import os
import httpx

def main():
    url = "http://localhost:8033/api/v1/videos"
    video_file = "videos/mov_bbb.mp4"
    
    if not os.path.exists(video_file):
        print(f"Error: {video_file} not found!")
        return
        
    print(f"Using real video file: {video_file}")
    
    payload = {
        "title": "Big Buck Bunny Test Video 🐰",
        "description": "This is a real video upload test verifying ffmpeg metadata extraction.",
        "creator_id": "6a0bdf9bc0d0a93bff883daa",
    }
    
    print("Sending POST request to upload real video...")
    try:
        with open(video_file, "rb") as f:
            files = {"file": ("mov_bbb.mp4", f, "video/mp4")}
            response = httpx.post(url, data=payload, files=files, timeout=60.0)
            
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        import json
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
