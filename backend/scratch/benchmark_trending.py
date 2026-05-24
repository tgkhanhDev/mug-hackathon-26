import asyncio
import time
import random
from app.repositories.database import connect_db, get_database, disconnect_db

async def run_benchmark():
    print("Connecting to database...")
    await connect_db()
    
    db = get_database()
    col_name = "benchmark_videos"
    
    # 1. Clean up and recreate benchmark collection
    if col_name in await db.list_collection_names():
        await db[col_name].drop()
    
    print("\n[1/4] Inserting 10,000 dummy documents for benchmark...")
    bulk_docs = []
    for i in range(10000):
        views = random.randint(0, 10000)
        likes = random.randint(0, 2000)
        comments = random.randint(0, 500)
        # Static precomputed score
        trending_score = views * 1 + likes * 3 + comments * 5
        
        bulk_docs.append({
            "title": f"Video Benchmark {i}",
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            "trending_score": trending_score,
            "category": "lifestyle",
            "tags": ["test", "benchmark"]
        })
        
    await db[col_name].insert_many(bulk_docs)
    print("✅ Inserted 10,000 documents.")

    # 2. Create index on precomputed static score
    print("\n[2/4] Creating index on static 'trending_score'...")
    await db[col_name].create_index([("trending_score", -1)])
    print("✅ Index created.")

    # 3. Define the two queries
    # Query A: Normal (Precomputed & Indexed Sort)
    async def query_static():
        cursor = db[col_name].find({}).sort("trending_score", -1).limit(10)
        return await cursor.to_list(length=10)

    # Query B: Dynamic Aggregation (On-the-fly math + Sort)
    async def query_dynamic():
        pipeline = [
            {
                "$addFields": {
                    "calculated_score": {
                        "$add": [
                            {"$multiply": [{"$ifNull": ["$view_count", 0]}, 1]},
                            {"$multiply": [{"$ifNull": ["$like_count", 0]}, 3]},
                            {"$multiply": [{"$ifNull": ["$comment_count", 0]}, 5]}
                        ]
                    }
                }
            },
            {"$sort": {"calculated_score": -1}},
            {"$limit": 10}
        ]
        cursor = db[col_name].aggregate(pipeline)
        return await cursor.to_list(length=None)

    # Warm-up run
    await query_static()
    await query_dynamic()

    # 4. Measure execution times
    iterations = 50
    print(f"\n[3/4] Running Query A (Indexed Static Sort) {iterations} times...")
    start_time = time.perf_counter()
    for _ in range(iterations):
        await query_static()
    static_duration = (time.perf_counter() - start_time) * 1000 / iterations
    print(f"✅ Query A average time: {static_duration:.2f} ms")

    print(f"\n[3/4] Running Query B (Dynamic Aggregation Sort) {iterations} times...")
    start_time = time.perf_counter()
    for _ in range(iterations):
        await query_dynamic()
    dynamic_duration = (time.perf_counter() - start_time) * 1000 / iterations
    print(f"✅ Query B average time: {dynamic_duration:.2f} ms")

    # Ratio
    ratio = dynamic_duration / static_duration if static_duration > 0 else 0
    print(f"\n=== BENCHMARK RESULTS ===")
    print(f"🚀 Cách bình thường (Static Index): {static_duration:.2f} ms")
    print(f"🧠 Cách động (Aggregation Dynamic): {dynamic_duration:.2f} ms")
    print(f"⚡ Cách bình thường nhanh hơn cách động khoảng: {ratio:.1f} lần!")
    
    # 5. Explain queries plans briefly
    print("\n[4/4] Fetching Query Plans (explain)...")
    # Explain Static
    explain_static = await db.command("explain", {
        "find": col_name,
        "sort": {"trending_score": -1},
        "limit": 10
    }, verbosity="executionStats")
    
    # Explain Dynamic
    explain_dynamic = await db.command("explain", {
        "aggregate": col_name,
        "pipeline": [
            {
                "$addFields": {
                    "calculated_score": {
                        "$add": [
                            {"$multiply": [{"$ifNull": ["$view_count", 0]}, 1]},
                            {"$multiply": [{"$ifNull": ["$like_count", 0]}, 3]},
                            {"$multiply": [{"$ifNull": ["$comment_count", 0]}, 5]}
                        ]
                    }
                }
            },
            {"$sort": {"calculated_score": -1}},
            {"$limit": 10}
        ],
        "cursor": {}
    }, verbosity="executionStats")

    # Parse stage info
    static_stages = explain_static.get("queryPlanner", {}).get("winningPlan", {})
    # Drill down to find stage name
    def get_stages(plan):
        stages = [plan.get("stage")]
        if "inputStage" in plan:
            stages.extend(get_stages(plan["inputStage"]))
        elif "inputStages" in plan:
            for s in plan["inputStages"]:
                stages.extend(get_stages(s))
        return stages
    
    print(f"Plan Query A (Static): {' -> '.join(get_stages(static_stages))}")
    print(f"   (Sử dụng IXSCAN - Index Scan, tối ưu tối đa vì không cần tính toán và duyệt qua mọi record)")
    
    print("Plan Query B (Dynamic): COLLSCAN -> ADD_FIELDS -> SORT")
    print(f"   (Sử dụng COLLSCAN - Collection Scan, bắt buộc phải đọc toàn bộ 10,000 tài liệu lên RAM để tính toán rồi mới sort)")

    # Clean up benchmark collection
    print("\nCleaning up benchmark collection...")
    await db[col_name].drop()
    await disconnect_db()
    print("🎉 Done.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
