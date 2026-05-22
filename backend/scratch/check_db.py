import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.database import connect_db, disconnect_db
from app.repositories.video_repository import VideoRepository

async def check():
    await connect_db()
    repo = VideoRepository()
    videos = await repo.find_many(limit=100)
    print(f"Total videos: {len(videos)}")
    for v in videos:
        print(f"ID: {v.get('id')} | Title: {v.get('title')} | Cat: {v.get('category')} | Intensity: {v.get('intensity_level')} | Tags: {v.get('tags')}")
    await disconnect_db()

if __name__ == "__main__":
    asyncio.run(check())
