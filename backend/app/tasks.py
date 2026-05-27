"""
Celery background tasks.
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime
from app.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.process_video_task")
def process_video_task(
    video_id: str,
    temp_video_path: str,
    video_folder_id: str,
    title: str,
    description: str,
    creator_id: str,
    view_count: int,
    like_count: int,
    comment_count: int
):
    """
    Background Celery task to process video:
    1. Extract duration, width, height using ffprobe.
    2. Package into HLS streams using ffmpeg.
    3. Extract thumbnail.
    4. Upload to MinIO.
    5. Predict category, tags, and intensity level.
    6. Generate text embedding.
    7. Calculate initial trending score.
    8. Update MongoDB.
    """
    logger.info(f"🚀 Starting background process_video_task for video {video_id}")
    
    try:
        return asyncio.run(
            _process_video_async(
                video_id=video_id,
                temp_video_path=temp_video_path,
                video_folder_id=video_folder_id,
                title=title,
                description=description,
                creator_id=creator_id,
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count
            )
        )
    except Exception as e:
        logger.error(f"❌ process_video_task failed for video {video_id}: {e}", exc_info=True)
        raise


async def _process_video_async(
    video_id: str,
    temp_video_path: str,
    video_folder_id: str,
    title: str,
    description: str,
    creator_id: str,
    view_count: int,
    like_count: int,
    comment_count: int
):
    import app.repositories.database as db
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.repositories.video_repository import VideoRepository
    from app.utils.video_processor import get_video_metadata, extract_thumbnail, create_hls_playlist
    from app.utils.minio_client import upload_directory_to_minio
    from app.utils.classifier import predict_all_metadata
    from app.utils.embedding import generate_embedding, build_embed_text
    import tempfile

    # Re-initialize Motor client inside this loop to avoid loop conflict
    db._client = AsyncIOMotorClient(settings.MONGODB_URI)
    db._database = db._client[settings.DATABASE_NAME]

    repo = VideoRepository()

    # Idempotency check
    video_doc = await repo.find_by_id(video_id)
    if video_doc and video_doc.get("status") == "completed":
        logger.info(f"⏭️ Video {video_id} already completed. Skipping processing task to prevent duplicate execution.")
        return

    temp_hls_dir = None
    file_url = ""
    auto_thumbnail_url = ""
    duration = None
    width = None
    height = None

    try:
        # 1. Extract metadata using ffprobe
        metadata = await get_video_metadata(temp_video_path)
        duration = metadata.get("duration")
        width = metadata.get("width")
        height = metadata.get("height")

        # 2. Package into HLS streams using ffmpeg
        temp_hls_dir = tempfile.mkdtemp(prefix="hls_")
        hls_success = await create_hls_playlist(temp_video_path, temp_hls_dir)
        if not hls_success:
            raise Exception("Failed to segment video into HLS using ffmpeg.")

        # 3. Extract thumbnail
        thumb_filename = "thumbnail.jpg"
        temp_thumb_path = os.path.join(temp_hls_dir, thumb_filename)
        seek_pos = 1.0
        if duration and duration < 1.0:
            seek_pos = duration / 2.0
        
        thumb_success = await extract_thumbnail(temp_video_path, temp_thumb_path, seek_seconds=seek_pos)
        if thumb_success:
            auto_thumbnail_url = f"{settings.MINIO_ENDPOINT_URL}/{settings.MINIO_BUCKET_NAME}/videos/{video_folder_id}/{thumb_filename}"
            logger.info(f"Successfully generated thumbnail: {auto_thumbnail_url}")

        # 4. Upload directory to MinIO
        file_url = await upload_directory_to_minio(temp_hls_dir, f"videos/{video_folder_id}")

        # 5. Predict metadata if missing
        pred_category, pred_tags, pred_intensity = await predict_all_metadata(
            description=description,
            title=title
        )

        # 6. Generate embedding
        embed_text = build_embed_text(
            title=title,
            description=description,
            category=pred_category,
            tags=pred_tags,
        )
        embedding = await generate_embedding(embed_text)

        # 7. Calculate initial trending score
        trending_score = (
            view_count * 1
            + like_count * 3
            + comment_count * 5
        )

        # 8. Update video record in MongoDB
        repo = VideoRepository()
        update_data = {
            "url": file_url,
            "thumbnail_url": auto_thumbnail_url,
            "category": pred_category,
            "tags": pred_tags,
            "intensity_level": pred_intensity,
            "embedding": embedding,
            "duration": duration,
            "width": width,
            "height": height,
            "trending_score": trending_score,
            "status": "completed",
            "updated_at": datetime.utcnow()
        }

        success = await repo.update_one(video_id, update_data)
        if not success:
            raise Exception(f"Failed to update MongoDB video record: {video_id}")
        logger.info(f"✅ Video {video_id} processed successfully.")

    except Exception as e:
        logger.error(f"❌ Error inside async process_video: {e}", exc_info=True)
        # Update video status to failed
        try:
            repo = VideoRepository()
            await repo.update_one(video_id, {
                "status": "failed",
                "updated_at": datetime.utcnow()
            })
        except Exception as db_err:
            logger.error(f"Failed to set status to failed: {db_err}")
        raise e

    finally:
        # Clean up temporary raw video file
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
                logger.info(f"Removed temporary video file: {temp_video_path}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to remove temp video: {cleanup_err}")
        
        # Clean up temporary HLS folder
        if temp_hls_dir and os.path.exists(temp_hls_dir):
            try:
                shutil.rmtree(temp_hls_dir)
                logger.info(f"Removed temporary HLS folder: {temp_hls_dir}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to remove temp HLS folder: {cleanup_err}")

        # Close client connections
        db._client.close()
        db._client = None
        db._database = None
