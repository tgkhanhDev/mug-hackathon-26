#!/usr/bin/env python3
"""
Orchestrator Script: setup_and_run.py
Runs pre-flight diagnostics, auto-installs missing Python packages & CLI tools,
spins up local Docker services, runs Pexels crawl with HLS chunking (high quality),
inserts them into local MongoDB, and boots the FastAPI server.
"""

import os
import sys
import shutil
import subprocess
import socket
import argparse
import time
import logging
from typing import List, Dict

# Set up logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("setup_and_run")

def check_python_dependencies():
    """Verify and install missing Python packages from requirements.txt."""
    logger.info("🔍 Checking Python package dependencies...")
    req_file = "requirements.txt"
    if not os.path.exists(req_file):
        logger.warning(f"⚠️ {req_file} not found. Skipping pip dependencies check.")
        return

    # Check if pip is available
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError:
        logger.error("❌ pip is not available in the current Python environment.")
        sys.exit(1)

    logger.info(f"📦 Installing/verifying packages from {req_file}...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], check=True)
        logger.info("✅ Python dependencies verified and up-to-date.")
    except Exception as e:
        logger.error(f"❌ Failed to install Python dependencies: {e}")
        sys.exit(1)

def check_system_tools():
    """Verify ffmpeg, ffprobe, docker, and docker compose. Try auto-install for ffmpeg/ffprobe."""
    logger.info("🔍 Checking system tools (ffmpeg, ffprobe, docker)...")

    # 1. ffmpeg & ffprobe check
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")

    if not ffmpeg_path or not ffprobe_path:
        logger.warning("⚠️ ffmpeg or ffprobe is missing.")
        # Try auto-install on Debian/Ubuntu systems
        if shutil.which("apt-get"):
            logger.info("🛠️ Debian/Ubuntu detected. Attempting to install ffmpeg/ffprobe...")
            try:
                # Try non-interactive sudo install
                result = subprocess.run(["sudo", "-n", "apt-get", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if result.returncode == 0:
                    subprocess.run(["sudo", "-n", "apt-get", "install", "-y", "ffmpeg"], check=True)
                    logger.info("✅ Successfully installed ffmpeg/ffprobe using apt-get.")
                else:
                    raise subprocess.CalledProcessError(1, "apt-get update with sudo -n failed")
            except Exception:
                logger.error(
                    "❌ Could not install ffmpeg automatically. Please run manually:\n"
                    "   sudo apt-get update && sudo apt-get install -y ffmpeg"
                )
                sys.exit(1)
        else:
            logger.error("❌ ffmpeg/ffprobe not found in PATH, and package manager apt-get is not available. Please install ffmpeg manually.")
            sys.exit(1)
    else:
        logger.info(f"✅ ffmpeg found at {ffmpeg_path}")
        logger.info(f"✅ ffprobe found at {ffprobe_path}")

    # 2. Docker check
    docker_path = shutil.which("docker")
    if not docker_path:
        logger.error("❌ Docker is not installed. Please install Docker before running.")
        sys.exit(1)
    else:
        logger.info(f"✅ Docker found at {docker_path}")

    # 3. Docker Compose plugin or CLI check
    docker_compose_cmd = None
    try:
        res = subprocess.run(["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            docker_compose_cmd = ["docker", "compose"]
    except Exception:
        pass

    if not docker_compose_cmd:
        if shutil.which("docker-compose"):
            docker_compose_cmd = ["docker-compose"]
        else:
            logger.error("❌ Docker Compose (V2 plugin 'docker compose' or V1 'docker-compose') not found. Please install it.")
            sys.exit(1)

    logger.info(f"✅ Docker Compose command: {' '.join(docker_compose_cmd)}")

    # 4. Check Docker Daemon Running
    try:
        subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        logger.info("✅ Docker daemon is running and accessible.")
    except subprocess.CalledProcessError:
        logger.error("❌ Docker daemon is not running. Please start Docker service (e.g. sudo systemctl start docker).")
        sys.exit(1)

    return docker_compose_cmd

def check_docker_images():
    """Check if required Docker images are present locally; warn if they need to be pulled."""
    images = [
        "mongodb/mongodb-atlas-local:latest",
        "mongo-express:latest",
        "quay.io/minio/minio:latest",
        "rabbitmq:3-management",
        "redis:alpine"
    ]
    logger.info("🔍 Checking required Docker images...")
    for img in images:
        try:
            # Run docker image inspect
            subprocess.run(["docker", "image", "inspect", img], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            logger.info(f"✓ Image '{img}' is available locally.")
        except subprocess.CalledProcessError:
            if "mongodb-atlas-local" in img:
                logger.warning(
                    f"⚠️ Image '{img}' is NOT available locally. "
                    f"Docker Compose will pull it on startup (size ~1.5GB, this might take a few minutes depending on your network)..."
                )
            else:
                logger.info(f"ℹ_ Image '{img}' is NOT available locally. Compose will pull it on startup.")

def check_port_conflicts():
    """Verify required ports are not occupied by host services, unless occupied by docker containers from this project."""
    logger.info("🔍 Checking port conflicts...")
    ports = {
        27017: "MongoDB",
        6379: "Redis",
        9000: "MinIO API",
        9001: "MinIO Console",
        5672: "RabbitMQ",
        8081: "Mongo Express UI",
        8033: "FastAPI server"
    }

    conflicts = []
    for port, name in ports.items():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
        except socket.error:
            # Check if this port is occupied by docker container from our compose
            try:
                out = subprocess.check_output(["docker", "ps", "--format", "{{.Ports}}"]).decode()
                # Check if port is mapped in docker ps
                if f":{port}->" in out:
                    # It's mapped by a docker container, which might be ours. We warn but don't fail immediately.
                    logger.debug(f"Port {port} ({name}) is in use by a Docker container. Assuming it could be our service.")
                else:
                    conflicts.append((port, name))
            except Exception:
                conflicts.append((port, name))

    if conflicts:
        for port, name in conflicts:
            logger.warning(f"⚠️ Port {port} ({name}) is already occupied by a non-docker process or external service!")
        logger.info("ℹ️ If you already have local MongoDB, Redis, or MinIO running, please stop them to avoid conflict, or check if the container services launch successfully.")

def update_env_file():
    """Back up .env and update connection strings to local services."""
    logger.info("📝 Verifying environment configuration in .env...")
    env_file = ".env"
    bak_file = ".env.bak"

    if not os.path.exists(env_file):
        logger.warning(f"⚠️ {env_file} does not exist. Creating default from template...")
        with open(env_file, "w") as f:
            f.write("# Generated local configuration\nPEXELS_API_KEY=\n")

    # Read current env contents
    with open(env_file, "r") as f:
        lines = f.readlines()

    # Backup env
    shutil.copyfile(env_file, bak_file)
    logger.info(f"💾 Backed up existing .env to {bak_file}")

    updated_lines = []
    mongodb_updated = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("MONGODB_URI="):
            updated_lines.append("MONGODB_URI=mongodb://localhost:27017/gotouchgrass?directConnection=true\n")
            mongodb_updated = True
        else:
            updated_lines.append(line)

    if not mongodb_updated:
        updated_lines.append("MONGODB_URI=mongodb://localhost:27017/gotouchgrass?directConnection=true\n")
        updated_lines.append("DATABASE_NAME=gotouchgrass\n")

    # Make sure default local minio/redis values are set if not present
    env_keys = {line.split("=")[0].strip() for line in updated_lines if "=" in line and not line.strip().startswith("#")}
    defaults = {
        "REDIS_URL": "redis://localhost:6379/0",
        "CELERY_BROKER_URL": "amqp://guest:guest@localhost:5672//",
        "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
        "MINIO_ENDPOINT_URL": "http://localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin",
        "MINIO_BUCKET_NAME": "gotouchgrass-media",
        "MINIO_USE_SSL": "False",
        "PORT": "8033"
    }

    for key, val in defaults.items():
        if key not in env_keys:
            updated_lines.append(f"{key}={val}\n")

    with open(env_file, "w") as f:
        f.writelines(updated_lines)

    logger.info("✅ .env file successfully configured to point to local services.")

def check_existing_services():
    """Verify if MongoDB or Redis are already running on the host."""
    mongo_running = False
    redis_running = False

    # Check MongoDB
    try:
        import pymongo
        client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
        mongo_running = True
        logger.info("ℹ️ Detected MongoDB already running on port 27017 natively. Will reuse it instead of starting a container.")
    except Exception:
        pass

    # Check Redis
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_timeout=1)
        r.ping()
        redis_running = True
        logger.info("ℹ️ Detected Redis already running on port 6379 natively. Will reuse it instead of starting a container.")
    except Exception:
        pass

    return mongo_running, redis_running

def start_docker_services(docker_compose_cmd: List[str], skip_mongo: bool, skip_redis: bool):
    """Run docker compose up -d for services that are not already running on the host."""
    services = ["minio", "rabbitmq", "mongo-express"]
    if not skip_mongo:
        services.append("mongodb")
    if not skip_redis:
        services.append("redis")

    logger.info(f"🚀 Starting local Docker services ({', '.join(services)})...")
    try:
        import os
        env = os.environ.copy()
        if skip_mongo:
            env["ME_CONFIG_MONGODB_SERVER"] = "host.docker.internal"
            logger.info("ℹ️ Configuring Mongo Express to connect to host's native MongoDB at 'host.docker.internal'")
        else:
            env["ME_CONFIG_MONGODB_SERVER"] = "mongodb"
            logger.info("ℹ️ Configuring Mongo Express to connect to container MongoDB at 'mongodb'")
            
        subprocess.run(docker_compose_cmd + ["up", "-d"] + services, env=env, check=True)
        logger.info("✅ Docker Compose command successfully executed.")
    except Exception as e:
        logger.error(f"❌ Failed to run Docker Compose: {e}")
        sys.exit(1)

def run_health_checks():
    """Wait for MongoDB, Redis, and MinIO to accept connections."""
    logger.info("🔌 Waiting for local services to be healthy...")
    
    # Reload environment to load updated MONGODB_URI
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    from app.config import settings
    import pymongo
    import redis
    import urllib.request

    # 1. MongoDB Healthcheck
    logger.info("⏳ Checking MongoDB connection...")
    mongo_success = False
    for attempt in range(15):
        try:
            client = pymongo.MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            logger.info("✅ MongoDB is UP and healthy.")
            mongo_success = True
            break
        except Exception as e:
            logger.info(f"MongoDB not ready yet (attempt {attempt + 1}/15)...")
            time.sleep(2)
    if not mongo_success:
        logger.error("❌ MongoDB healthcheck failed. Check container logs: docker logs gotouchgrass-mongodb")
        sys.exit(1)

    # 2. Redis Healthcheck
    logger.info("⏳ Checking Redis connection...")
    redis_success = False
    for attempt in range(15):
        try:
            r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            logger.info("✅ Redis is UP and healthy.")
            redis_success = True
            break
        except Exception as e:
            logger.info(f"Redis not ready yet (attempt {attempt + 1}/15)...")
            time.sleep(2)
    if not redis_success:
        logger.error("❌ Redis healthcheck failed. Check container logs: docker logs gotouchgrass-redis")
        sys.exit(1)

    # 3. MinIO Healthcheck
    logger.info("⏳ Checking MinIO Connection...")
    minio_success = False
    health_url = f"{settings.MINIO_ENDPOINT_URL}/minio/health/live"
    for attempt in range(15):
        try:
            req = urllib.request.Request(health_url)
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    logger.info("✅ MinIO is UP and healthy.")
                    minio_success = True
                    break
        except Exception:
            logger.info(f"MinIO not ready yet (attempt {attempt + 1}/15)...")
            time.sleep(2)
    if not minio_success:
        logger.error("❌ MinIO healthcheck failed. Check container logs: docker logs gotouchgrass-minio")
        sys.exit(1)

    # 4. Mongo Express Healthcheck
    logger.info("⏳ Checking Mongo Express connection...")
    express_success = False
    for attempt in range(15):
        try:
            req = urllib.request.Request("http://localhost:8081")
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    logger.info("✅ Mongo Express is UP and healthy.")
                    express_success = True
                    break
        except Exception:
            logger.info(f"Mongo Express not ready yet (attempt {attempt + 1}/15)...")
            time.sleep(2)
    if not express_success:
        logger.warning("⚠️ Mongo Express healthcheck failed/timed out, but continuing...")

    logger.info("🎉 All local container services are fully UP and healthy!")

async def process_pexels_video_hls(
    video_data: dict,
    query: str,
    category: str,
    intensity_level: str,
    creator_id: str,
    client,
    video_service
) -> bool:
    """Download best quality video raw file, create placeholder in DB and delegate to Celery worker."""
    import uuid
    from app.config import settings
    from app.models.video import VideoCreate
    
    video_id = video_data.get("id")
    video_url_page = video_data.get("url", "")
    photographer = video_data.get("user", {}).get("name", "Unknown Photographer")

    # Extract title
    try:
        path_parts = video_url_page.rstrip("/").split("/")
        slug = path_parts[-1] if path_parts else ""
        words = slug.split("-")
        if words and words[-1].isdigit():
            words = words[:-1]
        title = " ".join(words).capitalize() if words else f"{query} video"
    except Exception:
        title = f"{query.capitalize()} video by {photographer}"

    title = title[:2000]
    description = f"High-quality {query} video shot by {photographer} on Pexels."
    description = description[:500]

    # Find the best quality MP4 file (largest width)
    video_files = video_data.get("video_files", [])
    if not video_files:
        logger.warning(f"⚠️ No video files for video ID {video_id}.")
        return False

    mp4_files = [f for f in video_files if f.get("file_type") == "video/mp4" or "mp4" in f.get("link", "").lower()]
    if not mp4_files:
        mp4_files = video_files

    # Select the video with maximum width (best quality)
    best_video = max(mp4_files, key=lambda x: x.get("width") or 0)
    download_link = best_video.get("link")
    if not download_link:
        logger.warning(f"⚠️ No download link for video ID {video_id}.")
        return False

    # Check if duplicate exists in DB
    try:
        existing = await video_service._repo.find_one({
            "$or": [
                {"title": description},
                {"description": title}
            ]
        })
        if existing:
            logger.info(f"⏭️ Video '{title}' already exists in database. Skipping.")
            return True
    except Exception as e:
        logger.warning(f"⚠️ Failed to query DB for duplicates: {e}")

    # Define a clean temporary folder structures in /tmp/uploads
    os.makedirs("/tmp/uploads", exist_ok=True)
    video_folder_id = str(uuid.uuid4())
    raw_video_path = f"/tmp/uploads/{video_folder_id}.mp4"

    logger.info(f"⬇️ Downloading best quality video {video_id} ({best_video.get('width')}x{best_video.get('height')})...")
    
    try:
        # Download file using httpx client
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with client.stream("GET", download_link, headers=headers, follow_redirects=True, timeout=120.0) as response:
            if response.status_code != 200:
                logger.error(f"❌ Failed to download raw video: HTTP {response.status_code}")
                return False
            with open(raw_video_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

        # Verify download succeeded
        if not os.path.exists(raw_video_path) or os.path.getsize(raw_video_path) == 0:
            logger.error("❌ Downloaded video file is empty or missing.")
            return False

        logger.info(f"✓ Video downloaded successfully ({os.path.getsize(raw_video_path) // 1024} KB). Enqueueing to Celery task queue...")

        # Construct VideoCreate schema (for placeholder)
        video_dto = VideoCreate(
            title=description,  # swapped for DB schema compatibility
            description=title,   # swapped for DB schema compatibility
            url="",
            thumbnail_url="",
            creator_id=creator_id,
            view_count=0,
            like_count=0,
            comment_count=0,
        )

        # Save video document in database (creates placeholder with status 'processing')
        saved_video = await video_service.create_video_async(video_dto)
        
        # Trigger Celery background task
        from app.tasks import process_video_task
        
        process_video_task.delay(
            video_id=str(saved_video.id),
            temp_video_path=raw_video_path,
            video_folder_id=video_folder_id,
            title=description,
            description=title,
            creator_id=creator_id,
            view_count=0,
            like_count=0,
            comment_count=0
        )
        
        logger.info(f"✅ Queued to Celery! Video '{title}' registered with ID: {saved_video.id} (status: processing)")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to download/queue video {video_id}: {e}", exc_info=True)
        # Cleanup file if something failed before task was queued
        if os.path.exists(raw_video_path):
            try:
                os.remove(raw_video_path)
            except Exception:
                pass
        return False

async def run_crawlers(limit: int, query_override: str):
    """Orchestrate crawling task list against Pexels API."""
    from dotenv import load_dotenv
    load_dotenv(override=True)

    from app.config import settings
    from app.repositories.database import connect_db, disconnect_db
    from app.services.video_service import VideoService
    import httpx

    api_key = settings.PEXELS_API_KEY
    if not api_key:
        logger.error("❌ PEXELS_API_KEY is not defined in .env! Cannot run crawler.")
        sys.exit(1)

    # Resolve queries list
    from crawl_pexels import PRESET_TASKS
    tasks = PRESET_TASKS
    if query_override and query_override != "all":
        queries = [q.strip() for q in query_override.split(",")]
        tasks = [t for t in PRESET_TASKS if t["query"] in queries]
        if not tasks:
            # Fallback to custom manual task if not in preset
            tasks = [{"query": q, "category": "nature", "intensity_level": "low"} for q in queries]

    logger.info(f"🕸️ Starting Pexels crawler. Limit per category: {limit} videos.")
    logger.info("🔌 Connecting to MongoDB...")
    await connect_db()
    video_service = VideoService()

    creator_id = "6a0bdf9bc0d0a93bff883daa"

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": api_key}
        for task in tasks:
            query = task["query"]
            category = task["category"]
            intensity = task["intensity_level"]

            logger.info("=" * 60)
            logger.info(f"🕷️ Crawling Category: '{category}' (Query: '{query}')")
            logger.info("=" * 60)

            url = f"https://api.pexels.com/videos/search?query={query}&per_page={limit}"
            
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.error(f"❌ Failed to fetch video search result from Pexels for '{query}': {e}")
                continue

            videos = data.get("videos", [])
            logger.info(f"Found {len(videos)} videos on Pexels. Commencing HLS-chunking crawler process...")

            count = 0
            for v in videos:
                if count >= limit:
                    break
                success = await process_pexels_video_hls(
                    video_data=v,
                    query=query,
                    category=category,
                    intensity_level=intensity,
                    creator_id=creator_id,
                    client=client,
                    video_service=video_service
                )
                if success:
                    count += 1
            
            logger.info(f"✓ Completed category '{category}': Imported {count} videos successfully.")

    await disconnect_db()
    logger.info("🔌 Disconnected from MongoDB. Crawling phase finished!")

def start_services_and_app():
    """Start Celery worker in the background and FastAPI in the foreground, managing their lifecycles."""
    from app.config import settings
    port = settings.PORT or 8033

    # Command to start Celery worker
    celery_cmd = [
        sys.executable, "-m", "celery",
        "-A", "app.celery_app", "worker",
        "--loglevel=info", "--concurrency=2"
    ]
    
    # Command to start FastAPI
    fastapi_cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", str(port)
    ]

    logger.info(f"🚀 Starting Celery background worker: {' '.join(celery_cmd)}")
    celery_proc = None
    try:
        # Start Celery worker in the background
        celery_proc = subprocess.Popen(
            celery_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Log Celery output stream asynchronously
        import threading
        def log_stream(stream, prefix):
            for line in stream:
                logger.info(f"[{prefix}] {line.strip()}")

        t = threading.Thread(target=log_stream, args=(celery_proc.stdout, "Celery"), daemon=True)
        t.start()
        
        logger.info("✅ Celery worker launched in background.")
        logger.info(f"🚀 Launching local Backend FastAPI application server: {' '.join(fastapi_cmd)}")
        
        # Start FastAPI (blocking)
        subprocess.run(fastapi_cmd, check=True)

    except KeyboardInterrupt:
        logger.info("🛑 KeyboardInterrupt received. Shutting down servers...")
    except Exception as e:
        logger.error(f"❌ Error during server execution: {e}")
    finally:
        if celery_proc:
            logger.info("🛑 Terminating Celery worker process...")
            celery_proc.terminate()
            try:
                celery_proc.wait(timeout=5)
                logger.info("✅ Celery worker terminated successfully.")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Celery worker did not terminate in time. Killing it forcibly...")
                celery_proc.kill()
                celery_proc.wait()
                logger.info("✅ Celery worker killed.")

def sync_users_from_atlas():
    """
    Crawl users collection from online MongoDB Atlas to users.json (if not exists),
    then insert/upsert them into the local MongoDB database.
    """
    logger.info("👥 Starting user synchronization step...")
    json_path = "users.json"
    
    # 1. Check if users.json exists
    if not os.path.exists(json_path):
        logger.info("🔍 File users.json not found. Crawling users from online MongoDB Atlas...")
        atlas_uri = "mongodb+srv://nguyenhoangan03study_db_user:Cytr1NtuWnd4LLfY@cluster0.dzjbtvv.mongodb.net/gotouchgrass?retryWrites=true&w=majority&appName=Cluster0"
        try:
            from bson import json_util
            import json
            from pymongo import MongoClient
            
            # Connect to Atlas online
            logger.info("🔌 Connecting to online MongoDB Atlas...")
            client = MongoClient(atlas_uri, serverSelectionTimeoutMS=5000)
            db = client["gotouchgrass"]
            collection = db["users"]
            
            # Fetch all users
            users = list(collection.find({}))
            logger.info(f"📥 Successfully fetched {len(users)} users from Atlas.")
            
            # Dump to JSON file using json_util to handle ObjectId and DateTime correctly
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json.loads(json_util.dumps(users)), f, indent=4, ensure_ascii=False)
            
            logger.info(f"💾 Users data successfully saved to local file: {json_path}")
            client.close()
        except Exception as e:
            logger.error(f"❌ Failed to crawl users from online Mongo Atlas: {e}")
            logger.info("⚠️ Continuing setup without fresh crawl (fallback to local if users.json exists, or skip).")
            if not os.path.exists(json_path):
                logger.warning("⚠️ No users.json file available. Skipping user import.")
                return
    else:
        logger.info(f"✓ Found existing users data file: {json_path}")

    # 2. Read users.json and insert/upsert into local MongoDB
    try:
        from bson import json_util
        from pymongo import MongoClient, ReplaceOne
        import json
        
        # Load local .env to make sure MONGODB_URI is correctly read
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        local_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/gotouchgrass?directConnection=true")
        
        logger.info(f"🔌 Connecting to local MongoDB: {local_uri}")
        local_client = MongoClient(local_uri)
        local_db = local_client["gotouchgrass"]
        local_col = local_db["users"]
        
        # Read data from users.json
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = f.read()
            users_list = json_util.loads(raw_data)
        
        if not users_list:
            logger.warning(f"⚠️ No user data found inside {json_path}.")
            local_client.close()
            return
            
        logger.info(f"📥 Loading {len(users_list)} users into local MongoDB...")
        
        # Build ReplaceOne operations for upsert based on _id
        operations = []
        for user in users_list:
            if "_id" in user:
                operations.append(ReplaceOne({"_id": user["_id"]}, user, upsert=True))
            else:
                operations.append(ReplaceOne({"username": user.get("username")}, user, upsert=True))
        
        if operations:
            result = local_col.bulk_write(operations)
            logger.info(
                f"✅ User synchronization complete: "
                f"{result.matched_count} matched, "
                f"{result.modified_count} modified, "
                f"{result.upserted_count} upserted."
            )
        
        local_client.close()
    except Exception as e:
        logger.error(f"❌ Failed to import users into local MongoDB: {e}")

def main():
    parser = argparse.ArgumentParser(description="Orchestrator script for Local Setup, Crawl and Launch.")
    parser.add_argument("--limit", type=int, default=30, help="Number of videos to crawl per category (default: 30)")
    parser.add_argument("--query", type=str, default="all", help="Pexels query terms. Use 'all' or comma-separated values.")
    parser.add_argument("--skip-crawl", action="store_true", help="Skip the crawling and chunking phase.")
    parser.add_argument("--skip-launch", action="store_true", help="Skip launching the FastAPI application server.")
    args = parser.parse_args()

    # 1. Install missing pip libraries
    check_python_dependencies()

    # 2. Check system commands (ffmpeg, docker, etc.)
    docker_compose_cmd = check_system_tools()
    check_docker_images()

    # 3. Check for local port conflicts
    check_port_conflicts()

    # Detect existing native services on host
    mongo_exists, redis_exists = check_existing_services()

    # 4. Modify .env config to point to local
    update_env_file()

    # 5. Start docker containers (only starting what's not running natively)
    start_docker_services(docker_compose_cmd, mongo_exists, redis_exists)

    # 6. Check health of services
    run_health_checks()

    # 7. Synchronize users from online Atlas to local DB
    sync_users_from_atlas()

    # 8. Crawl Pexels high-quality videos and package HLS chunks
    if not args.skip_crawl:
        import asyncio
        asyncio.run(run_crawlers(limit=args.limit, query_override=args.query))
    else:
        logger.info("⏭️ Skipped crawling phase.")

    # 9. Start the backend app server
    if not args.skip_launch:
        start_services_and_app()
    else:
        logger.info("⏭️ Setup and crawl complete. App launch skipped by command argument.")

if __name__ == "__main__":
    main()

