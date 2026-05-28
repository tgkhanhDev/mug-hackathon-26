"""
MinIO client utility — helper functions for local dedicated MinIO upload.
"""

import logging
import uuid
import boto3
import json
import os
from typing import Optional
from fastapi import UploadFile
from app.config import settings

logger = logging.getLogger(__name__)

# Cache bucket verification status to avoid checking on every request
_bucket_verified = False


def get_minio_client():
    """
    Initializes and returns a boto3 client configured specifically for local MinIO.
    Ensures the target bucket exists and has public read access policy.
    """
    global _bucket_verified

    client_kwargs = {
        "aws_access_key_id": settings.MINIO_ACCESS_KEY,
        "aws_secret_access_key": settings.MINIO_SECRET_KEY,
        "region_name": settings.MINIO_REGION,
        "endpoint_url": settings.MINIO_ENDPOINT_URL,
        "use_ssl": settings.MINIO_USE_SSL,
    }

    # Path-style addressing is required for MinIO
    from botocore.client import Config
    client_kwargs["config"] = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"}
    )

    minio_client = boto3.client("s3", **client_kwargs)

    # Automatically ensure bucket exists and set public read policy
    if not _bucket_verified and settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY:
        try:
            bucket_name = settings.MINIO_BUCKET_NAME or "gotouchgrass-media"
            
            # Check if bucket exists
            try:
                minio_client.head_bucket(Bucket=bucket_name)
                logger.info(f"MinIO Bucket '{bucket_name}' already exists.")
            except Exception:
                logger.info(f"MinIO Bucket '{bucket_name}' does not exist. Creating it...")
                minio_client.create_bucket(Bucket=bucket_name)

                # Set policy to public read-only (GetObject)
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                        }
                    ]
                }
                minio_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
                logger.info(f"MinIO Bucket '{bucket_name}' created and set to public read-only policy.")

            _bucket_verified = True
        except Exception as e:
            logger.warning(f"⚠️ Failed to verify or create MinIO bucket: {e}")

    return minio_client


async def upload_to_minio(file: UploadFile) -> str:
    """
    Uploads an UploadFile to MinIO and returns the public URL.
    """
    file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    try:
        client = get_minio_client()
        file_content = await file.read()
        
        # Reset seek position just in case
        await file.seek(0)

        bucket_name = settings.MINIO_BUCKET_NAME or "gotouchgrass-media"
        logger.info(f"Uploading file {unique_filename} to MinIO bucket {bucket_name}...")

        client.put_object(
            Bucket=bucket_name,
            Key=unique_filename,
            Body=file_content,
            ContentType=file.content_type
        )

        file_url = f"{settings.MINIO_ENDPOINT_URL}/{bucket_name}/{unique_filename}"
        logger.info(f"Successfully uploaded file to MinIO: {file_url}")
        return file_url

    except Exception as e:
        logger.error(f"❌ MinIO upload failed ({e}). Returning fallback URL.")
        bucket_name = settings.MINIO_BUCKET_NAME or "gotouchgrass-media"
        return f"{settings.MINIO_ENDPOINT_URL}/{bucket_name}/{unique_filename}"


async def upload_file_from_path(file_path: str, content_type: str, custom_filename: Optional[str] = None) -> str:
    """
    Uploads a local file from disk to MinIO and returns the public URL.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Local file not found: {file_path}")

    filename = custom_filename or os.path.basename(file_path)
    file_extension = filename.split(".")[-1] if "." in filename else ""
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    try:
        client = get_minio_client()
        bucket_name = settings.MINIO_BUCKET_NAME or "gotouchgrass-media"
        logger.info(f"Uploading file {unique_filename} from path {file_path} to MinIO bucket {bucket_name}...")

        with open(file_path, "rb") as f:
            client.put_object(
                Bucket=bucket_name,
                Key=unique_filename,
                Body=f,
                ContentType=content_type
            )

        file_url = f"{settings.MINIO_ENDPOINT_URL}/{bucket_name}/{unique_filename}"
        logger.info(f"Successfully uploaded file from path to MinIO: {file_url}")
        return file_url

    except Exception as e:
        logger.error(f"❌ MinIO upload from path failed ({e}). Returning fallback URL.")
        bucket_name = settings.MINIO_BUCKET_NAME or "gotouchgrass-media"
        return f"{settings.MINIO_ENDPOINT_URL}/{bucket_name}/{unique_filename}"


async def upload_directory_to_minio(local_dir: str, minio_prefix: str) -> str:
    """
    Uploads all files inside a local directory to MinIO under the specified prefix.
    Preserves original filenames to maintain HLS segment linking.
    Returns the public URL of the 'playlist.m3u8' file.
    """
    if not os.path.isdir(local_dir):
        raise ValueError(f"Not a valid directory: {local_dir}")

    client = get_minio_client()
    bucket_name = settings.MINIO_BUCKET_NAME or "gotouchgrass-media"
    logger.info(f"Uploading HLS directory {local_dir} to MinIO bucket {bucket_name} with prefix {minio_prefix}...")

    playlist_url = ""

    for root, _, files in os.walk(local_dir):
        for file in files:
            local_file_path = os.path.join(root, file)
            rel_path = os.path.relpath(local_file_path, local_dir)
            minio_key = f"{minio_prefix}/{rel_path}".replace("\\", "/")

            # Determine content type based on extension
            ext = file.split(".")[-1].lower() if "." in file else ""
            if ext == "m3u8":
                content_type = "application/x-mpegURL"
            elif ext == "m4s":
                content_type = "video/iso.segment"
            elif ext == "mp4":
                content_type = "video/mp4"
            elif ext in ["jpg", "jpeg"]:
                content_type = "image/jpeg"
            else:
                content_type = "application/octet-stream"

            logger.info(f"Uploading file {rel_path} as {minio_key} ({content_type})...")

            with open(local_file_path, "rb") as f:
                client.put_object(
                    Bucket=bucket_name,
                    Key=minio_key,
                    Body=f,
                    ContentType=content_type
                )

            if file == "playlist.m3u8":
                playlist_url = f"{settings.MINIO_ENDPOINT_URL}/{bucket_name}/{minio_key}"

    logger.info(f"Successfully uploaded HLS directory. Playlist URL: {playlist_url}")
    return playlist_url
