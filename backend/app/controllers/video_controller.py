"""
Video controller — API route handlers for video management.

Thin layer: validates request → calls service → returns response.
"""

import logging
import os
import shutil
import tempfile
import uuid
from typing import Optional
from fastapi import APIRouter, Query, status, UploadFile, File, Form, Request, HTTPException
from app.config import settings

from app.models.video import VideoCreate, VideoResponse, VideoListResponse
from app.services.video_service import VideoService

router = APIRouter(prefix="/videos", tags=["Videos"])
logger = logging.getLogger(__name__)


def parse_optional_int(val: Optional[str]) -> Optional[int]:
    if val is None or val.strip() == "":
        return None
    try:
        return int(val)
    except ValueError:
        return None


@router.post(
    "",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new video",
    description="Asynchronously processes the video file using ffmpeg HLS chunking and AI metadata extraction.",
)
async def create_video(
    request: Request,
    title: str = Form(..., description="Tiêu đề video"),
    description: str = Form(..., description="Mô tả ngắn nội dung video"),
    creator_id: str = Form(..., description="ID định danh creator (string slug)"),
    file: UploadFile = File(..., description="File video tải lên")
):
    """POST /api/v1/videos — Create a new video asynchronously."""
    # Read optional/hidden fields from form data
    form_data = await request.form()
    view_count = form_data.get("view_count")
    like_count = form_data.get("like_count")
    comment_count = form_data.get("comment_count")

    view_str = str(view_count) if view_count is not None else None
    like_str = str(like_count) if like_count is not None else None
    comment_str = str(comment_count) if comment_count is not None else None

    parsed_view = parse_optional_int(view_str) or 0
    parsed_like = parse_optional_int(like_str) or 0
    parsed_comment = parse_optional_int(comment_str) or 0

    # Generate folder ID and set up shared temp video location
    video_folder_id = str(uuid.uuid4())
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "mp4"
    
    os.makedirs("/tmp/uploads", exist_ok=True)
    temp_video_path = f"/tmp/uploads/{video_folder_id}.{file_ext}"

    try:
        # Write uploaded file to persistent temp path for Celery to read
        with open(temp_video_path, "wb") as f:
            logger.info(f"Saving uploaded video file for async queue to {temp_video_path}...")
            content = await file.read()
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to write uploaded file to temp path: {e}")
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to receive file: {str(e)}"
        )

    # Construct VideoCreate schema
    data = VideoCreate(
        title=title,
        description=description,
        url="",  # Celery will fill this once HLS chunking is done
        thumbnail_url="",  # Celery will fill this
        creator_id=creator_id,
        view_count=parsed_view,
        like_count=parsed_like,
        comment_count=parsed_comment,
    )

    service = VideoService()
    created_video = await service.create_video_async(data)

    # Trigger background processing task
    from app.tasks import process_video_task
    import kombu.exceptions
    from datetime import datetime

    try:
        process_video_task.delay(
            video_id=created_video.id,
            temp_video_path=temp_video_path,
            video_folder_id=video_folder_id,
            title=title,
            description=description,
            creator_id=creator_id,
            view_count=parsed_view,
            like_count=parsed_like,
            comment_count=parsed_comment
        )
    except (kombu.exceptions.OperationalError, Exception) as e:
        logger.error(f"❌ Failed to enqueue video processing task to broker: {e}")
        # 1. Update video status in DB to failed_queue
        try:
            await service._repo.update_one(created_video.id, {
                "status": "failed_queue",
                "updated_at": datetime.utcnow()
            })
        except Exception as db_err:
            logger.error(f"Failed to update video status in DB: {db_err}")

        # 2. Clean up temporary video file
        if os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
                logger.info(f"Cleaned up temp video file after queue failure: {temp_video_path}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to remove temp video: {cleanup_err}")

        # 3. Raise 503 Service Unavailable
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Video processing service queue is currently unavailable. Please try again later."
        )

    return created_video


@router.get(
    "",
    response_model=VideoListResponse,
    summary="List videos",
    description="Get a paginated list of all videos, ordered by creation date (newest first).",
)
async def list_videos(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
):
    """GET /api/v1/videos — List videos with pagination."""
    service = VideoService()
    return await service.get_videos(skip=skip, limit=limit)


@router.get(
    "/trending",
    response_model=list[VideoResponse],
    summary="Get trending videos",
    description="Get top videos sorted by trending_score (view*1 + like*3 + comment*5).",
)
async def get_trending(
    limit: int = Query(default=10, ge=1, le=50, description="Number of trending videos"),
):
    """GET /api/v1/videos/trending — Get trending videos."""
    service = VideoService()
    return await service.get_trending_videos(limit=limit)


@router.post(
    "/train",
    status_code=status.HTTP_200_OK,
    summary="Train video classifier model",
    description="Fetches all video data from MongoDB and trains classification models for categories and tags.",
)
async def train_classifier_endpoint():
    """POST /api/v1/videos/train — Train classifier model."""
    service = VideoService()
    return await service.train_classification_model()


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get video by ID",
    description="Retrieve a single video by its MongoDB ObjectId.",
)
async def get_video(video_id: str):
    """GET /api/v1/videos/{video_id} — Get a single video."""
    service = VideoService()
    return await service.get_video_by_id(video_id)
