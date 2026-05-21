import asyncio
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")

async def main():
    print("Initializing environment...")
    from app.utils.embedding import generate_embedding, generate_embeddings_batch, is_mock_mode
    from app.config import settings

    print(f"Configured embedding model: {settings.EMBEDDING_MODEL}")
    print(f"Configured dimensions: {settings.EMBEDDING_DIMENSIONS}")
    print(f"Mock mode active? {is_mock_mode()}")

    # Test single embedding
    text = "FastAPI web application for short video sharing and recommendations."
    print(f"\n--- Testing Single Embedding for: '{text}' ---")
    try:
        vector = await generate_embedding(text)
        print(f"Successfully generated embedding vector!")
        print(f"Vector type: {type(vector)}")
        print(f"Vector length: {len(vector)}")
        print(f"First 5 elements: {vector[:5]}")
        
        # Verify length matches dimensions
        if len(vector) != settings.EMBEDDING_DIMENSIONS:
            print(f"❌ ERROR: Expected dimension {settings.EMBEDDING_DIMENSIONS}, got {len(vector)}", file=sys.stderr)
            sys.exit(1)
        else:
            print("✅ Dimension check passed for single embedding!")
    except Exception as e:
        print(f"❌ ERROR generating single embedding: {e}", file=sys.stderr)
        sys.exit(1)

    # Test batch embedding
    texts = [
        "First text to embed in a batch",
        "Second text to embed in a batch",
        "Third text to embed in a batch"
    ]
    print("\n--- Testing Batch Embeddings ---")
    try:
        vectors = await generate_embeddings_batch(texts)
        print(f"Successfully generated batch embedding vectors!")
        print(f"Batch size: {len(vectors)}")
        for idx, vec in enumerate(vectors):
            print(f"Vector {idx + 1} length: {len(vec)}")
            if len(vec) != settings.EMBEDDING_DIMENSIONS:
                print(f"❌ ERROR: Batch index {idx} dimension mismatch", file=sys.stderr)
                sys.exit(1)
        print("✅ Dimension check passed for batch embeddings!")
    except Exception as e:
        print(f"❌ ERROR generating batch embeddings: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n🎉 Hugging Face embedding integration verification successful!")

if __name__ == "__main__":
    asyncio.run(main())
