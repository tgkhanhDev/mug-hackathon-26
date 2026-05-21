"""
Video controller — API route handlers for video management.

Thin layer: validates request → calls service → returns response.
"""

from typing import Optional
from fastapi import APIRouter, Query, status, UploadFile, File, Form, Request

from app.models.video import VideoCreate, VideoResponse, VideoListResponse
from app.services.video_service import VideoService

router = APIRouter(prefix="/videos", tags=["Videos"])


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
    description="Automatically uploads the video file to S3, generates embedding vector, and calculates trending score.",
)
async def create_video(
    request: Request,
    title: str = Form(..., description="Tiêu đề video"),
    description: str = Form(..., description="Mô tả ngắn nội dung video"),
    tags: str = Form(..., description="Các tags phân loại nội dung, cách nhau bằng dấu phẩy"),
    category: str = Form(..., description="Nhóm lớn"),
    intensity_level: str = Form(..., description="Mức dopamine"),
    creator_id: str = Form(..., description="ID định danh creator (string slug)"),
    file: UploadFile = File(..., description="File video tải lên S3")
):
    """POST /api/v1/videos — Create a new video by uploading a file and providing metadata."""
    # 1. Upload video file to S3
    from app.utils.s3 import upload_to_s3
    file_url = await upload_to_s3(file)

    # 2. Parse tags list from comma-separated string
    tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    # 3. Read optional/hidden fields from form data
    form_data = await request.form()
    view_count = form_data.get("view_count")
    like_count = form_data.get("like_count")
    comment_count = form_data.get("comment_count")
    thumbnail_url = form_data.get("thumbnail_url")

    # 4. Construct VideoCreate schema
    data_dict = {
        "title": title,
        "description": description,
        "url": file_url,
        "tags": tags_list,
        "category": category,
        "intensity_level": intensity_level,
        "creator_id": creator_id,
    }

    # Ensure form values are strings or None before parsing
    view_str = str(view_count) if view_count is not None else None
    like_str = str(like_count) if like_count is not None else None
    comment_str = str(comment_count) if comment_count is not None else None
    thumb_str = str(thumbnail_url) if thumbnail_url is not None else None

    parsed_view = parse_optional_int(view_str)
    parsed_like = parse_optional_int(like_str)
    parsed_comment = parse_optional_int(comment_str)

    if parsed_view is not None:
        data_dict["view_count"] = parsed_view
    if parsed_like is not None:
        data_dict["like_count"] = parsed_like
    if parsed_comment is not None:
        data_dict["comment_count"] = parsed_comment
    if thumb_str is not None and thumb_str.strip() != "":
        data_dict["thumbnail_url"] = thumb_str

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
