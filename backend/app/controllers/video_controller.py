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
    description="Automatically processes the video file using ffmpeg to create HLS segments and uploads to local MinIO.",
)
async def create_video(
    request: Request,
    title: str = Form(..., description="Tiêu đề video"),
    description: str = Form(..., description="Mô tả ngắn nội dung video"),
    creator_id: str = Form(..., description="ID định danh creator (string slug)"),
    file: UploadFile = File(..., description="File video tải lên")
):
    """POST /api/v1/videos — Create a new video with HLS packaging."""
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "mp4"
    temp_video_path = ""
    temp_hls_dir = ""
    duration = None
    width = None
    height = None
    auto_thumbnail_url = ""
    file_url = ""
    video_folder_id = str(uuid.uuid4())

    try:
        # 1. Write file to temp path
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_video:
            temp_video_path = temp_video.name
            logger.info(f"Saving temporary upload video file to {temp_video_path}...")
            content = await file.read()
            temp_video.write(content)
            
        # 2. Extract metadata
        from app.utils.video_processor import get_video_metadata, extract_thumbnail, create_hls_playlist
        metadata = await get_video_metadata(temp_video_path)
        duration = metadata.get("duration")
        width = metadata.get("width")
        height = metadata.get("height")

        # Create HLS temp folder
        temp_hls_dir = tempfile.mkdtemp(prefix="hls_")

        # 3. Create HLS segment files (.m3u8, .m4s, init.mp4)
        hls_success = await create_hls_playlist(temp_video_path, temp_hls_dir)
        if not hls_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to segment video into HLS using ffmpeg."
            )

        # 4. Extract thumbnail if not provided
        form_data = await request.form()
        view_count = form_data.get("view_count")
        like_count = form_data.get("like_count")
        comment_count = form_data.get("comment_count")
        thumbnail_url = form_data.get("thumbnail_url")

        thumb_str = str(thumbnail_url) if thumbnail_url is not None else None
        if not thumb_str or thumb_str.strip() == "":
            thumb_filename = "thumbnail.jpg"
            temp_thumb_path = os.path.join(temp_hls_dir, thumb_filename)
            
            logger.info(f"Extracting frame for thumbnail to {temp_thumb_path}...")
            seek_pos = 1.0
            if duration and duration < 1.0:
                seek_pos = duration / 2.0
                
            thumb_success = await extract_thumbnail(temp_video_path, temp_thumb_path, seek_seconds=seek_pos)
            if thumb_success:
                auto_thumbnail_url = f"{settings.MINIO_ENDPOINT_URL}/{settings.MINIO_BUCKET_NAME}/videos/{video_folder_id}/{thumb_filename}"
                logger.info(f"Generated auto thumbnail URL: {auto_thumbnail_url}")

        # 5. Upload HLS directory to MinIO
        from app.utils.minio_client import upload_directory_to_minio
        file_url = await upload_directory_to_minio(temp_hls_dir, f"videos/{video_folder_id}")

    except Exception as e:
        logger.error(f"Error processing uploaded video: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing video: {str(e)}"
        )
    finally:
        # Clean up temporary video file
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
                logger.info(f"Removed temporary video file: {temp_video_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temp video file: {e}")

        # Clean up temporary HLS folder
        if temp_hls_dir and os.path.exists(temp_hls_dir):
            try:
                shutil.rmtree(temp_hls_dir)
                logger.info(f"Removed temporary HLS directory: {temp_hls_dir}")
            except Exception as e:
                logger.warning(f"Failed to remove temp HLS directory: {e}")

    # Construct VideoCreate schema
    data_dict = {
        "title": title,
        "description": description,
        "url": file_url,
        "thumbnail_url": thumb_str if (thumb_str and thumb_str.strip() != "") else (auto_thumbnail_url or ""),
        "tags": None,
        "category": None,
        "intensity_level": None,
        "creator_id": creator_id,
        "duration": duration,
        "width": width,
        "height": height
    }

    # Ensure form values are strings or None before parsing
    view_str = str(view_count) if view_count is not None else None
    like_str = str(like_count) if like_count is not None else None
    comment_str = str(comment_count) if comment_count is not None else None

    parsed_view = parse_optional_int(view_str)
    parsed_like = parse_optional_int(like_str)
    parsed_comment = parse_optional_int(comment_str)

    if parsed_view is not None:
        data_dict["view_count"] = parsed_view
    if parsed_like is not None:
        data_dict["like_count"] = parsed_like
    if parsed_comment is not None:
        data_dict["comment_count"] = parsed_comment

    data = VideoCreate(**data_dict)

    service = VideoService()
    return await service.create_video(data)


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
