import os
import sys
import asyncio

# Add project root to python path to import app modules correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.database import connect_db, disconnect_db
from app.utils.classifier import heuristic_predict, predict_all_metadata, train_classifier, MODEL_PATH


async def test_classification_system():
    print("==================================================")
    print("🧪 TESTING CLASSIFICATION & FINE-TUNING SYSTEM 🧪")
    print("==================================================")

    # 1. Test Descriptions
    test_cases = [
        {
            "title": "Easy homemade pasta recipe",
            "desc": "Today we are cooking an amazing garlic butter cream pasta with grilled chicken. Perfect dinner recipe!",
            "expected_cat": "cooking",
            "expected_intensity": "medium"
        },
        {
            "title": "Valorant gameplay highlights RTX 4090",
            "desc": "Insane match showing custom keybinds, high sens gaming, and ultimate console streaming tips.",
            "expected_cat": "gaming",
            "expected_intensity": "high"
        },
        {
            "title": "10-Minute Morning Gym Workout",
            "desc": "Quick full-body fitness routine. Follow this exercise guidance to improve your run and athletic performance.",
            "expected_cat": "sports",
            "expected_intensity": "high"
        },
        {
            "title": "Deep Sleep Forest Rain Sounds",
            "desc": "Relaxing and calming ambient sounds for sleeping and studying. Natural meditation to quiet your mind.",
            "expected_cat": "calming",
            "expected_intensity": "low"
        },
        {
            "title": "Learn Python Programming from Scratch",
            "desc": "Complete tutorial explaining variables, loops, and object-oriented coding. Perfect lesson for beginners.",
            "expected_cat": "education",
            "expected_intensity": "medium"
        },
        {
            "title": "Hướng dẫn nấu lẩu thái chua cay tại nhà 🍲",
            "desc": "Hôm nay mình chia sẻ công thức nấu lẩu thái siêu ngon, nguyên liệu dễ tìm tại nhà, chuẩn vị nhà hàng ẩm thực.",
            "expected_cat": "cooking",
            "expected_intensity": "medium"
        },
        {
            "title": "Bai tap gym giam mo bung hieu qua tai nha",
            "desc": "Huong dan cac dong tac cardio va workout cuong do cao giup dot mo bung hieu qua. Tap luyen the thao hang ngay thoi nao!",
            "expected_cat": "sports",
            "expected_intensity": "high"
        },
        {
            "title": "Nhạc lofi thư giãn ngủ ngon đêm muộn 💤",
            "desc": "Tuyển tập những bài hát lofi chill giúp bạn ngủ ngon, giảm stress, tập trung học tập thiền định và chữa lành tâm hồn.",
            "expected_cat": "calming",
            "expected_intensity": "low"
        },
        {
            "title": "Daily vlog: Một ngày dọn dẹp phòng tối giản và skincare",
            "desc": "Cùng mình trang trí lại phòng ngủ phong cách tối giản, dọn dẹp nhà cửa, phối đồ đi cafe cuối tuần và skincare chăm sóc da nhé.",
            "expected_cat": "lifestyle",
            "expected_intensity": "medium"
        }
    ]

    print("\n--- 1. Testing Keyword Heuristics (Cold Start / No Model) ---")
    # Temporarily remove model file if it exists to test pure heuristics
    model_existed = os.path.exists(MODEL_PATH)
    temp_model_path = MODEL_PATH + ".tmp"
    if model_existed:
        print("💡 Temporarily hiding existing model file for heuristics testing...")
        os.rename(MODEL_PATH, temp_model_path)

    try:
        for idx, tc in enumerate(test_cases):
            cat, tags, intensity = await predict_all_metadata(tc["desc"], tc["title"])
            print(f"Test case #{idx+1}: '{tc['title']}'")
            print(f"  -> Predicted Category: {cat} (Expected: {tc['expected_cat']})")
            print(f"  -> Predicted Intensity: {intensity} (Expected: {tc['expected_intensity']})")
            print(f"  -> Predicted Tags: {tags}")
            print()
    finally:
        # Restore model if we renamed it
        if model_existed:
            os.rename(temp_model_path, MODEL_PATH)

    # 2. Connect to Database and Train/Fine-tune
    print("\n--- 2. Connecting to MongoDB Atlas & Training Model ---")
    await connect_db()

    try:
        stats = await train_classifier()
        print(f"📊 Training execution stats: {stats}")

        if not stats.get("success"):
            print("❌ Model training did not succeed. Checking if model file exists...")
        else:
            print("✅ Model trained and saved successfully.")

        # 3. Test Predictions with Fine-Tuned Model
        print("\n--- 3. Testing Predictions with Fine-Tuned Model ---")
        if os.path.exists(MODEL_PATH):
            for idx, tc in enumerate(test_cases):
                cat, tags, intensity = await predict_all_metadata(tc["desc"], tc["title"])
                print(f"Test case #{idx+1}: '{tc['title']}'")
                print(f"  -> ML Predicted Category: {cat}")
                print(f"  -> ML Predicted Intensity: {intensity}")
                print(f"  -> ML Predicted Tags: {tags}")
                print()
        else:
            print("⚠️ Skipping ML predictions testing: classification_model.pkl not found.")

    except Exception as e:
        print(f"❌ Error occurred during training test: {e}")
    finally:
        await disconnect_db()
        print("🔌 Database disconnected.")


if __name__ == "__main__":
    asyncio.run(test_classification_system())
