# 🌿 GoTouchGrass Backend Setup Guide

Welcome to the backend setup guide for the **GoTouchGrass (Mindful Feed Recommendation Engine)** MVP. This backend is built using a modern Python stack featuring **FastAPI**, **Motor (Async MongoDB Driver)**, and **APScheduler**.

---

## 1. Architecture: N-Layer Pattern

The codebase is organized following a strict N-Layer architecture to ensure modularity, ease of testing, and clean separation of concerns:

```
┌──────────────────────────────────────────────────┐
│                  Controller Layer                 │
│         (Routing, validation, HTTP concerns)      │
├──────────────────────────────────────────────────┤
│                   Service Layer                   │
│    (Business logic, embedding, trending calc)     │
├──────────────────────────────────────────────────┤
│                 Repository Layer                  │
│   (MongoDB CRUD, aggregation, vector search)      │
│   database.py (connection) lives here             │
├──────────────────────────────────────────────────┤
│              MongoDB Atlas (Cloud)                │
│     Vector Search • Time-Series • Aggregation     │
└──────────────────────────────────────────────────┘
```

* **Controller Layer (`app/controllers/`)**: Handles request/response schemas, routing, HTTP statuses, and inputs validation.
* **Service Layer (`app/services/`)**: Orchestrates business logic, such as constructing the text block for embedding creation and calculating trending scores.
* **Repository Layer (`app/repositories/`)**: Directly communicates with MongoDB. Contains connection lifetime management and optimized database aggregations.
* **Models (`app/models/`)**: Structured using **Pydantic** for schema definition and DTOs (Request / Response / DB Internal).

---

## 2. Directory Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI application initialization & lifespan
│   ├── config.py                        # Pydantic-settings environment config loader
│   │
│   ├── models/                          # 📋 Pydantic schemas (DTOs & DB schemas)
│   │   ├── video.py                     # VideoCreate, VideoResponse, VideoInDB
│   │   ├── user.py                      # UserCreate, UserResponse, UserInDB
│   │   ├── interaction.py               # Interaction schemas (like, skip, etc.)
│   │   ├── feed_session.py              # Feed session metadata & fatigue tracking
│   │   ├── behavior_log.py              # Raw behavior logs for sliding window analysis
│   │   └── auth.py                      # Login, register, and token payload DTOs
│   │
│   ├── repositories/                    # 💾 Database / Data Access Layer
│   │   ├── database.py                  # MongoDB Motor client & collection initializer
│   │   ├── base.py                      # Generic Repository with async CRUD helpers
│   │   ├── video_repository.py          # Video data layer (vector searches & trendings)
│   │   └── user_repository.py           # User data layer (profile & interest vector updates)
│   │
│   ├── services/                        # ⚙️ Business Logic Layer
│   │   ├── video_service.py             # Video creation, embedding, and list orchestration
│   │   ├── user_service.py              # User onboarding & interest vector averages
│   │   └── auth_service.py              # JWT authentication & password hashing stubs
│   │
│   ├── controllers/                     # 🌐 API Routers (Thin handlers)
│   │   ├── video_controller.py          # POST/GET /api/v1/videos
│   │   ├── user_controller.py           # POST/GET /api/v1/users
│   │   ├── auth_controller.py           # POST /api/v1/auth/register|login|refresh
│   │   └── scheduler_controller.py      # Runtime configuration of embedding scheduler
│   │
│   └── utils/                           # 🔧 Helper Utilities
│       ├── embedding.py                 # OpenAI & seeded Mock embedding generator
│       ├── exceptions.py                # App exceptions & global handlers
│       └── scheduler.py                 # APScheduler background tasks
│
├── docs/
│   └── backend_setup_guide.md           # This guide
├── .env.example                         # Template env file
├── requirements.txt                     # System package dependencies
└── .env                                 # Local configuration (created during setup)
```

---

## 3. Quick Setup

### Step 3.1: Initialize and Install Dependencies
Navigate into the `backend/` directory, create a Python virtual environment, and install dependencies:

```bash
cd /home/nhphat/Personal/WorkSpace/Hackathon/backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Step 3.2: Configure Environment Variables (`.env`)
Copy the template configuration file to `.env`:

```bash
cp .env.example .env
```

Modify the `.env` file to fit your database configurations:

```env
# MongoDB Connection String (Atlas or Local)
MONGODB_URI=mongodb://admin:password@localhost:27017/gotouchgrass?authSource=admin
DATABASE_NAME=gotouchgrass

# OpenAI API Key (Leave empty to use Mock Embedding Mode)
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small

# JWT Security Configurations
JWT_SECRET_KEY=dev-secret-key-gotouchgrass-hackathon-2026
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Scheduler Intervals (in minutes)
EMBEDDING_SCHEDULE_INTERVAL_MINUTES=60

# FastAPI Port
PORT=8033
```

> 🎲 **No OpenAI Key?** Leaving `OPENAI_API_KEY` empty triggers **Mock Embedding Mode**. The backend will generate deterministic 1536-dimensional mock vectors from text hashes, allowing you to test the complete flow end-to-end without incurring API costs.

### Step 3.3: Set Up Atlas Vector Search Index (Required for Phase 2+)
If utilizing MongoDB Atlas for Vector Search, configure the vector index manually on the Atlas UI:

1. Open your **MongoDB Atlas Console**.
2. Go to **Atlas Search** under Services -> **Create Search Index**.
3. Select the **JSON Editor** option.
4. Set the Target Database to `gotouchgrass` and Collection to `videos`.
5. Paste the following configuration:

```json
{
  "name": "video_embedding_index",
  "type": "vectorSearch",
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    }
  ]
}
```
6. Click **Create Index** and wait until its status changes to **Active**.

---

## 4. Run the Server

Start the application with Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8033
```

Your server will be up and running at: **http://localhost:8033**

---

## 5. API Testing Commands

Here are some sample `curl` commands to test the system:

### 5.1. System Health Check
Check connection health status and verified indexes:
```bash
curl -s http://localhost:8033/health
```

### 5.2. Admin - Add a Video (`POST /api/v1/videos`)
Pushes a video with metadata. Automatically computes its `trending_score` and triggers the embedding processor:
```bash
curl -s -X POST http://localhost:8033/api/v1/videos \
  -H "Content-Type: application/json" \
  -d '{
    "title": "10 Coding Memes Only Devs Understand 😂",
    "description": "Relatable content for programmers who debug at 3AM. Funny and dark humor about software development life.",
    "url": "https://cdn.example.com/video-001.mp4",
    "thumbnail_url": "https://cdn.example.com/thumb-001.jpg",
    "tags": ["coding", "meme", "programmer"],
    "category": "entertainment",
    "intensity_level": "high",
    "creator_id": "creator_devjokes",
    "view_count": 3200,
    "like_count": 540,
    "comment_count": 87
  }'
```

### 5.3. Onboarding - Create a User (`POST /api/v1/users`)
Registers an onboarding user, calculating their initial `interest_vector` from matches:
```bash
curl -s -X POST http://localhost:8033/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tgkhanh_dev",
    "email": "khanh@example.com",
    "interest_tags": ["coding", "calming"]
  }'
```

### 5.4. Scheduler Status (`GET /api/v1/scheduler/embedding`)
Inspect the next run schedule of the async embedding background task:
```bash
curl -s http://localhost:8033/api/v1/scheduler/embedding
```

---

## 6. Automatically Initialized MongoDB Collections

Upon server startup, the backend automatically initializes the following database schemas and sets indexes:

| Collection Name | Collection Type | Index strategy |
|---|---|---|
| `videos` | Regular | Cosine vector index (`embedding`), compound `tags` & `category`, and `trending_score` (desc) |
| `users` | Regular | Unique index on `username` |
| `interactions` | Regular | Chronological index on `user_id` and `timestamp` (desc) |
| `feed_sessions` | Regular | Search indexes for active sessions (`user_id`, `ended_at`) |
| `behavior_logs` | **Time-Series** | Optimized for temporal queries using metadata `session_id` and `timestamp` |
