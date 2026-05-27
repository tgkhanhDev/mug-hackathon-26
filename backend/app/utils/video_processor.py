"""
Video processor utility — helper functions to extract metadata and thumbnails using ffmpeg/ffprobe.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def get_video_metadata(video_path: str) -> Dict[str, Any]:
    """
    Extracts metadata from a video file using ffprobe.
    Returns a dict with: duration (float), width (int), height (int)
    """
    metadata = {"duration": 0.0, "width": 0, "height": 0}

    if not os.path.exists(video_path):
        logger.warning(f"Video file not found at path: {video_path}")
        return metadata

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json",
        video_path
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.warning(f"ffprobe returned non-zero code {proc.returncode}: {stderr.decode().strip()}")
            return metadata

        data = json.loads(stdout.decode())

        # Parse duration
        duration_str = data.get("format", {}).get("duration")
        if duration_str:
            try:
                metadata["duration"] = float(duration_str)
            except ValueError:
                pass

        # Parse width/height from streams
        streams = data.get("streams", [])
        if streams:
            for stream in streams:
                width = stream.get("width")
                height = stream.get("height")
                if width is not None and height is not None:
                    try:
                        metadata["width"] = int(width)
                        metadata["height"] = int(height)
                        break
                    except ValueError:
                        pass

        logger.info(f"Extracted video metadata: {metadata}")

    except Exception as e:
        logger.error(f"Error executing ffprobe: {e}")

    return metadata


async def extract_thumbnail(video_path: str, output_thumb_path: str, seek_seconds: float = 1.0) -> bool:
    """
    Extracts a single frame from the video at seek_seconds and saves it as a JPEG using ffmpeg.
    """
    if not os.path.exists(video_path):
        logger.warning(f"Video file not found for thumbnail extraction: {video_path}")
        return False

    # Create parent directories if they don't exist
    parent_dir = os.path.dirname(os.path.abspath(output_thumb_path))
    os.makedirs(parent_dir, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(seek_seconds),
        "-i", video_path,
        "-vframes", "1",
        "-f", "image2",
        output_thumb_path
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and os.path.exists(output_thumb_path):
            logger.info(f"Successfully extracted thumbnail to {output_thumb_path}")
            return True
        else:
            logger.warning(f"ffmpeg thumbnail extraction failed. Return code: {proc.returncode}. Error: {stderr.decode().strip()}")
            return False
    except Exception as e:
        logger.error(f"Error executing ffmpeg: {e}")
        return False


async def create_hls_playlist(video_path: str, output_dir: str) -> bool:
    """
    Chunks a video file using ffmpeg to produce HLS fragmented MP4 (.m4s) segments.
    Uses copy mode first for fast processing, and falls back to transcoding to H.264/AAC if copying fails.
    """
    if not os.path.exists(video_path):
        logger.warning(f"Video file not found for HLS segmenting: {video_path}")
        return False

    os.makedirs(output_dir, exist_ok=True)

    cmd_copy = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-c", "copy",
        "-hls_time", "6",
        "-hls_playlist_type", "vod",
        "-hls_segment_type", "fmp4",
        "-hls_fmp4_init_filename", "init.mp4",
        "-hls_segment_filename", os.path.join(output_dir, "segment_%03d.m4s"),
        os.path.join(output_dir, "playlist.m3u8")
    ]

    logger.info("Attempting fast HLS segmenting using stream copy (-c copy)...")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_copy,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and os.path.exists(os.path.join(output_dir, "playlist.m3u8")):
            logger.info("Successfully created HLS playlist using stream copy mode.")
            return True
        else:
            logger.warning(f"Fast HLS copy failed (code {proc.returncode}). Falling back to transcoding mode...")
    except Exception as e:
        logger.error(f"Error executing ffmpeg stream copy: {e}")

    cmd_transcode = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-hls_time", "6",
        "-hls_playlist_type", "vod",
        "-hls_segment_type", "fmp4",
        "-hls_fmp4_init_filename", "init.mp4",
        "-hls_segment_filename", os.path.join(output_dir, "segment_%03d.m4s"),
        os.path.join(output_dir, "playlist.m3u8")
    ]

    logger.info("Transcoding video to H.264/AAC for HLS segmenting...")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_transcode,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and os.path.exists(os.path.join(output_dir, "playlist.m3u8")):
            logger.info("Successfully created HLS playlist using transcoding mode.")
            return True
        else:
            logger.error(f"Transcoding HLS failed (code {proc.returncode}). Error: {stderr.decode().strip()}")
            return False
    except Exception as e:
        logger.error(f"Error executing ffmpeg transcoding: {e}")
        return False
