"""
S3 utility — helper functions for AWS S3 upload.
"""

import logging
import uuid
import boto3
from fastapi import UploadFile, HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)


async def upload_to_s3(file: UploadFile) -> str:
    """
    Uploads a file to AWS S3 and returns the public URL.
    Falls back to a mock S3 URL if S3 upload fails or credentials are missing.

    Args:
        file (UploadFile): The file uploaded via FastAPI.

    Returns:
        str: The public URL of the uploaded file on S3.
    """
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    
    # Try S3 upload if credentials look configured
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        try:
            # Initialize boto3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )

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
            
            file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
            logger.info(f"Successfully uploaded file to S3: {file_url}")
            return file_url
            
        except Exception as e:
            logger.warning(f"⚠️ AWS S3 upload failed ({e}). Falling back to mock S3 URL for local development.")
    else:
        logger.warning("⚠️ AWS S3 credentials missing. Using mock S3 URL for local development.")

    # Generate a mock S3 URL
    bucket_name = settings.AWS_BUCKET_NAME or "bshowsell-public"
    region = settings.AWS_REGION or "ap-southeast-1"
    mock_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{unique_filename}"
    logger.info(f"Generated mock S3 URL: {mock_url}")
    return mock_url
