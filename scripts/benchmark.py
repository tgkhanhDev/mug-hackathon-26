#!/usr/bin/env python3
"""
🌿 GoTouchGrass — Benchmark Script for Hackathon Slide 6

Measures:
  1. Feed API Latency (P50, P95, P99, avg, min, max)
  2. Behavior Log Ingestion Throughput
  3. Session Creation & Retrieval Latency
  4. Vector Search vs Cold-Start (Trending) Latency
  5. Fatigue State Transition Speed (Normal → Warning → Exhausted)
  6. End-to-End Adaptive Feed Reranking Time
  7. Concurrent Users Simulation

Usage:
  python scripts/benchmark.py --base-url http://localhost:8033 --runs 50
  python scripts/benchmark.py --base-url http://localhost:8033 --runs 100 --concurrent 10
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    print("❌ httpx is required. Install with: pip install httpx")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════

API_PREFIX = "/api/v1"
COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m",
    "dim": "\033[2m",
}


def color(text: str, c: str) -> str:
    return f"{COLORS.get(c, '')}{text}{COLORS['reset']}"


def print_header(title: str):
    width = 60
    print(f"\n{color('═' * width, 'cyan')}")
    print(f"{color(f'  {title}', 'bold')}")
    print(f"{color('═' * width, 'cyan')}")


def print_latency_stats(label: str, latencies_ms: List[float]):
    if not latencies_ms:
        print(f"  {label}: No data")
        return
    latencies_ms.sort()
    n = len(latencies_ms)
    avg = statistics.mean(latencies_ms)
    p50 = latencies_ms[int(n * 0.50)]
    p95 = latencies_ms[int(min(n * 0.95, n - 1))]
    p99 = latencies_ms[int(min(n * 0.99, n - 1))]

    def fmt(v: float) -> str:
        if v < 100:
            return color(f"{v:.1f}ms", "green")
        elif v < 300:
            return color(f"{v:.1f}ms", "yellow")
        else:
            return color(f"{v:.1f}ms", "red")

    print(f"  {color(label, 'bold')}:")
    print(f"    Avg: {fmt(avg)}  |  P50: {fmt(p50)}  |  P95: {fmt(p95)}  |  P99: {fmt(p99)}")
    print(f"    Min: {fmt(min(latencies_ms))}  |  Max: {fmt(max(latencies_ms))}  |  Samples: {n}")


# ═══════════════════════════════════════════════════════════════
# API Helpers
# ═══════════════════════════════════════════════════════════════

async def timed_request(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> tuple[float, Any]:
    """Execute an HTTP request and return (latency_ms, response_json)."""
    start = time.perf_counter()
    resp = await client.request(method, url, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    resp.raise_for_status()
    return elapsed_ms, resp.json()


async def get_any_user(client: httpx.AsyncClient, base: str) -> Optional[Dict]:
    """Fetch any user from the database."""
    resp = await client.get(f"{base}{API_PREFIX}/users")
    if resp.status_code == 200:
        users = resp.json()
        if isinstance(users, list) and len(users) > 0:
            return users[0]
        if isinstance(users, dict) and users.get("data"):
            return users["data"][0]
    return None


async def get_any_video(client: httpx.AsyncClient, base: str) -> Optional[Dict]:
    """Fetch any video from the database."""
    resp = await client.get(f"{base}{API_PREFIX}/videos", params={"limit": 1})
    if resp.status_code == 200:
        videos = resp.json()
        if isinstance(videos, list) and len(videos) > 0:
            return videos[0]
        if isinstance(videos, dict) and videos.get("data"):
            return videos["data"][0]
    return None


# ═══════════════════════════════════════════════════════════════
# Benchmark 1: Feed API Latency
# ═══════════════════════════════════════════════════════════════

async def bench_feed_latency(client: httpx.AsyncClient, base: str, user_id: str, runs: int) -> List[float]:
    """Measure GET /feed/{user_id} latency across multiple runs."""
    print_header("📊 Benchmark 1: Feed API Latency (Vector Search + Reranking)")
    latencies = []
    errors = 0

    for i in range(runs):
        try:
            ms, data = await timed_request(client, "GET", f"{base}{API_PREFIX}/feed/{user_id}", params={"limit": 5})
            latencies.append(ms)
            if (i + 1) % 10 == 0:
                print(f"    Run {i+1}/{runs}: {ms:.1f}ms ({len(data)} videos)")
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"    ⚠️ Run {i+1} error: {e}")

    print_latency_stats("Feed API (Vector Search → Reranking → Response)", latencies)
    if errors:
        print(f"    Errors: {color(str(errors), 'red')}/{runs}")
    return latencies


# ═══════════════════════════════════════════════════════════════
# Benchmark 2: Behavior Log Ingestion
# ═══════════════════════════════════════════════════════════════

async def bench_behavior_log(
    client: httpx.AsyncClient, base: str, user_id: str, session_id: str, video_id: str, runs: int
) -> List[float]:
    """Measure POST /behavior-logs latency (includes Redis write + Kafka produce)."""
    print_header("📊 Benchmark 2: Behavior Log Ingestion (Redis + Kafka)")
    latencies = []
    errors = 0

    for i in range(runs):
        try:
            payload = {
                "user_id": user_id,
                "session_id": session_id,
                "video_id": video_id,
                "swipe_speed": 1.5 + (i % 5) * 0.3,
                "watch_duration": 2.0 + (i % 10) * 0.5,
                "is_interaction": i % 3 == 0,
                "topic": ["nature", "comedy", "music", "tech", "art"][i % 5],
            }
            ms, _ = await timed_request(client, "POST", f"{base}{API_PREFIX}/behavior-logs", json=payload)
            latencies.append(ms)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"    ⚠️ Run {i+1} error: {e}")

    print_latency_stats("Behavior Log Ingestion", latencies)
    if errors:
        print(f"    Errors: {color(str(errors), 'red')}/{runs}")
    return latencies


# ═══════════════════════════════════════════════════════════════
# Benchmark 3: Session CRUD
# ═══════════════════════════════════════════════════════════════

async def bench_session_ops(client: httpx.AsyncClient, base: str, user_id: str, runs: int) -> Dict[str, List[float]]:
    """Measure session create → get → end cycle latency."""
    print_header("📊 Benchmark 3: Session Lifecycle (Create → Get → End)")
    create_lat = []
    get_lat = []
    end_lat = []

    for i in range(runs):
        try:
            # Create session
            ms_create, sess = await timed_request(
                client, "POST", f"{base}{API_PREFIX}/sessions", json={"user_id": user_id}
            )
            sid = sess.get("id")
            create_lat.append(ms_create)

            # Get session
            ms_get, _ = await timed_request(client, "GET", f"{base}{API_PREFIX}/sessions/{sid}")
            get_lat.append(ms_get)

            # End session
            ms_end, _ = await timed_request(client, "PUT", f"{base}{API_PREFIX}/sessions/{sid}/end")
            end_lat.append(ms_end)

        except Exception as e:
            if len(create_lat) <= 3:
                print(f"    ⚠️ Run {i+1} error: {e}")

    print_latency_stats("Session Create", create_lat)
    print_latency_stats("Session Get", get_lat)
    print_latency_stats("Session End (+ batch vector update)", end_lat)
    return {"create": create_lat, "get": get_lat, "end": end_lat}


# ═══════════════════════════════════════════════════════════════
# Benchmark 4: Trending vs Vector Search Comparison
# ═══════════════════════════════════════════════════════════════

async def bench_trending_vs_vector(client: httpx.AsyncClient, base: str, user_id: str, runs: int):
    """Compare cold-start trending vs personalized vector search latency."""
    print_header("📊 Benchmark 4: Cold-Start (Trending) vs Personalized (Vector Search)")

    trending_lat = []
    vector_lat = []

    for i in range(runs):
        try:
            # Trending (cold-start)
            ms, _ = await timed_request(
                client, "GET", f"{base}{API_PREFIX}/videos/trending-decay", params={"limit": 5}
            )
            trending_lat.append(ms)

            # Vector search (personalized)
            ms, _ = await timed_request(
                client, "GET", f"{base}{API_PREFIX}/feed/{user_id}", params={"limit": 5}
            )
            vector_lat.append(ms)
        except Exception as e:
            pass

    print_latency_stats("Cold-Start (Trending)", trending_lat)
    print_latency_stats("Personalized (Vector Search + Reranking)", vector_lat)


# ═══════════════════════════════════════════════════════════════
# Benchmark 5: Fatigue State Transition (E2E)
# ═══════════════════════════════════════════════════════════════

async def bench_fatigue_transition(
    client: httpx.AsyncClient, base: str, user_id: str, video_id: str
) -> Dict[str, Any]:
    """
    Simulate doomscrolling: send rapid behavior logs until state transitions to
    exhausted. Measures the E2E time from normal → warning → exhausted.
    """
    print_header("📊 Benchmark 5: Fatigue State Transition (Doomscrolling Simulation)")

    # Create a fresh session
    _, sess = await timed_request(client, "POST", f"{base}{API_PREFIX}/sessions", json={"user_id": user_id})
    session_id = sess["id"]
    print(f"  Session: {session_id}")

    states_seen = {"normal": None, "warning": None, "exhausted": None, "critical": None}
    start_time = time.perf_counter()
    state = "normal"
    log_count = 0
    max_logs = 60  # Safety limit

    while state not in ("exhausted", "critical") and log_count < max_logs:
        # Simulate doomscrolling: very fast swipe, short watch
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "video_id": video_id,
            "swipe_speed": 8.0 + log_count * 0.2,  # Progressively faster
            "watch_duration": max(0.3, 1.5 - log_count * 0.02),  # Progressively shorter
            "is_interaction": False,
            "topic": "tech",  # Same topic = consecutive penalty
        }
        try:
            await timed_request(client, "POST", f"{base}{API_PREFIX}/behavior-logs", json=payload)
            log_count += 1

            # Small delay to let Kafka consumer process
            await asyncio.sleep(0.15)

            # Check session state
            _, session_data = await timed_request(client, "GET", f"{base}{API_PREFIX}/sessions/{session_id}")
            new_state = session_data.get("adaptive_state", "normal")
            fatigue = session_data.get("fatigue_score", 0)

            if new_state != state:
                elapsed = (time.perf_counter() - start_time) * 1000
                states_seen[new_state] = {"elapsed_ms": elapsed, "log_count": log_count, "fatigue_score": fatigue}
                print(f"    📍 {state} → {color(new_state, 'yellow')} "
                      f"(logs: {log_count}, fatigue: {fatigue:.1f}, elapsed: {elapsed:.0f}ms)")
                state = new_state

        except Exception as e:
            print(f"    ⚠️ Log {log_count} error: {e}")
            log_count += 1

    # End session
    try:
        await timed_request(client, "PUT", f"{base}{API_PREFIX}/sessions/{session_id}/end")
    except Exception:
        pass

    total_ms = (time.perf_counter() - start_time) * 1000
    print(f"\n  {color('Result:', 'bold')}")
    print(f"    Total logs sent: {log_count}")
    print(f"    Final state: {color(state, 'yellow')}")
    print(f"    Total time: {total_ms:.0f}ms")
    for s, data in states_seen.items():
        if data:
            print(f"    → {s}: reached at log #{data['log_count']} "
                  f"({data['elapsed_ms']:.0f}ms, fatigue={data['fatigue_score']:.1f})")

    return {"total_logs": log_count, "final_state": state, "total_ms": total_ms, "transitions": states_seen}


# ═══════════════════════════════════════════════════════════════
# Benchmark 6: Concurrent Feed Requests
# ═══════════════════════════════════════════════════════════════

async def bench_concurrent(client: httpx.AsyncClient, base: str, user_id: str, concurrent: int) -> List[float]:
    """Fire N concurrent feed requests and measure all latencies."""
    print_header(f"📊 Benchmark 6: Concurrent Feed Requests ({concurrent} parallel)")

    async def single_request() -> float:
        ms, _ = await timed_request(client, "GET", f"{base}{API_PREFIX}/feed/{user_id}", params={"limit": 5})
        return ms

    tasks = [single_request() for _ in range(concurrent)]
    latencies = await asyncio.gather(*tasks, return_exceptions=True)

    valid = [l for l in latencies if isinstance(l, float)]
    errors = [l for l in latencies if isinstance(l, Exception)]

    print_latency_stats(f"Concurrent ({concurrent} requests)", valid)
    if errors:
        print(f"    Errors: {color(str(len(errors)), 'red')}/{concurrent}")
    return valid


# ═══════════════════════════════════════════════════════════════
# Benchmark 7: Database Aggregation Pipeline Latency
# ═══════════════════════════════════════════════════════════════

async def bench_health_and_db(client: httpx.AsyncClient, base: str, runs: int) -> List[float]:
    """Measure health check (includes DB ping) latency."""
    print_header("📊 Benchmark 7: Health Check (DB Ping)")
    latencies = []
    for _ in range(runs):
        try:
            ms, _ = await timed_request(client, "GET", f"{base}/health")
            latencies.append(ms)
        except Exception:
            pass
    print_latency_stats("Health Check (MongoDB Ping)", latencies)
    return latencies


# ═══════════════════════════════════════════════════════════════
# Summary Report
# ═══════════════════════════════════════════════════════════════

def print_summary(results: Dict[str, Any]):
    print_header("📋 BENCHMARK SUMMARY — Slide 6 Numbers")

    def safe_avg(vals):
        return statistics.mean(vals) if vals else 0

    def safe_p95(vals):
        if not vals:
            return 0
        vals.sort()
        return vals[int(min(len(vals) * 0.95, len(vals) - 1))]

    def safe_p99(vals):
        if not vals:
            return 0
        vals.sort()
        return vals[int(min(len(vals) * 0.99, len(vals) - 1))]

    rows = []
    if "feed" in results:
        rows.append(("Feed API (Vector Search)", safe_avg(results["feed"]), safe_p95(results["feed"]), safe_p99(results["feed"])))
    if "behavior_log" in results:
        rows.append(("Behavior Log Ingestion", safe_avg(results["behavior_log"]), safe_p95(results["behavior_log"]), safe_p99(results["behavior_log"])))
    if "session" in results:
        for key in ["create", "get", "end"]:
            if key in results["session"]:
                rows.append((f"Session {key.capitalize()}", safe_avg(results["session"][key]), safe_p95(results["session"][key]), safe_p99(results["session"][key])))
    if "concurrent" in results:
        rows.append(("Concurrent Feed", safe_avg(results["concurrent"]), safe_p95(results["concurrent"]), safe_p99(results["concurrent"])))
    if "health" in results:
        rows.append(("Health (DB Ping)", safe_avg(results["health"]), safe_p95(results["health"]), safe_p99(results["health"])))

    print(f"\n  {'Metric':<35} {'Avg':>10} {'P95':>10} {'P99':>10}")
    print(f"  {'─' * 35} {'─' * 10} {'─' * 10} {'─' * 10}")
    for label, avg, p95, p99 in rows:
        print(f"  {label:<35} {avg:>8.1f}ms {p95:>8.1f}ms {p99:>8.1f}ms")

    if "fatigue" in results:
        ft = results["fatigue"]
        print(f"\n  {color('Fatigue State Transition:', 'bold')}")
        print(f"    Final state: {ft['final_state']}")
        print(f"    Logs needed: {ft['total_logs']}")
        print(f"    Total time:  {ft['total_ms']:.0f}ms")

    # Print presentation-ready numbers
    print(f"\n{color('═' * 60, 'green')}")
    print(f"  {color('🎤 SLIDE 6 — Copy-paste numbers:', 'bold')}")
    print(f"{color('═' * 60, 'green')}")

    if "feed" in results:
        avg_feed = safe_avg(results["feed"])
        p95_feed = safe_p95(results["feed"])
        below_300 = sum(1 for l in results["feed"] if l < 300) / len(results["feed"]) * 100
        print(f"  • Feed API Avg Latency:       {color(f'{avg_feed:.0f}ms', 'green')}")
        print(f"  • Feed API P95 Latency:       {color(f'{p95_feed:.0f}ms', 'green')}")
        print(f"  • Requests < 300ms:           {color(f'{below_300:.0f}%', 'green')}")

    if "behavior_log" in results:
        avg_bl = safe_avg(results["behavior_log"])
        throughput = 1000 / avg_bl if avg_bl > 0 else 0
        print(f"  • Behavior Log Avg Latency:   {color(f'{avg_bl:.0f}ms', 'green')}")
        print(f"  • Ingestion Throughput:        {color(f'~{throughput:.0f} logs/sec', 'green')}")

    if "fatigue" in results:
        ft = results["fatigue"]
        ft_total = ft["total_logs"]
        ft_state = ft["final_state"]
        print(f"  • Fatigue Detection:           {color(f'{ft_total} logs → {ft_state}', 'green')}")

    if "concurrent" in results:
        p95_conc = safe_p95(results["concurrent"])
        print(f"  • Concurrent P95 ({len(results['concurrent'])} req):  {color(f'{p95_conc:.0f}ms', 'green')}")

    print()


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="GoTouchGrass Benchmark Suite")
    parser.add_argument("--base-url", default="http://localhost:8033", help="Backend base URL")
    parser.add_argument("--runs", type=int, default=30, help="Number of iterations per benchmark")
    parser.add_argument("--concurrent", type=int, default=10, help="Concurrent requests for concurrency test")
    parser.add_argument("--skip-fatigue", action="store_true", help="Skip fatigue transition benchmark (slower)")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    results: Dict[str, Any] = {}

    print(f"\n{color('🌿 GoTouchGrass Benchmark Suite', 'bold')}")
    print(f"  Target: {base}")
    print(f"  Runs per benchmark: {args.runs}")
    print(f"  Concurrent test:    {args.concurrent} parallel requests")
    print(f"  Timestamp:          {datetime.now().isoformat()}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 0. Health check — verify server is up
        try:
            resp = await client.get(f"{base}/health")
            health = resp.json()
            print(f"\n  ✅ Server healthy: {health.get('database', 'unknown')} | embedding: {health.get('embedding_mode', '?')}")
        except Exception as e:
            print(f"\n  ❌ Server not reachable at {base}: {e}")
            print(f"     Make sure the backend is running (uvicorn app.main:app --port 8033)")
            sys.exit(1)

        # 1. Get test user & video
        user = await get_any_user(client, base)
        if not user:
            print("  ❌ No users found in database. Create a user first.")
            sys.exit(1)
        user_id = user.get("id") or str(user.get("_id"))
        print(f"  📌 Test user: {user.get('username', user_id)} ({user_id})")

        video = await get_any_video(client, base)
        if not video:
            print("  ❌ No videos found in database.")
            sys.exit(1)
        video_id = video.get("id") or str(video.get("_id"))
        print(f"  📌 Test video: {video.get('title', video_id)[:40]} ({video_id})")

        # Create a session for tests that need it
        _, sess = await timed_request(client, "POST", f"{base}{API_PREFIX}/sessions", json={"user_id": user_id})
        session_id = sess["id"]
        print(f"  📌 Test session: {session_id}")

        # ── Run Benchmarks ────────────────────────────────────
        results["feed"] = await bench_feed_latency(client, base, user_id, args.runs)

        results["behavior_log"] = await bench_behavior_log(
            client, base, user_id, session_id, video_id, args.runs
        )

        # End the temp session before session benchmark
        try:
            await timed_request(client, "PUT", f"{base}{API_PREFIX}/sessions/{session_id}/end")
        except Exception:
            pass

        results["session"] = await bench_session_ops(client, base, user_id, min(args.runs, 15))

        await bench_trending_vs_vector(client, base, user_id, args.runs)

        if not args.skip_fatigue:
            results["fatigue"] = await bench_fatigue_transition(client, base, user_id, video_id)

        results["concurrent"] = await bench_concurrent(client, base, user_id, args.concurrent)

        results["health"] = await bench_health_and_db(client, base, min(args.runs, 20))

    # ── Final Summary ─────────────────────────────────────────
    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
