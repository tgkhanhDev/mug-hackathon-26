#!/usr/bin/env python
"""
Pexels Video Crawler.
Downloads high-quality videos from Pexels and registers them in the MongoDB database
using the app's Video model, repositories, and services layer.
"""

# python crawl_pexels.py --query nature --category nature --intensity low --limit 100

import os
import sys
import argparse
import asyncio
import logging
from typing import List, Dict
import httpx
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pexels_crawler")

# Load environment variables from .env
load_dotenv()

# Add root folder to sys.path to ensure absolute imports from 'app' work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.repositories.database import connect_db, disconnect_db
from app.services.video_service import VideoService
from app.models.video import VideoCreate, CATEGORY_ENUM, INTENSITY_ENUM


# Predefined list of search configurations covering multiple categories
PRESET_TASKS = [
    {"query": "nature", "category": "nature", "intensity_level": "low"},
    {"query": "meditation", "category": "calming", "intensity_level": "low"},
    {"query": "cooking", "category": "cooking", "intensity_level": "medium"},
    {"query": "fitness", "category": "sports", "intensity_level": "high"},
    {"query": "gaming", "category": "gaming", "intensity_level": "high"},
    {"query": "programming", "category": "education", "intensity_level": "medium"},
    {"query": "travel", "category": "lifestyle", "intensity_level": "medium"},
    {"query": "dance", "category": "entertainment", "intensity_level": "high"},
    {"query": "animals", "category": "animals", "intensity_level": "low"},
    {"query": "art", "category": "art", "intensity_level": "medium"},
    {"query": "music", "category": "music", "intensity_level": "medium"},
    {"query": "funny", "category": "comedy", "intensity_level": "high"},
    {"query": "fashion", "category": "fashion", "intensity_level": "medium"},
    {"query": "cars", "category": "automotive", "intensity_level": "high"},
    {"query": "space", "category": "space", "intensity_level": "low"},
]


def extract_title_from_url(url: str, query: str, photographer: str) -> str:
    """
    Extract a descriptive title from Pexels video URL slug.
    Example: https://www.pexels.com/video/snow-covered-trees-1851190/ -> "Snow covered trees"
    """
    try:
        path_parts = url.rstrip("/").split("/")
        if len(path_parts) > 0:
            slug = path_parts[-1]
            words = slug.split("-")
            # If the last word is the numeric ID, remove it
            if words and words[-1].isdigit():
                words = words[:-1]
            if words:
                return " ".join(words).capitalize()
    except Exception as e:
        logger.debug(f"Could not parse title from URL slug: {e}")
    
    return f"{query.capitalize()} video by {photographer}"


def generate_tags(query: str, title: str) -> List[str]:
    """
    Generates a list of valid, clean tags from the query and title words.
    Filters out common stop words to keep tags relevant.
    """
    tags = {query.lower()}
    stop_words = {
        "a", "an", "the", "of", "in", "on", "at", "by", "for", "with", "and", "or", 
        "to", "from", "video", "shot", "footage", "pexels", "free", "stock", "some", "many"
    }
    
    # Extract words from the title
    for word in title.lower().split():
        cleaned = "".join(c for c in word if c.isalnum())
        if cleaned and cleaned not in stop_words and len(cleaned) > 2:
            tags.add(cleaned)
            
    # Schema validation requires tags list length to be 1 to 10
    return list(tags)[:10]


async def crawl_pexels(
    tasks: List[Dict[str, str]],
    limit: int,
    creator_id: str,
    api_key: str,
    db_url_mode: str,
):
    """
    Crawl videos from Pexels for a list of tasks, download them locally,
    and save their metadata and embeddings into MongoDB.
    """
    if not api_key:
        logger.error(
            "Pexels API key is required. Please set it in your .env as PEXELS_API_KEY "
            "or pass it via --api-key argument."
        )
        sys.exit(1)

    # Ensure local storage directory exists
    os.makedirs("videos", exist_ok=True)

    headers = {
        "Authorization": api_key
    }
    
    # Initialize database connection once for all tasks
    logger.info("🔌 Connecting to MongoDB...")
    await connect_db()
    video_service = VideoService()

    async with httpx.AsyncClient() as client:
        try:
            for task in tasks:
                query = task["query"]
                category = task["category"]
                intensity_level = task["intensity_level"]
                
                logger.info("=" * 60)
                logger.info(f"🚀 Crawling Topic: '{query}' -> Category: '{category}' (Intensity: {intensity_level})")
                logger.info("=" * 60)
                
                # Call Pexels Video Search API
                url = f"https://api.pexels.com/videos/search?query={query}&per_page={limit}"
                
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                except Exception as e:
                    logger.error(f"❌ Failed to query Pexels API for '{query}': {e}")
                    continue

                data = response.json()
                videos = data.get("videos", [])
                logger.info(f"🎥 Found {len(videos)} videos for '{query}' from Pexels API.")

                if not videos:
                    logger.warning(f"No videos found matching query: {query}")
                    continue

                for index, video in enumerate(videos):
                    video_id = video.get("id")
                    video_url_page = video.get("url", "")
                    photographer = video.get("user", {}).get("name", "Unknown Photographer")

                    logger.info("-" * 50)
                    logger.info(f"⏳ Processing video {index + 1}/{len(videos)} of query '{query}' (ID: {video_id})")

                    # Extract title
                    title = extract_title_from_url(video_url_page, query, photographer)
                    title = title[:500]

                    # Construct description
                    description = f"High-quality {query} video shot by {photographer} on Pexels."
                    description = description[:2000]

                    # Find best quality MP4 file
                    video_files = video.get("video_files", [])
                    if not video_files:
                        logger.warning(f"⚠️ No video files found for video ID {video_id}. Skipping.")
                        continue

                    # Filter specifically for video/mp4 files
                    mp4_files = [
                        f for f in video_files 
                        if f.get("file_type") == "video/mp4" or "mp4" in f.get("link", "").lower()
                    ]
                    
                    if not mp4_files:
                        logger.warning(f"⚠️ No MP4 files found for video ID {video_id}. Skipping.")
                        continue

                    # Sort by resolution/width to get the best quality
                    best_video = max(mp4_files, key=lambda x: x.get("width") or 0)
                    download_link = best_video.get("link")
                    if not download_link:
                        logger.warning(f"⚠️ No download link for video ID {video_id}. Skipping.")
                        continue

                    # Use a unique file path based on the Pexels video ID to prevent overwriting
                    file_path = f"videos/video_{video_id}.mp4"

                    # Download video file
                    logger.info(f"📥 Downloading video file: {download_link}")
                    try:
                        video_res = await client.get(download_link, follow_redirects=True, timeout=60.0)
                        video_res.raise_for_status()
                        
                        with open(file_path, "wb") as f:
                            f.write(video_res.content)
                        logger.info(f"💾 Saved video locally to: {file_path}")
                    except Exception as e:
                        logger.error(f"❌ Failed to download or save video {video_id}: {e}")
                        continue

                    # Prepare metadata tags and validation limits
                    tags = generate_tags(query, title)
                    thumbnail_url = video.get("image", "")

                    # Determine which URL to save in the database
                    db_url = download_link if db_url_mode == "online" else file_path

                    # Instantiate the Pydantic create schema
                    video_dto = VideoCreate(
                        title=title,
                        description=description,
                        url=db_url,
                        thumbnail_url=thumbnail_url,
                        tags=tags,
                        category=category,
                        intensity_level=intensity_level,
                        creator_id=creator_id,
                        view_count=0,
                        like_count=0,
                        comment_count=0,
                    )

                    # Save video using the Service Layer (generates embeddings and trending scores)
                    logger.info(f"📝 Registering video in MongoDB (URL saved: {db_url})...")
                    try:
                        saved_video = await video_service.create_video(video_dto)
                        logger.info(f"✅ Success! Saved to DB with ID: {saved_video.id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to save video metadata to DB: {e}")
                        # Clean up downloaded file on database save failure
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info("🗑️ Cleaned up downloaded video file due to DB failure.")
        finally:
            logger.info("🔌 Disconnecting MongoDB...")
            await disconnect_db()


def main():
    parser = argparse.ArgumentParser(
        description="Crawl and import Pexels videos into Gotouchgrass MongoDB."
    )
    parser.add_argument(
        "--query",
        type=str,
        default="all",
        help="Search query for Pexels videos. Use 'all' for preset topics, or comma-separated values (e.g. 'cooking,gaming') for batch crawling."
    )
    parser.add_argument(
        "--category",
        type=str,
        default="nature",
        help=f"Category field for the video model. Can be comma-separated for batch crawling (default: 'nature'). Choices: {', '.join(CATEGORY_ENUM)}"
    )
    parser.add_argument(
        "--intensity",
        type=str,
        default="low",
        help=f"Intensity level for the video. Can be comma-separated for batch crawling (default: 'low'). Choices: {', '.join(INTENSITY_ENUM)}"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of videos to fetch and save per topic (default: 10)"
    )
    parser.add_argument(
        "--creator-id",
        type=str,
        default="6a0bdf9bc0d0a93bff883daa",
        help="Creator ID to associate with the videos (default: 6a0bdf9bc0d0a93bff883daa)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("PEXELS_API_KEY", ""),
        help="Pexels API key (defaults to PEXELS_API_KEY from environment/.env)"
    )
    parser.add_argument(
        "--db-url-mode",
        type=str,
        choices=["online", "local"],
        default="online",
        help="Whether to save the online Pexels CDN link ('online') or the local path ('local') to the MongoDB database (default: 'online')"
    )

    args = parser.parse_args()

    # Generate tasks list
    tasks = []
    if args.query.lower() == "all":
        tasks = PRESET_TASKS
    elif "," in args.query or "," in args.category or "," in args.intensity:
        queries = [q.strip() for q in args.query.split(",")]
        categories = [c.strip() for c in args.category.split(",")]
        if len(categories) < len(queries):
            categories = categories + [categories[-1]] * (len(queries) - len(categories))
        intensities = [i.strip() for i in args.intensity.split(",")]
        if len(intensities) < len(queries):
            intensities = intensities + [intensities[-1]] * (len(queries) - len(intensities))
        for q, c, i in zip(queries, categories, intensities):
            tasks.append({"query": q, "category": c, "intensity_level": i})
    else:
        tasks = [{"query": args.query, "category": args.category, "intensity_level": args.intensity}]


    # Validate categories and intensities in tasks
    for task in tasks:
        if task["category"] not in CATEGORY_ENUM:
            logger.error(f"❌ Invalid category '{task['category']}'. Must be one of: {CATEGORY_ENUM}")
            sys.exit(1)
        if task["intensity_level"] not in INTENSITY_ENUM:
            logger.error(f"❌ Invalid intensity level '{task['intensity_level']}'. Must be one of: {INTENSITY_ENUM}")
            sys.exit(1)

    asyncio.run(
        crawl_pexels(
            tasks=tasks,
            limit=args.limit,
            creator_id=args.creator_id,
            api_key=args.api_key,
            db_url_mode=args.db_url_mode,
        )
    )


if __name__ == "__main__":
    main()

