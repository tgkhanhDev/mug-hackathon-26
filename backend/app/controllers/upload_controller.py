"""
Upload controller — API to upload files to local MinIO.
"""

import logging
import uuid
import os
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.utils.minio_client import upload_to_minio

router = APIRouter(prefix="/upload", tags=["Upload"])
logger = logging.getLogger(__name__)


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Upload a file to MinIO",
    description="Uploads a file to local MinIO storage.",
)
async def upload_file(file: UploadFile = File(...)):
    """POST /api/v1/upload/ — Upload file to local MinIO."""
    try:
        file_url = await upload_to_minio(file)
        unique_filename = file_url.split("/")[-1]
        
        return {
            "message": "File uploaded successfully",
            "file_url": file_url,
            "filename": unique_filename,
            "original_filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to MinIO"
        )
