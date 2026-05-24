"""
Video classification module.
Contains keyword-based heuristics (fallback) and ML-based (TF-IDF + LogisticRegression)
fine-tuning logic for predicting category and tags based on video description.
"""

import os
import re
import pickle
import logging
from typing import List, Tuple, Dict, Any, Optional

from app.models.video import CATEGORY_ENUM

logger = logging.getLogger(__name__)

# Constants for model persistence
MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "classification_model.pkl")

# Helper to remove Vietnamese diacritics
def remove_vietnamese_diacritics(text: str) -> str:
    """
    Remove diacritics from Vietnamese characters, converting them to their ASCII equivalents.
    Useful for matching accentless words in search queries or descriptions.
    """
    patterns = {
        '[aăâàằầáắấảẳẩãẵẫạặậ]': 'a',
        '[AĂÂÀẰẦÁẮẤẢẲẨÃẴẪẠẶẬ]': 'A',
        '[dđ]': 'd',
        '[DĐ]': 'D',
        '[eêèềéếẻểẽễẹệ]': 'e',
        '[EÊÈỀÉẾẺỂẼỄẸỆ]': 'E',
        '[iìíỉĩị]': 'i',
        '[IÌÍỈĨỊ]': 'I',
        '[oôơòồờóốớỏổởõỗỡọộợ]': 'o',
        '[OÔƠÒỒỜÓỐỚỎỔỞÕỖỠỌỘỢ]': 'O',
        '[uưùừúứủửũữụự]': 'u',
        '[UƯÙỪÚỨỦỬŨỮỤỰ]': 'U',
        '[yỳýỷỹỵ]': 'y',
        '[YỲÝỶỸỴ]': 'Y'
    }
    res = text
    for regex, replacement in patterns.items():
        res = re.sub(regex, replacement, res)
    return res

# Heuristic category mapping keywords (English, Vietnamese accented & unaccented)
CATEGORY_KEYWORDS = {
    "cooking": [
        # English
        "cook", "recipe", "food", "kitchen", "chef", "bake", "delicious", "eat",
        "meal", "dinner", "lunch", "breakfast", "cake", "dessert", "baking", "grill",
        "fry", "sauce", "taste", "yummy", "culinary", "gastronomy", "restaurant",
        "dish", "ingredient", "spices", "gourmet", "cuisine", "mukbang", "cookware",
        # Vietnamese Accented
        "nấu ăn", "nấu", "ẩm thực", "làm bánh", "công thức", "ngon", "nhà bếp", "bếp",
        "bữa ăn", "bữa tối", "ăn uống", "món ăn", "món", "nướng", "chiên", "lẩu",
        "xào", "nước sốt", "bánh ngọt", "đầu bếp", "hướng dẫn nấu", "gia vị",
        "nguyên liệu", "ăn vặt", "thực đơn", "chế biến", "nội trợ", "nước dùng",
        # Vietnamese Unaccented
        "nau an", "nau", "am thuc", "lam banh", "cong thuc", "nha bep", "bep",
        "bua an", "bua toi", "an uong", "mon an", "mon", "nuong", "chien", "lau",
        "xao", "nuoc sot", "banh ngot", "dau bep", "huong dan nau", "gia vi",
        "nguyen lieu", "an vat", "thuc don", "che bien", "noi tro", "nuoc dung"
    ],
    "gaming": [
        # English
        "game", "gaming", "gameplay", "gamer", "playstation", "xbox", "nintendo",
        "pc gaming", "streamer", "live stream", "console", "esports", "fps", "rpg",
        "mmo", "valorant", "minecraft", "fortnite", "pubg", "csgo", "dota", "twitch",
        "steam", "rtx", "graphics", "controller", "keyboard", "mouse", "headset",
        "speedrun", "modding", "nvidia", "gta", "gta6", "gta5", "gta v", "playthrough", "co-op", "multiplayer",
        # Vietnamese Accented
        "chơi game", "game thủ", "phát trực tiếp", "đồ họa", "máy chơi game", "giải đấu",
        "đấu giải", "tay cầm", "bàn phím", "chuột chơi game", "tai nghe", "trận đấu game",
        "phòng máy", "nét", "stream game", "cày cuốc", "chơi", "trò chơi", "tựa game",
        # Vietnamese Unaccented
        "choi game", "game thu", "phat truc tiep", "do hoa", "may choi game", "giai dau",
        "dau giai", "tay cam", "ban phim", "chuot choi game", "tai nghe", "tran dau game",
        "phong may", "net", "stream game", "cay cuoc", "choi", "tro choi", "tua game"
    ],
    "sports": [
        # English
        "sports", "sport", "gym", "workout", "fitness", "exercise", "run", "running",
        "marathon", "football", "soccer", "basketball", "tennis", "badminton", "volleyball",
        "athlete", "training", "coach", "championship", "match", "stadium", "cup",
        "tournament", "cardio", "yoga", "bodybuilding", "weightlifting", "healthy", "active",
        "swimming", "cycling", "workout routine", "calisthenics", "stretching", "pilates",
        # Vietnamese Accented
        "thể thao", "chạy bộ", "đá bóng", "bóng đá", "cầu lông", "quần vợt", "bóng rổ",
        "thể hình", "giảm cân", "tập luyện", "vận động viên", "huấn luyện viên", "trận đấu",
        "giải đấu", "tập gym", "thể dục", "bơi lội", "đạp xe", "bóng bàn", "võ thuật",
        "leo núi", "vận động", "cơ bắp", "giảm mỡ",
        # Vietnamese Unaccented
        "the thao", "chay bo", "da bong", "bong da", "cau long", "quan vot", "bong ro",
        "the hinh", "giam can", "tap luyen", "van dong vien", "huan luyen vien", "tran dau",
        "giai dau", "tap gym", "the duc", "boi loi", "dap xe", "bong ban", "vo thuat",
        "leo nui", "van dong", "co bap", "giam mo"
    ],
    "calming": [
        # English
        "calm", "calming", "relax", "relaxing", "sleep", "sleeping", "meditation", "meditate",
        "peaceful", "ambient", "soft", "lofi", "study", "quiet", "breathe", "breathing",
        "spa", "soothe", "soothing", "healing", "chill", "relaxing sound", "white noise",
        "rain sound", "waves", "zen", "stress relief", "cozy", "satisfying", "whisper",
        "asmr", "slomo", "slow motion", "peace", "therapeutic", "mindfulness", "deep sleep",
        # Vietnamese Accented
        "thư giãn", "ngủ ngon", "thiền", "yên bình", "êm dịu", "nhẹ nhàng", "tĩnh lặng",
        "chữa lành", "tiếng mưa", "nhạc lofi", "giảm stress", "thanh tịnh", "bình yên",
        "dễ chịu", "âm thanh thiên nhiên", "tiếng sóng", "ấm cúng", "thư thái", "mưa rơi",
        # Vietnamese Unaccented
        "thu gian", "ngu ngon", "thien", "yen binh", "em diu", "nhe nhang", "tinh lang",
        "chua lanh", "tieng mua", "nhac lofi", "giam stress", "thanh tinh", "binh yen",
        "de chiu", "am thanh thien nhien", "tieng song", "am cung", "thu thai", "mua roi"
    ],
    "nature": [
        # English
        "nature", "natural", "forest", "mountain", "river", "sea", "ocean", "lake",
        "beach", "rain", "storm", "landscape", "scenery", "wildlife", "animal", "animals",
        "birds", "tree", "trees", "plants", "flowers", "outdoor", "outdoors", "sky",
        "cloud", "clouds", "sun", "sunrise", "sunset", "jungle", "waterfall", "scenic",
        "greenery", "volcano", "island", "wilderness", "pet", "pets", "safari",
        # Vietnamese Accented
        "thiên nhiên", "rừng", "núi", "sông", "biển", "hồ", "mưa", "bão", "phong cảnh",
        "cảnh đẹp", "động vật", "thú hoang", "chim", "cây cối", "cây", "hoa", "ngoài trời",
        "bầu trời", "mây", "mặt trời", "hoàng hôn", "bình minh", "thác nước", "đảo",
        "rừng rậm", "thú cưng", "chó mèo", "hoa lá",
        # Vietnamese Unaccented
        "thien nhien", "rung", "nui", "song", "bien", "ho", "mua", "bao", "phong canh",
        "canh dep", "dong vat", "thu hoang", "chim", "cay coi", "cay", "hoa", "ngoai troi",
        "bau troi", "may", "mat troi", "hoang hon", "binh minh", "thac nuoc", "dao",
        "rung ram", "thu cung", "cho meo", "hoa la"
    ],
    "education": [
        # English
        "education", "learn", "learning", "tutorial", "guide", "how to", "course", "lesson",
        "study", "studying", "teach", "teacher", "school", "university", "explain",
        "explaining", "science", "history", "math", "mathematics", "physics", "chemistry",
        "biology", "coding", "programming", "developer", "python", "javascript", "ai",
        "machine learning", "technology", "knowledge", "facts", "docu", "documentary",
        "hacks", "tips", "tricks", "webinar", "lecture", "academy", "research",
        # Vietnamese Accented
        "giáo dục", "học tập", "học", "hướng dẫn", "bài học", "giảng dạy", "giáo viên",
        "trường học", "giải thích", "khoa học", "lịch sử", "toán học", "toán", "vật lý",
        "hóa học", "sinh học", "lập trình", "phát triển phần mềm", "công nghệ", "kiến thức",
        "sự thật", "phim tài liệu", "mẹo", "bí quyết", "nghiên cứu", "bài giảng", "chia sẻ kiến thức",
        # Vietnamese Unaccented
        "giao duc", "hoc tap", "hoc", "huong dan", "bai hoc", "giang day", "giao vien",
        "truong hoc", "giai thich", "khoa hoc", "lich su", "toan hoc", "toan", "vat ly",
        "hoa hoc", "sinh hoc", "lap trinh", "phat trien phan mem", "cong nghe", "kien thuc",
        "su that", "phim tai lieu", "meo", "bi quyet", "nghien cuu", "bai giang", "chia se kien thuc"
    ],
    "entertainment": [
        # English
        "entertainment", "funny", "meme", "memes", "comedy", "comedian", "joke", "jokes",
        "prank", "pranks", "humor", "hilarious", "lol", "laugh", "laughing", "movie",
        "movies", "film", "cinema", "theatre", "music", "song", "songs", "dance",
        "dancing", "dancer", "challenge", "challenges", "show", "parody", "reaction",
        "tiktok trend", "singer", "concert", "drama", "anime", "cartoon", "fun",
        # Vietnamese Accented
        "giải trí", "hài hước", "hài", "ảnh chế", "trò đùa", "tếu táo", "cười", "phim",
        "phim ảnh", "rạp phim", "âm nhạc", "nhạc", "ca khúc", "bài hát", "nhảy", "múa",
        "thử thách", "parody", "phản ứng", "trào lưu", "ca sĩ", "hòa nhạc", "kịch", "hoạt hình",
        "vui nhộn", "giải trí tổng hợp",
        # Vietnamese Unaccented
        "giai tri", "hai huoc", "hai", "anh che", "tro dua", "teu tao", "cuoi", "phim",
        "phim anh", "rap phim", "am nhac", "nhac", "ca khuc", "bai hat", "nhay", "mua",
        "thu thach", "parody", "phan ung", "trao luu", "ca si", "hoa nhac", "kich", "hoat hinh",
        "vui nhon", "giai tri tong hop"
    ],
    "lifestyle": [
        # English
        "lifestyle", "vlog", "routine", "minimalism", "minimalist", "travel", "traveling",
        "aesthetic", "daily", "life", "home", "decor", "shopping", "haul", "fashion",
        "outfit", "ootd", "grwm", "morning routine", "night routine", "skincare", "makeup",
        "organizing", "cleaning", "apartment tour", "beauty", "personal care", "hobby",
        "hobbies", "cafe", "coffee", "restaurant review", "outdoors vlog", "travel vlog",
        # Vietnamese Accented
        "phong cách sống", "cuộc sống", "vlog", "hằng ngày", "thói quen", "tối giản",
        "du lịch", "phượt", "đi chơi", "thẩm mỹ", "nhà cửa", "trang trí", "mua sắm",
        "thời trang", "phối đồ", "dọn dẹp", "chăm sóc da", "trang điểm", "làm đẹp",
        "quán cà phê", "review ăn uống", "nhật ký cuộc sống", "phong cach",
        # Vietnamese Unaccented
        "phong cach song", "cuoc song", "hang ngay", "thoi quen", "toi gian", "du lich",
        "phuot", "di choi", "tham my", "nha cua", "trang tri", "mua sam", "thoi trang",
        "phoi do", "don dep", "cham soc da", "trang diem", "lam dep", "quan ca phe",
        "review an uong", "nhat ky cuoc song"
    ]
}

# Default fallback tags by category
CATEGORY_DEFAULT_TAGS = {
    "cooking": ["cooking", "food", "recipe", "delicious", "kitchen", "yummy"],
    "gaming": ["gaming", "gameplay", "gamer", "play", "games", "stream"],
    "sports": ["sports", "fitness", "workout", "gym", "training", "exercise"],
    "calming": ["calming", "relaxing", "peaceful", "lofi", "chill", "meditation"],
    "nature": ["nature", "travel", "outdoors", "beautiful", "scenery", "landscape"],
    "education": ["education", "learning", "tutorial", "knowledge", "science", "guide"],
    "entertainment": ["entertainment", "funny", "music", "video", "meme", "comedy"],
    "lifestyle": ["lifestyle", "vlog", "aesthetic", "daily", "routine", "travel"]
}

# Stopwords for filtering tokens during heuristic tag extraction
STOP_WORDS = {
    "the", "a", "and", "of", "in", "to", "is", "for", "with", "on", "at", "by", "an", "this", "that", "it",
    "và", "của", "là", "trong", "cho", "với", "tại", "bởi", "này", "đó", "nó", "các", "những", "một", "hai",
    "được", "bị", "đã", "đang", "sẽ", "cũng", "như", "nhưng", "hoặc", "nếu", "thì", "vì", "nên", "cho nên",
    "nau", "lam", "choi", "chay", "tap", "tieng", "canh", "giao", "bai", "phim", "cuoc", "thoi"
}

# Map Vietnamese keywords to English tags
VN_TO_EN_KEYWORDS = {
    # cooking
    "nấu ăn": "cooking", "nấu": "cook", "ẩm thực": "cuisine", "làm bánh": "baking", "công thức": "recipe",
    "ngon": "delicious", "nhà bếp": "kitchen", "bếp": "kitchen", "bữa ăn": "meal", "bữa tối": "dinner",
    "ăn uống": "eating", "món ăn": "dish", "món": "dish", "nướng": "grill", "chiên": "fry", "lẩu": "hotpot",
    "xào": "stir-fry", "nước sốt": "sauce", "bánh ngọt": "cake", "đầu bếp": "chef", "hướng dẫn nấu": "recipe",
    "gia vị": "spices", "nguyên liệu": "ingredient", "ăn vặt": "snack", "thực đơn": "menu", "chế biến": "cooking",
    "nội trợ": "cooking", "nước dùng": "broth",
    "nau an": "cooking", "nau": "cook", "am thuc": "cuisine", "lam banh": "baking", "cong thuc": "recipe",
    "nha bep": "kitchen", "bep": "kitchen", "bua an": "meal", "bua toi": "dinner", "an uong": "eating",
    "mon an": "dish", "mon": "dish", "nuong": "grill", "chien": "fry", "lau": "hotpot", "xao": "stir-fry",
    "nuoc sot": "sauce", "banh ngot": "cake", "dau bep": "chef", "huong dan nau": "recipe", "gia vi": "spices",
    "nguyen lieu": "ingredient", "an vat": "snack", "thuc don": "menu", "che bien": "cooking", "noi tro": "cooking",
    "nuoc dung": "broth",

    # gaming
    "chơi game": "gaming", "game thủ": "gamer", "phát trực tiếp": "stream", "đồ họa": "graphics",
    "máy chơi game": "console", "giải đấu": "tournament", "đấu giải": "tournament", "tay cầm": "controller",
    "bàn phím": "keyboard", "chuột chơi game": "mouse", "tai nghe": "headset", "trận đấu game": "match",
    "phòng máy": "pc", "nét": "pc", "stream game": "stream", "cày cuốc": "gamer", "chơi": "play",
    "trò chơi": "game", "tựa game": "game",
    "choi game": "gaming", "game thu": "gamer", "phat truc tiep": "stream", "do hoa": "graphics",
    "may choi game": "console", "giai dau": "tournament", "dau giai": "tournament", "tay cam": "controller",
    "ban phim": "keyboard", "chuot choi game": "mouse", "tran dau game": "match", "phong may": "pc",
    "net": "pc", "cay cuoc": "gamer", "choi": "play", "tro choi": "game", "tua game": "game",

    # sports
    "thể thao": "sports", "chạy bộ": "running", "đá bóng": "soccer", "bóng đá": "soccer", "cầu lông": "badminton",
    "quần vợt": "tennis", "bóng rổ": "basketball", "thể hình": "gym", "giảm cân": "weightloss",
    "tập luyện": "workout", "vận động viên": "athlete", "huấn luyện viên": "coach", "trận đấu": "match",
    "giải đấu": "tournament", "tập gym": "gym", "thể dục": "fitness", "bơi lội": "swimming",
    "đạp xe": "cycling", "bóng bàn": "pingpong", "võ thuật": "martialarts", "leo núi": "climbing",
    "vận động": "workout", "cơ bắp": "muscle", "giảm mỡ": "fitness",
    "the thao": "sports", "chay bo": "running", "da bong": "soccer", "bong da": "soccer", "cau long": "badminton",
    "quan vot": "tennis", "bong ro": "basketball", "the hinh": "gym", "giam can": "weightloss",
    "tap luyen": "workout", "van dong vien": "athlete", "huan luyen vien": "coach", "tran dau": "match",
    "giai dau": "tournament", "tap gym": "gym", "the duc": "fitness", "boi loi": "swimming",
    "dap xe": "cycling", "bong ban": "pingpong", "vo thuat": "martialarts", "leo nui": "climbing",
    "van dong": "workout", "co bap": "muscle", "giam mo": "fitness",

    # calming
    "thư giãn": "relax", "ngủ ngon": "sleep", "thiền": "meditation", "yên bình": "peaceful",
    "êm dịu": "soothing", "nhẹ nhàng": "soft", "tĩnh lặng": "quiet", "chữa lành": "healing",
    "tiếng mưa": "rain", "nhạc lofi": "lofi", "giảm stress": "chill", "thanh tịnh": "zen",
    "bình yên": "peaceful", "dễ chịu": "cozy", "âm thanh thiên nhiên": "nature", "tiếng sóng": "waves",
    "ấm cúng": "cozy", "thư thái": "relax", "mưa rơi": "rain",
    "thu gian": "relax", "ngu ngon": "sleep", "thien": "meditation", "yen binh": "peaceful",
    "em diu": "soothing", "nhe nhang": "soft", "tinh lang": "quiet", "chua lanh": "healing",
    "tieng mua": "rain", "nhac lofi": "lofi", "giam stress": "chill", "thanh tinh": "zen",
    "binh yen": "peaceful", "de chiu": "cozy", "am thanh thien nhien": "nature", "tieng song": "waves",
    "am cung": "cozy", "thu thai": "relax", "mua roi": "rain",

    # nature
    "thiên nhiên": "nature", "rừng": "forest", "núi": "mountain", "sông": "river", "biển": "sea",
    "hồ": "lake", "mưa": "rain", "bão": "storm", "phong cảnh": "landscape", "cảnh đẹp": "scenery",
    "động vật": "animal", "thú hoang": "wildlife", "chim": "birds", "cây cối": "trees", "cây": "tree",
    "hoa": "flowers", "ngoài trời": "outdoors", "bầu trời": "sky", "mây": "clouds", "mặt trời": "sun",
    "hoàng hôn": "sunset", "bình minh": "sunrise", "thác nước": "waterfall", "đảo": "island",
    "rừng rậm": "jungle", "thú cưng": "pets", "chó mèo": "pets", "hoa lá": "flowers",
    "thien nhien": "nature", "rung": "forest", "nui": "mountain", "song": "river", "bien": "sea",
    "ho": "lake", "mua": "rain", "bao": "storm", "phong canh": "landscape", "canh dep": "scenery",
    "dong vat": "animal", "thu hoang": "wildlife", "cay coi": "trees", "cay": "tree",
    "ngoai troi": "outdoors", "bau troi": "sky", "may": "clouds", "mat troi": "sun",
    "hoang hon": "sunset", "binh minh": "sunrise", "thac nuoc": "waterfall", "dao": "island",
    "rung ram": "jungle", "thu cung": "pets", "cho meo": "pets", "hoa la": "flowers",

    # education
    "giáo dục": "education", "học tập": "learning", "học": "learn", "hướng dẫn": "guide",
    "bài học": "lesson", "giảng dạy": "teaching", "giáo viên": "teacher", "trường học": "school",
    "giải thích": "explain", "khoa học": "science", "lịch sử": "history", "toán học": "math",
    "toán": "math", "vật lý": "physics", "hóa học": "chemistry", "sinh học": "biology",
    "lập trình": "programming", "phát triển phần mềm": "developer", "công nghệ": "technology",
    "kiến thức": "knowledge", "sự thật": "facts", "phim tài liệu": "documentary", "mẹo": "tips",
    "bí quyết": "tricks", "nghiên cứu": "research", "bài giảng": "lecture", "chia sẻ kiến thức": "knowledge",
    "giao duc": "education", "hoc tap": "learning", "hoc": "learn", "huong dan": "guide",
    "bai hoc": "lesson", "giang day": "teaching", "giao vien": "teacher", "truong hoc": "school",
    "giai thich": "explain", "khoa hoc": "science", "lich su": "history", "toan hoc": "math",
    "toan": "math", "vat ly": "physics", "hoa hoc": "chemistry", "sinh hoc": "biology",
    "lap trinh": "programming", "phat trien phan mem": "developer", "cong nghe": "technology",
    "kien thuc": "knowledge", "su that": "facts", "phim tai lieu": "documentary", "meo": "tips",
    "bi quyet": "tricks", "nghien cuu": "research", "bai giang": "lecture", "chia se kien thuc": "knowledge",

    # entertainment
    "giải trí": "entertainment", "hài hước": "funny", "hài": "comedy", "ảnh chế": "meme",
    "trò đùa": "prank", "tếu táo": "humor", "cười": "laugh", "phim": "movie", "phim ảnh": "movie",
    "rạp phim": "cinema", "âm nhạc": "music", "nhạc": "music", "ca khúc": "song", "bài hát": "song",
    "nhảy": "dance", "múa": "dance", "thử thách": "challenge", "parody": "parody", "phản ứng": "reaction",
    "trào lưu": "trend", "ca sĩ": "singer", "hòa nhạc": "concert", "kịch": "drama", "hoạt hình": "cartoon",
    "vui nhộn": "fun", "giải trí tổng hợp": "entertainment",
    "giai tri": "entertainment", "hai huoc": "funny", "hai": "comedy", "anh che": "meme",
    "tro dua": "prank", "teu tao": "humor", "cuoi": "laugh", "phim anh": "movie",
    "rap phim": "cinema", "am nhac": "music", "nhac": "music", "ca khuc": "song", "bai hat": "song",
    "nhay": "dance", "mua": "dance", "thu thach": "challenge", "phan ung": "reaction",
    "trao luu": "trend", "ca si": "singer", "hoa nhac": "concert", "kich": "drama", "hoat hinh": "cartoon",
    "vui nhon": "fun", "giai tri tong hop": "entertainment",

    # lifestyle
    "phong cách sống": "lifestyle", "cuộc sống": "life", "vlog": "vlog", "hằng ngày": "daily",
    "thói quen": "routine", "tối giản": "minimalism", "du lịch": "travel", "phượt": "travel",
    "đi chơi": "travel", "thẩm mỹ": "aesthetic", "nhà cửa": "home", "trang trí": "decor",
    "mua sắm": "shopping", "thời trang": "fashion", "phối đồ": "fashion", "dọn dẹp": "cleaning",
    "chăm sóc da": "skincare", "trang điểm": "makeup", "làm đẹp": "beauty", "quán cà phê": "cafe",
    "review ăn uống": "review", "nhật ký cuộc sống": "vlog", "phong cach": "style",
    "phong cach song": "lifestyle", "cuoc song": "life", "hang ngay": "daily", "thoi quen": "routine",
    "toi gian": "minimalism", "du lich": "travel", "phuot": "travel", "di choi": "travel",
    "tham my": "aesthetic", "nha cua": "home", "trang tri": "decor", "mua sam": "shopping",
    "thoi trang": "fashion", "phoi do": "fashion", "don dep": "cleaning", "cham soc da": "skincare",
    "trang diem": "makeup", "lam dep": "beauty", "quan ca phe": "cafe", "review an uong": "review",
    "nhat ky cuoc song": "vlog"
}

# Blacklist of common Vietnamese unaccented words to exclude during custom tag extraction
COMMON_VN_WORDS = {
    # Pronouns, prepositions, conjunctions
    "toi", "ban", "tao", "to", "cau", "minh", "chung", "ta", "ho", "anh", "chi", "em", "ong", "ba", "co", "chu", "bac", "di",
    "con", "cai", "chiec", "nguoi", "nha", "cua", "trong", "ngoai", "tren", "duoi", "truoc", "sau", "giua", "ben", "phai", "trai",
    "nay", "kia", "do", "ay", "gi", "nao", "sao", "dau", "the", "nho", "lon", "cu", "moi", "tot", "xau", "dung", "sai",
    "khoe", "yeu", "vui", "buon", "gian", "so", "ghet", "can", "co", "khong", "la", "va", "nhu", "nhung", "hoac", "nhieu",
    "it", "qua", "lam", "rat", "kha", "hoi", "chua", "roi", "se", "dang", "da", "di", "ve", "den", "o", "cho", "voi",
    "tai", "boi", "vi", "nen", "ma", "thi", "cac", "mot", "hai", "ba", "bon", "nam", "sau", "bay", "tam", "chin", "muoi",
    # Common words in descriptions
    "cung", "chia", "se", "huong", "dan", "giao", "duc", "bai", "giang", "hoc", "tap", "chay", "bo", "da", "bong", "cau",
    "long", "quan", "vot", "ro", "boi", "loi", "dap", "xe", "vo", "thuat", "leo", "nui", "luyen", "van", "dong", "vien",
    "huan", "tran", "dau", "giai", "the", "duc", "nau", "an", "am", "thuc", "banh", "cong", "ngon", "bep", "bua", "toi",
    "mon", "nuong", "chien", "lau", "xao", "nuoc", "sot", "ngot", "gia", "vi", "nguyen", "lieu", "vat", "don", "noi",
    "tro", "dung", "thu", "gian", "ngu", "thien", "yen", "binh", "em", "diu", "nhe", "nhang", "tinh", "lang", "chua",
    "lanh", "tieng", "mua", "lofi", "nhac", "stress", "thanh", "de", "chiu", "song", "am", "cung", "thai", "roi", "rung",
    "bien", "ho", "bao", "phong", "canh", "dep", "hoang", "chim", "coi", "cay", "hoa", "ngoai", "troi", "bau", "may",
    "mat", "sunset", "thac", "dao", "ram", "cho", "meo", "la", "truong", "thich", "khoa", "lich", "su", "toan", "ly",
    "sinh", "lap", "trinh", "phat", "trien", "phan", "mem", "nghe", "kien", "su", "that", "meo", "bi", "quyet",
    "nghien", "cuu", "tri", "hai", "huoc", "che", "dua", "teu", "tao", "cuoi", "anh", "rap", "ca", "khuc", "hat",
    "nhay", "mua", "thach", "phan", "ung", "trao", "luu", "si", "concert", "kich", "hoat", "hinh", "tong", "hop",
    "cuoc", "hang", "ngay", "thoi", "quen", "toi", "gian", "du", "phuot", "sam", "trang", "diem", "don", "dep",
    "cham", "soc", "review", "phe", "nhat", "ky", "cam", "nhan", "cua", "tui", "minh", "hinh", "quay", "dung",
    "phim", "vlog", "clip", "kenh", "dang", "ky", "theo", "doi", "cam", "on", "moi", "nguoi", "chuc", "buoi",
    "sang", "chieu", "toi", "vui", "ve", "hanh", "phuc", "khoe", "manh", "binh", "an", "mong", "giup", "do",
    "ung", "ho", "like", "share", "sub", "kenh", "cua", "minh", "nhe", "nha", "luon", "luon", "yeu", "thuong",
    "tac", "cuong", "cao", "dot", "bung", "hieu", "giam", "thao", "can", "thich"
}


def clean_and_translate_tag(tag: str) -> Optional[str]:
    """
    Cleans a tag, translates it from Vietnamese to English if mapped,
    and returns the English tag, or None if it is a Vietnamese/invalid word.
    """
    t_clean = tag.strip().lower()
    
    # 1. Translate directly if in translation map
    if t_clean in VN_TO_EN_KEYWORDS:
        return VN_TO_EN_KEYWORDS[t_clean]
    
    # 2. Check if we remove accents, is it in translation map?
    t_no_accent = remove_vietnamese_diacritics(t_clean)
    if t_no_accent in VN_TO_EN_KEYWORDS:
        return VN_TO_EN_KEYWORDS[t_no_accent]
        
    # 3. If it's a common VN word (accented or unaccented), filter it out
    if t_clean in COMMON_VN_WORDS or t_no_accent in COMMON_VN_WORDS:
        return None
        
    # 4. If it's in STOP_WORDS, filter it out
    if t_clean in STOP_WORDS or t_no_accent in STOP_WORDS:
        return None
        
    # 5. If it's not ASCII, it must contain Vietnamese diacritics.
    # Since we couldn't translate it, we must discard it to prevent Vietnamese tags.
    if not t_clean.isascii():
        return None
        
    return t_clean


async def query_hf_zero_shot(text: str, candidate_labels: List[str]) -> Optional[str]:
    """
    Call Hugging Face Zero-Shot Classification API using mDeBERTa.
    Returns the predicted category with the highest score, or None if it fails.
    """
    import httpx
    import asyncio
    from app.config import settings

    if not settings.HF_API_TOKEN:
        logger.debug("No Hugging Face token configured. Skipping zero-shot API.")
        return None

    model = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
    api_url = f"https://router.huggingface.co/hf-inference/models/{model}/pipeline/zero-shot-classification"
    
    headers = {
        "Authorization": f"Bearer {settings.HF_API_TOKEN}"
    }
    
    payload = {
        "inputs": text,
        "parameters": {
            "candidate_labels": candidate_labels
        }
    }
    
    retries = 3
    delay = 3.0
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(retries):
                logger.debug(f"Querying HF zero-shot classification API (attempt {attempt + 1}/{retries})...")
                response = await client.post(api_url, headers=headers, json=payload)
                
                if response.status_code == 503:
                    try:
                        data = response.json()
                        estimated_time = data.get("estimated_time", delay)
                        wait_time = min(estimated_time, 10.0)
                    except Exception:
                        wait_time = delay
                    logger.info(f"🤗 HF Zero-Shot model is loading. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                if response.status_code != 200:
                    logger.warning(f"HF Zero-Shot API returned status {response.status_code}: {response.text}")
                    return None
                
                result = response.json()
                
                # Check for list format first
                if isinstance(result, list) and len(result) > 0:
                    first_item = result[0]
                    # Format A: list of {"label": "...", "score": ...}
                    if isinstance(first_item, dict) and "label" in first_item:
                        best_label = first_item["label"]
                        score = first_item.get("score", 0.0)
                        logger.info(f"🤗 HF Zero-Shot predicted category: {best_label} (score: {score:.4f})")
                        return best_label
                    
                    # Format B: list containing a dict with "labels"
                    if isinstance(first_item, dict) and "labels" in first_item and len(first_item["labels"]) > 0:
                        best_label = first_item["labels"][0]
                        score = first_item["scores"][0] if "scores" in first_item and len(first_item["scores"]) > 0 else 0.0
                        logger.info(f"🤗 HF Zero-Shot predicted category: {best_label} (score: {score:.4f})")
                        return best_label

                # Format B (non-list): dict containing "labels"
                if isinstance(result, dict) and "labels" in result and len(result["labels"]) > 0:
                    best_label = result["labels"][0]
                    score = result["scores"][0] if "scores" in result and len(result["scores"]) > 0 else 0.0
                    logger.info(f"🤗 HF Zero-Shot predicted category: {best_label} (score: {score:.4f})")
                    return best_label
                
                logger.warning(f"Unexpected response format from HF Zero-Shot API: {result}")
                return None
                
    except Exception as e:
        logger.warning(f"Failed to query HF Zero-Shot API: {e}")
        return None
        
    return None


async def heuristic_predict(description: str, title: str = "") -> Tuple[str, List[str], str]:
    """
    Predict category, tags, and intensity_level.
    First tries Hugging Face Zero-Shot Classification API,
    and falls back to rule-based keyword matching if the API fails or is unconfigured.
    """
    text_raw = f"{title} {description}".strip()
    
    # 1. Try Hugging Face Zero-Shot Category Classification
    best_category = None
    if text_raw:
        best_category = await query_hf_zero_shot(text_raw, CATEGORY_ENUM)

    # Clean text for tag extraction and fallback keyword matching
    cleaned_raw = re.sub(r"[^\w\s]", " ", text_raw.lower())
    cleaned_words = " ".join(cleaned_raw.split())
    cleaned_text = f" {cleaned_words} "
    cleaned_no_accents = remove_vietnamese_diacritics(cleaned_text)

    if not best_category:
        logger.debug("Falling back to local keyword-based heuristics for category prediction.")
        category_scores = {cat: 0.0 for cat in CATEGORY_ENUM}
        for category, keywords in CATEGORY_KEYWORDS.items():
            # Category name itself appearing in text gets bonus points
            cat_word = f" {category} "
            if cat_word in cleaned_text or cat_word in cleaned_no_accents:
                category_scores[category] += 5.0

            for kw in keywords:
                kw_clean = kw.lower().strip()
                if not kw_clean:
                    continue

                phrase = f" {kw_clean} "
                # Whole phrase/word match
                if phrase in cleaned_text or phrase in cleaned_no_accents:
                    category_scores[category] += 3.0
                # Substring match (only for keywords of length >= 4 to avoid false positive substring matches on short words)
                elif len(kw_clean) >= 4 and (kw_clean in cleaned_text or kw_clean in cleaned_no_accents):
                    category_scores[category] += 0.5

        # Get category with highest score
        best_category = max(category_scores, key=category_scores.get)
        if category_scores[best_category] == 0:
            best_category = "entertainment"  # Default fallback

    # 2. Determine predicted_intensity based on category
    # gaming, sports, entertainment -> high
    # cooking, lifestyle, education -> medium
    # calming, nature -> low
    if best_category in ["gaming", "sports", "entertainment"]:
        predicted_intensity = "high"
    elif best_category in ["cooking", "lifestyle", "education"]:
        predicted_intensity = "medium"
    else:  # calming, nature
        predicted_intensity = "low"

    # Override intensity based on specific trigger words
    calming_triggers = [
        "relax", "sleep", "meditation", "lofi", "ambient", "quiet", "breathe", "spa", "chill", "cozy",
        "thư giãn", "ngủ ngon", "thiền", "yên bình", "chữa lành", "tĩnh lặng", "êm dịu", "nhẹ nhàng"
    ]
    high_triggers = [
        "gym", "workout", "fitness", "speedrun", "action", "challenge", "extreme", "hardcore",
        "tập luyện", "đấu giải", "thể thao", "chạy bộ", "đá bóng", "bóng đá", "vận động"
    ]

    words_list = cleaned_words.split()
    for w in words_list:
        w_clean = w.strip().lower()
        w_no_accent = remove_vietnamese_diacritics(w_clean)
        if w_clean in calming_triggers or w_no_accent in calming_triggers:
            predicted_intensity = "low"
            break
        elif w_clean in high_triggers or w_no_accent in high_triggers:
            predicted_intensity = "high"
            break

    # 3. Smart tag extraction
    tags = []

    # First, prioritize matching keywords belonging to the selected category
    for kw in CATEGORY_KEYWORDS[best_category]:
        kw_clean = kw.lower().strip()
        if not kw_clean or len(kw_clean) < 3:
            continue
        phrase = f" {kw_clean} "
        if (phrase in cleaned_text or phrase in cleaned_no_accents):
            target_tag = clean_and_translate_tag(kw_clean)
            if target_tag and target_tag not in tags:
                tags.append(target_tag)
                if len(tags) >= 8:
                    break

    # Second, add default category tags if we need more
    if len(tags) < 8:
        for default_tag in CATEGORY_DEFAULT_TAGS.get(best_category, []):
            target_tag = clean_and_translate_tag(default_tag)
            if target_tag and target_tag not in tags:
                tags.append(target_tag)
                if len(tags) >= 8:
                    break

    # Third, extract most frequent custom words from the text
    if len(tags) < 8:
        candidate_words = []
        for w in words_list:
            w_clean = w.strip()
            target_tag = clean_and_translate_tag(w_clean)
            if (
                target_tag
                and len(target_tag) > 2
                and len(target_tag) < 15
                and not target_tag.isdigit()
            ):
                candidate_words.append(target_tag)

        from collections import Counter
        word_counts = Counter(candidate_words)
        most_common = [word for word, count in word_counts.most_common(12)]
        for word in most_common:
            if word not in tags:
                tags.append(word)
                if len(tags) >= 8:
                    break

    return best_category, tags[:8], predicted_intensity



def get_heuristic_max_score(description: str, title: str = "") -> float:
    """
    Calculate the maximum heuristic keyword-matching score across all categories.
    Used to determine if there is a strong keyword-based classification override.
    """
    text_raw = f"{title} {description}".lower()

    # Clean text: replace non-alphanumeric (except spaces) with spaces
    cleaned_raw = re.sub(r"[^\w\s]", " ", text_raw)
    cleaned_words = " ".join(cleaned_raw.split())
    cleaned_text = f" {cleaned_words} "

    # Unaccented text for matching unaccented words
    cleaned_no_accents = remove_vietnamese_diacritics(cleaned_text)

    category_scores = {cat: 0.0 for cat in CATEGORY_ENUM}
    for category, keywords in CATEGORY_KEYWORDS.items():
        # Category name itself appearing in text gets bonus points
        cat_word = f" {category} "
        if cat_word in cleaned_text or cat_word in cleaned_no_accents:
            category_scores[category] += 5.0

        for kw in keywords:
            kw_clean = kw.lower().strip()
            if not kw_clean:
                continue

            phrase = f" {kw_clean} "
            # Whole phrase/word match
            if phrase in cleaned_text or phrase in cleaned_no_accents:
                category_scores[category] += 3.0
            # Substring match (only for keywords of length >= 4 to avoid false positive substring matches on short words)
            elif len(kw_clean) >= 4 and (kw_clean in cleaned_text or kw_clean in cleaned_no_accents):
                category_scores[category] += 0.5

    return max(category_scores.values())


async def predict_category_and_tags(description: str, title: str = "") -> Tuple[str, List[str]]:
    """
    Deprecated: Use predict_all_metadata instead.
    Provided for backward compatibility.
    """
    cat, tags, _ = await predict_all_metadata(description, title)
    return cat, tags


async def predict_all_metadata(description: str, title: str = "") -> Tuple[str, List[str], str]:
    """
    Predict category, tags, and intensity_level for a video.
    Uses fine-tuned scikit-learn models if available, otherwise falls back to heuristics.
    """
    # If there is a strong heuristic keyword match (score >= 3.0), we trust the heuristics
    # over the ML model to ensure absolute precision for explicit/labeled content.
    h_max_score = get_heuristic_max_score(description, title)
    if h_max_score >= 3.0:
        logger.debug(f"Strong heuristic match found (score: {h_max_score}). Overriding ML model.")
        return await heuristic_predict(description, title)

    if not os.path.exists(MODEL_PATH):
        logger.debug("Trained model not found. Using heuristic fallback.")
        return await heuristic_predict(description, title)

    try:
        with open(MODEL_PATH, "rb") as f:
            model_data = pickle.load(f)

        vectorizer = model_data["vectorizer"]
        category_classifier = model_data["category_classifier"]
        tags_classifiers = model_data["tags_classifiers"]
        intensity_classifier = model_data.get("intensity_classifier")
        unique_categories = model_data.get("unique_categories", [])
        unique_intensities = model_data.get("unique_intensities", [])

        # Combine title and description
        text = f"{title} {description}".strip()
        if not text:
            return await heuristic_predict(description, title)

        # Vectorize text
        X = vectorizer.transform([text])

        # If the input text has zero overlap with the ML model's vocabulary,
        # the ML prediction will be completely arbitrary (biased toward majority class).
        # We fall back to the high-accuracy heuristics in this case.
        if X.nnz == 0:
            logger.debug("Input text has zero overlap with ML vocabulary. Falling back to heuristics.")
            return await heuristic_predict(description, title)

        # 1. Predict Category
        if category_classifier is not None and len(unique_categories) > 1:
            pred_cat = category_classifier.predict(X)[0]
        elif len(unique_categories) == 1:
            pred_cat = unique_categories[0]
        else:
            pred_cat, _, _ = await heuristic_predict(description, title)

        # Make sure predicted category is valid
        if pred_cat not in CATEGORY_ENUM:
            pred_cat, _, _ = await heuristic_predict(description, title)

        # 2. Predict Tags
        predicted_tags = []
        for tag, clf in tags_classifiers.items():
            if isinstance(clf, int):
                # Constant prediction
                if clf == 1:
                    predicted_tags.append(tag)
            else:
                pred = clf.predict(X)[0]
                if pred == 1:
                    predicted_tags.append(tag)

        # Fallback to heuristics if no tags were predicted
        if not predicted_tags:
            _, predicted_tags, _ = await heuristic_predict(description, title)

        # 3. Predict Intensity Level
        from app.models.video import INTENSITY_ENUM
        if intensity_classifier is not None and len(unique_intensities) > 1:
            pred_intensity = intensity_classifier.predict(X)[0]
        elif len(unique_intensities) == 1:
            pred_intensity = unique_intensities[0]
        else:
            _, _, pred_intensity = await heuristic_predict(description, title)

        if pred_intensity not in INTENSITY_ENUM:
            _, _, pred_intensity = await heuristic_predict(description, title)

        return pred_cat, predicted_tags[:8], pred_intensity

    except Exception as e:
        logger.error(f"Error predicting with ML model: {e}. Falling back to heuristics.")
        return await heuristic_predict(description, title)


async def train_classifier() -> Dict[str, Any]:
    """
    Asynchronously queries all videos from the MongoDB database,
    and trains TF-IDF + LogisticRegression models to predict Category, Tags, and Intensity Level.
    Saves models to app/utils/model/classification_model.pkl.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    import numpy as np

    from app.repositories.video_repository import VideoRepository
    repo = VideoRepository()

    # Query all videos (limit to 2000 to cover full DB)
    videos = await repo.find_many(limit=2000)

    X_raw = []
    y_category_raw = []
    y_intensity_raw = []
    y_tags_raw = []

    for v in videos:
        title = v.get("title", "").strip()
        desc = v.get("description", "").strip()
        text = f"{title} {desc}".strip()
        
        category = v.get("category", "").strip()
        intensity = v.get("intensity_level", "").strip()
        tags = v.get("tags", [])

        # Train on videos that have category, intensity, tags, and some text
        if text and category and intensity and isinstance(tags, list) and len(tags) > 0:
            cleaned_train_tags = []
            for t in tags:
                if not t.strip():
                    continue
                target_tag = clean_and_translate_tag(t)
                if target_tag and target_tag not in cleaned_train_tags:
                    cleaned_train_tags.append(target_tag)
            
            # Only train if we have at least one valid English tag left after processing
            if cleaned_train_tags:
                X_raw.append(text)
                y_category_raw.append(category)
                y_intensity_raw.append(intensity)
                y_tags_raw.append(cleaned_train_tags)

    n_samples = len(X_raw)
    if n_samples < 5:
        return {
            "success": False,
            "message": f"Too few training samples ({n_samples}). Need at least 5 videos to train.",
            "n_samples": n_samples
        }

    # Initialize TF-IDF Vectorizer
    vectorizer = TfidfVectorizer(
        max_features=3000,
        ngram_range=(1, 2),
        stop_words="english",
        sublinear_tf=True
    )
    X = vectorizer.fit_transform(X_raw)

    # 1. Category Classifier Training
    unique_categories = np.unique(y_category_raw)
    category_classifier = None
    category_accuracy = 1.0

    if len(unique_categories) > 1:
        category_classifier = LogisticRegression(
            C=1.0, 
            max_iter=1000, 
            class_weight="balanced"
          )
        category_classifier.fit(X, y_category_raw)
        category_accuracy = float(category_classifier.score(X, y_category_raw))
    elif len(unique_categories) == 1:
        category_accuracy = 1.0

    # 2. Intensity Level Classifier Training
    unique_intensities = np.unique(y_intensity_raw)
    intensity_classifier = None
    intensity_accuracy = 1.0

    if len(unique_intensities) > 1:
        intensity_classifier = LogisticRegression(
            C=1.0, 
            max_iter=1000, 
            class_weight="balanced"
        )
        intensity_classifier.fit(X, y_intensity_raw)
        intensity_accuracy = float(intensity_classifier.score(X, y_intensity_raw))
    elif len(unique_intensities) == 1:
        intensity_accuracy = 1.0

    # 3. Tags Classifier Training
    all_tags = set()
    for tags_list in y_tags_raw:
        for t in tags_list:
            all_tags.add(t)

    tag_vocabulary = sorted(list(all_tags))
    tags_classifiers = {}

    for tag in tag_vocabulary:
        y_tag = np.array([1 if tag in tags_list else 0 for tags_list in y_tags_raw])

        if 0 < np.sum(y_tag) < len(y_tag):
            clf = LogisticRegression(
                C=1.0, 
                max_iter=1000, 
                class_weight="balanced"
            )
            clf.fit(X, y_tag)
            tags_classifiers[tag] = clf
        else:
            tags_classifiers[tag] = int(y_tag[0])

    # Save to disk
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_data = {
        "vectorizer": vectorizer,
        "category_classifier": category_classifier,
        "intensity_classifier": intensity_classifier,
        "tags_classifiers": tags_classifiers,
        "tag_vocabulary": tag_vocabulary,
        "unique_categories": unique_categories.tolist(),
        "unique_intensities": unique_intensities.tolist(),
        "n_samples": n_samples
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model_data, f)

    logger.info(f"Classifier model trained successfully on {n_samples} samples.")

    return {
        "success": True,
        "n_samples": n_samples,
        "category_accuracy": category_accuracy,
        "intensity_accuracy": intensity_accuracy,
        "num_categories": len(unique_categories),
        "num_intensities": len(unique_intensities),
        "num_tags": len(tag_vocabulary)
    }
