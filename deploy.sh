#!/bin/bash
set -e

echo "🚀 Starting GoTouchGrass VPS Deployment..."

# 1. Ensure git is installed
if ! command -v git &> /dev/null; then
    echo "❌ git is not installed. Please install git."
    exit 1
fi

# 2. Check if Docker & Docker Compose are installed, try to install if missing
if ! command -v docker &> /dev/null; then
    echo "⚠️ Docker is not installed. Attempting auto-installation..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker installed successfully."
fi

# Check Docker Compose plugin
DOCKER_COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    echo "⚠️ Docker Compose plugin is missing. Attempting installation..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
    DOCKER_COMPOSE_CMD="docker compose"
    echo "✅ Docker Compose plugin installed successfully."
fi

# 3. Pull latest code from specified branch (defaults to release)
DEPLOY_BRANCH=${1:-release}
echo "📥 Fetching latest code from branch '$DEPLOY_BRANCH'..."
git fetch origin "$DEPLOY_BRANCH"
git reset --hard origin/"$DEPLOY_BRANCH"


# 4. Detect VPS public IP for dynamic MinIO endpoint
echo "🔍 Auto-detecting VPS Public IP..."
PUBLIC_IP=$(curl -4 -s https://ifconfig.me || curl -4 -s https://api.ipify.org || echo "217.216.73.190")
echo "🌐 Public IP: $PUBLIC_IP"

# Use public IP for MinIO endpoint if MINIO_ENDPOINT_URL is not set externally
if [ -z "$MINIO_ENDPOINT_URL" ]; then
    MINIO_ENDPOINT_URL="http://$PUBLIC_IP:9000"
fi
echo "🔗 MinIO Public Endpoint: $MINIO_ENDPOINT_URL"

# 5. Build production .env file
echo "📝 Writing environment configurations to .env..."

# Load existing .env to preserve values not passed via secrets
if [ -f .env ]; then
    # Extract existing MONGODB_URI if not passed from outside
    EXISTING_MONGODB_URI=$(grep '^MONGODB_URI=' .env | cut -d'=' -f2- | tr -d '[:space:]')
    EXISTING_JWT_SECRET=$(grep '^JWT_SECRET_KEY=' .env | cut -d'=' -f2-)
    EXISTING_PEXELS=$(grep '^PEXELS_API_KEY=' .env | cut -d'=' -f2-)
    EXISTING_OPENAI=$(grep '^OPENAI_API_KEY=' .env | cut -d'=' -f2-)
fi

# Use passed secrets, fall back to existing .env values, then defaults
FINAL_MONGODB_URI="${MONGODB_URI:-$EXISTING_MONGODB_URI}"
FINAL_PEXELS="${PEXELS_API_KEY:-$EXISTING_PEXELS}"
FINAL_OPENAI="${OPENAI_API_KEY:-$EXISTING_OPENAI}"
FINAL_JWT="${JWT_SECRET_KEY:-${EXISTING_JWT_SECRET:-$(openssl rand -hex 32 2>/dev/null || echo 'vps-default-secret-key-321-abc')}}"

if [ -z "$FINAL_MONGODB_URI" ]; then
    echo "❌ MONGODB_URI is not set. Provide it via GitHub Secret or existing .env"
    exit 1
fi

cat <<EOF > .env
# MongoDB Atlas
MONGODB_URI=${FINAL_MONGODB_URI}
DATABASE_NAME=${DATABASE_NAME:-gotouchgrass}

# S3 / MinIO Configuration
MINIO_ENDPOINT_URL=${MINIO_ENDPOINT_URL}
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-minioadmin}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-minioadmin}
MINIO_BUCKET_NAME=${MINIO_BUCKET_NAME:-gotouchgrass-media}
MINIO_USE_SSL=${MINIO_USE_SSL:-False}

# Crawler & AI APIs
PEXELS_API_KEY=${FINAL_PEXELS}
OPENAI_API_KEY=${FINAL_OPENAI}

# JWT Auth Config
JWT_SECRET_KEY=${FINAL_JWT}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
EOF

echo "✅ Production .env created."

# 6. Spin up production containers
echo "🏗️ Starting production Docker containers..."
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml down --remove-orphans || true
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml up -d --build

# 7. Post-deployment cleanup (remove dangling/old images to save VPS storage)
echo "🧹 Cleaning up old Docker images..."
docker image prune -f

echo "🎉 Deployment successfully completed! Application is live."
echo "   - Frontend is running on: http://$PUBLIC_IP"
echo "   - Backend API is running on: http://$PUBLIC_IP/api/v1 (proxied)"
echo "   - MinIO Console: http://$PUBLIC_IP:9001"
echo "   - MinIO API endpoint: $MINIO_ENDPOINT_URL"
