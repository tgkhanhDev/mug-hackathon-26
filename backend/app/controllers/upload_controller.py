"""
Upload controller — API to upload files to AWS S3.

Currently stubs the AWS upload functionality until AWS credentials are provided.
"""

import logging
import uuid
import os
import boto3
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.config import settings

router = APIRouter(prefix="/upload", tags=["Upload"])
logger = logging.getLogger(__name__)


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Upload a file to AWS S3",
    description="Uploads a file to AWS S3. Currently mocked until AWS credentials are provided in .env.",
)
async def upload_file(file: UploadFile = File(...)):
    """POST /api/v1/upload/ — Upload file to AWS."""
    try:
        # Initialize boto3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )

        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # Read file content
        file_content = await file.read()
        
        logger.info(f"Uploading file {unique_filename} to AWS S3 bucket {settings.AWS_BUCKET_NAME}...")
        
        # Actual upload logic
        s3_client.put_object(
            Bucket=settings.AWS_BUCKET_NAME,
            Key=unique_filename,
            Body=file_content,
            ContentType=file.content_type
        )
        
        # Real URL
        file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
        
        return {
            "message": "File uploaded successfully",
            "file_url": file_url,
            "filename": unique_filename,
            "original_filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to AWS"
        )
