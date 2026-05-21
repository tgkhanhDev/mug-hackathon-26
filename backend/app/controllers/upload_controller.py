"""
Upload controller — API to upload files to AWS S3.

Currently stubs the AWS upload functionality until AWS credentials are provided.
"""

import logging
import uuid
import os
import boto3
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.utils.s3 import upload_to_s3

router = APIRouter(prefix="/upload", tags=["Upload"])
logger = logging.getLogger(__name__)


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Upload a file to AWS S3",
    description="Uploads a file to AWS S3.",
)
async def upload_file(file: UploadFile = File(...)):
    """POST /api/v1/upload/ — Upload file to AWS S3."""
    try:
        file_url = await upload_to_s3(file)
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
            detail="Failed to upload file to AWS"
        )
