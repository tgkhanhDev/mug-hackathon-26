import asyncio
from app.repositories.database import connect_db, get_database, disconnect_db
from app.utils.embedding import generate_embedding

async def test_vector_search():
    print("🔌 Connecting to MongoDB...")
    await connect_db()
    db = get_database()
    
    # 1. Check if we have videos in DB
    video_count = await db["videos"].count_documents({})
    print(f"📊 Current videos in database: {video_count}")
    
    if video_count == 0:
        print("⚠️ Warning: No videos found in the database. Please run crawl_pexels.py first to populate the database.")
        await disconnect_db()
        return

    # 2. Generate a real query vector using the configured Hugging Face model
    search_query = "nature and trees"
    print(f"🧠 Generating embedding for query text: '{search_query}'...")
    try:
        query_vector = await generate_embedding(search_query)
        dim = len(query_vector)
        print(f"✅ Generated vector with {dim} dimensions.")
    except Exception as e:
        print(f"❌ Failed to generate embedding: {e}")
        await disconnect_db()
        return

    # 3. Build and execute the $vectorSearch aggregation pipeline
    print("\n🚀 Executing $vectorSearch on Atlas...")
    pipeline = [
        {
            "$vectorSearch": {
                "index": "video_embedding_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": 10,
                "limit": 3
            }
        },
        {
            "$addFields": {
                "search_score": {"$meta": "vectorSearchScore"}
            }
        },
        {
            "$project": {
                "title": 1,
                "category": 1,
                "intensity_level": 1,
                "search_score": 1,
                "_id": 1
            }
        }
    ]

    try:
        results = []
        async for doc in db["videos"].aggregate(pipeline):
            results.append(doc)
            
        print(f"🎉 Success! Retrieved {len(results)} matches.")
        for idx, doc in enumerate(results):
            print(f"[{idx+1}] ID: {doc['_id']} | Title: '{doc.get('title')}'")
            print(f"    Category: {doc.get('category')} | Intensity: {doc.get('intensity_level')}")
            print(f"    Vector Similarity Score: {doc.get('search_score'):.4f}\n")
            
    except Exception as e:
        print("\n❌ Vector Search execution failed!")
        print(f"Error Message: {e}")
        print("\n💡 Trouble-shooting guide:")
        print("1. Did you create the Atlas Vector Search Index named 'video_embedding_index' on your cluster?")
        print("2. Is the index type set to 'vectorSearch'?")
        print("3. Did you set 'numDimensions' to 384 in the Atlas index config?")
        print("4. Check if the index building status on the MongoDB Atlas website has reached 'Active' status.")

    await disconnect_db()

if __name__ == "__main__":
    asyncio.run(test_vector_search())
