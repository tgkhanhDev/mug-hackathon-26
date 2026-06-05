import random
import time
import requests
from locust import HttpUser, task, between, events

# Shared pool of users and videos to simulate realistic loads
users_pool = []
videos_pool = []

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Prefetch users and videos from the API to populate the load testing pool.
    """
    print("🚀 Pre-fetching users and videos for load test...")
    host = environment.host or "http://217.216.73.190"
    # Fetch up to 100 users
    try:
        response = requests.get(f"{host}/api/v1/users?limit=100", timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("items", []):
                users_pool.append(item)
            print(f"✓ Found {len(users_pool)} users in the pool.")
        else:
            print(f"❌ Failed to fetch users: {response.status_code}")
    except Exception as e:
        print(f"❌ Exception fetching users: {e}")

    # Fetch trending videos to use as interaction targets
    try:
        response = requests.get(f"{host}/api/v1/videos/trending?limit=20", timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                videos_pool.append(item)
            print(f"✓ Found {len(videos_pool)} videos in the pool.")
        else:
            print(f"❌ Failed to fetch trending videos: {response.status_code}")
    except Exception as e:
        print(f"❌ Exception fetching videos: {e}")

    # If the pools are empty, add fallback mock data to prevent crashes
    if not users_pool:
        users_pool.append({"id": "6a224871ff8ed2f4ed10fcb4", "username": "fallback_user"})
        print("⚠️ Using fallback user in pool")
    if not videos_pool:
        videos_pool.append({"id": "6a22360053458f9b8211d7c3", "topic": "fitness", "intensity_level": "high"})
        print("⚠️ Using fallback video in pool")


class GoTouchGrassAppUser(HttpUser):
    # Simulated think time between user actions (1 to 3 seconds)
    wait_time = between(1.0, 3.0)

    def on_start(self):
        """
        Executed when a virtual user starts.
        Sets up the user's identity and creates a browsing session.
        """
        # Assign a random user from the pre-fetched pool
        self.user = random.choice(users_pool)
        self.user_id = self.user["id"]
        self.session_id = None
        self.active_videos = []

        # Create session
        payload = {"user_id": self.user_id}
        try:
            with self.client.post("/api/v1/sessions", json=payload, catch_response=True) as response:
                if response.status_code == 201:
                    self.session_id = response.json().get("id")
                    response.success()
                else:
                    response.failure(f"Session creation failed with status {response.status_code}")
        except Exception as e:
            pass

    @task(3)
    def get_feed(self):
        """
        Simulate user requesting their personalized video recommendation feed.
        """
        try:
            with self.client.get(
                f"/api/v1/feed/{self.user_id}?limit=5",
                name="/api/v1/feed/{user_id}",
                catch_response=True
            ) as response:
                if response.status_code == 200:
                    feed_data = response.json()
                    # Store feed videos so the user can interact with them
                    self.active_videos = feed_data
                    response.success()
                else:
                    response.failure(f"Feed retrieval failed: {response.status_code}")
        except Exception:
            pass

    @task(2)
    def view_trending(self):
        """
        Simulate user clicking the 'Trending' tab to see hot videos.
        """
        self.client.get("/api/v1/videos/trending?limit=5")

    @task(5)
    def simulate_scrolling_and_viewing(self):
        """
        Simulate user scrolling and viewing videos.
        Pushes behavior logs (passive interactions) to Kafka.
        """
        if not self.session_id:
            return

        # Choose a video from the feed or the trending pool
        video = None
        if self.active_videos and random.random() < 0.7:
            video = random.choice(self.active_videos)
        elif videos_pool:
            video = random.choice(videos_pool)

        if not video:
            return

        video_id = video.get("id") or video.get("_id")
        topic = video.get("topic", "general")

        # Simulate passive viewing metrics
        watch_duration = round(random.uniform(0.5, 20.0), 2)
        swipe_speed = round(random.uniform(10.0, 1500.0), 2)
        is_interaction = random.choice([True, False])

        # Doomscrolling signature: fast swipe, short watch, no interaction
        if random.random() < 0.2:
            watch_duration = round(random.uniform(0.1, 1.8), 2)
            swipe_speed = round(random.uniform(850.0, 1800.0), 2)
            is_interaction = False

        payload = {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "video_id": video_id,
            "swipe_speed": swipe_speed,
            "watch_duration": watch_duration,
            "is_interaction": is_interaction,
            "topic": topic
        }

        self.client.post("/api/v1/behavior-logs", json=payload)

    @task(1)
    def simulate_like_or_replay(self):
        """
        Simulate active user interaction (like or replay).
        Updates state in MongoDB.
        """
        if not self.session_id:
            return

        video = None
        if self.active_videos:
            video = random.choice(self.active_videos)
        elif videos_pool:
            video = random.choice(videos_pool)

        if not video:
            return

        video_id = video.get("id") or video.get("_id")
        interaction_type = random.choice(["like", "replay"])

        payload = {
            "user_id": self.user_id,
            "video_id": video_id,
            "session_id": self.session_id,
            "type": interaction_type
        }

        self.client.post("/api/v1/interactions", json=payload)
