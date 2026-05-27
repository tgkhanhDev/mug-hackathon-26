# 🔧 Kế Hoạch Fix: Duplicate Behavior Log + Các Edge Case Touch Pad

**Ngày tạo:** 27/05/2026  
**Vấn đề:** CÓ NHIỀU behavior_log được tạo cho cùng 1 video trong 1 session  
**Trạng thái:** Chờ Review

---

## 📋 Phân Tích Vấn Đề

### Luồng Hiện Tại (CÓ BUG) ❌

```
User mở Feed
  ↓
Video 1 được hiển thị (70% màn hình)
  ↓
[LOG #1] Log được tạo ngay lập tức: watch_duration=0.0 ← PROBLEM: Log sớm quá
  {
    "video_id": "6a169cd085d9ff4baeba34cf",
    "watch_duration": {"source": "0.0", "parsedValue": 0},
    "timestamp": "2026-05-27T09:03:52.387499"
  }
  ↓
User lướt/scroll (touch pad: Video 1→30%, Video 2→70%)
  ↓
User thả tay (kéo lại Video 1→70%)
  ↓
[LOG #2] Log được tạo khi rời video: watch_duration=5.904 ← THỜI GIAN THỰC
  {
    "video_id": "6a169cd085d9ff4baeba34cf",
    "watch_duration": 5.904,
    "timestamp": "2026-05-27T09:03:58.291536"
  }
  ↓
[LOG #3] Log cho Video 2: watch_duration=0.492 ← LOG SỚM
  {
    "video_id": "6a169cc885d9ff4baeba34c7",
    "watch_duration": 0.492,
    "timestamp": "2026-05-27T09:03:58.784407"
  }

KẾT QUẢ: 3 logs cho 2 videos = TRÙNG LẶP ❌
```

### Các Nguyên Nhân Gốc 🎯

1. **Log ngay khi video được kích hoạt** 
   - Khi video hiện lên, log được tạo ngay với watch_duration=0
   - Vấn đề: User chưa xem gì cả
   - Nên: Chỉ log khi rời video (khi biết thời gian xem thực)

2. **Không có Deduplication**
   - Cùng (sessionId, videoId) có thể được log nhiều lần
   - Touch pad tạo events nhanh
   - Không kiểm tra xem log trùng không

3. **Touch Pad Edge Case**
   - Touch pad tạo events scroll nhanh qua lại
   - Mỗi "rời" video = 1 log
   - Chuột bình thường không có vấn đề này

4. **Lướt Qua Lại (Back-and-Forth)**
   - Khi user lướt Video 1 → 70% → 30% → quay lại 70%
   - Code hiện tại cứ mỗi thay đổi là tính "rời" video trước
   - Nên: Bỏ qua lướt qua lại nếu trong cùng 1 gesture

---

## ✅ Các Giải Pháp Được Đề Xuất

### **Giải Pháp 1: Bỏ Log Ngay Khi Kích Hoạt (RECOMMENDED)**

**Cách tiếp cận:** Chỉ log khi user **rời video**, KHÔNG log khi nó hiện ra.

**Điểm trừ vs điểm cộng:**
```
CŨ (Hiện tại - Có bug):
  ✅ Capture mọi video vào viewport
  ❌ Log videos user chưa xem thực sự (duration=0)
  ❌ Duplicate logs cho cùng video

MỚI (Đề xuất):
  ✅ Chỉ log xem thực tế (khi rời)
  ✅ Luôn có watch_duration thực
  ❌ Có thể miss video đầu nếu user đóng app (hiếm)
  ❌ Video đầu không được log nếu session kết thúc ngay
```

**Cài đặt:**
```tsx
// TRƯỚC (Hiện tại - Có bug)
const handleVideoActivated = (videoId) => {
  // ❌ Cái này tạo log ngay với duration=0
  sendBehaviorLog(videoId, topic, 0.0, 0); // duration=0
};

const handleVideoLeave = (videoId, duration) => {
  // ✅ Cái này tạo log với duration thực tế
  sendBehaviorLog(videoId, topic, duration, swipeSpeed);
};

// SAU (Sửa)
const handleVideoActivated = (videoId) => {
  // ✅ Không làm gì ở đây - chờ user rời video
  trackVideoStart(videoId); // Chỉ track nội bộ
};

const handleVideoLeave = (videoId, duration) => {
  // ✅ Chỉ log khi biết duration thực
  if (duration > 0.1) { // Bỏ qua view < 100ms
    sendBehaviorLog(videoId, topic, duration, swipeSpeed);
  }
};
```

---

### **Giải Pháp 2: Thêm Deduplication (Bảo Vệ)**

**Mục đích:** Prevent cùng (sessionId, videoId) không được log 2 lần.

**Vị trí cài đặt:** Frontend (Feed.tsx) + Backend (InteractionService)

**Deduplication ở Frontend:**
```tsx
// File: frontend/src/components/Feed.tsx

export const Feed: React.FC<FeedProps> = ({ ... }) => {
  // MỚI: Track videos đã log trong session này
  const loggedVideosRef = useRef<Set<string>>(new Set());
  
  const createLogKey = (videoId: string) => `${videoId}`;
  
  const sendBehaviorLogSafe = async (
    videoId: string,
    topic: string,
    duration: number,
    swipeSpeed: number
  ) => {
    const logKey = createLogKey(videoId);
    
    // MỚI: Kiểm tra xem đã log chưa
    if (loggedVideosRef.current.has(logKey)) {
      console.warn(`⚠️ [Dedup] Video ${videoId} đã được log trong session`);
      return; // Bỏ qua
    }
    
    loggedVideosRef.current.add(logKey); // Đánh dấu là đã log
    
    try {
      await sendBehaviorLog(videoId, topic, userId, sessionId, swipeSpeed, duration, false);
      console.log(`✅ [Log] Video ${videoId}: duration=${duration}s`);
    } catch (error) {
      console.error(`❌ Lỗi log: ${error}`);
      loggedVideosRef.current.delete(logKey); // Xóa nếu lỗi (cho phép retry)
    }
  };
  
  // Dùng cái này thay cho sendBehaviorLog
  // ...
};
```

**Deduplication ở Backend:**
```python
# File: backend/app/services/interaction_service.py

async def record_behavior_log(self, data: BehaviorLogCreate) -> BehaviorLogResponse:
    """Ghi log behavior với check duplicate."""
    
    # MỚI: Kiểm tra xem log cho video này đã tồn tại chưa
    existing_log = await self._log_repo.find_one({
        "session_id": data.session_id,
        "video_id": data.video_id,
        "is_interaction": False,
        # Kiểm tra nếu tạo trong 60 giây vừa rồi
        "timestamp": {"$gte": datetime.utcnow() - timedelta(seconds=60)}
    })
    
    if existing_log:
        logger.warning(
            f"⚠️ [Dedup] Duplicate behavior log cho video {data.video_id} "
            f"trong session {data.session_id}. Bỏ qua."
        )
        # Lựa chọn 1: Bỏ qua và return log cũ
        return self._log_to_response(existing_log)
        
        # Lựa chọn 2: Cập nhật log cũ với duration mới
        # await self._log_repo.update_one(
        #     existing_log['_id'],
        #     {"watch_duration": data.watch_duration}
        # )
        # return self._log_to_response(existing_log)
    
    # MỚI: Nếu duration quá ngắn (<100ms), log lỡ từ touch
    if data.watch_duration < 0.1:
        logger.debug(f"⏭️ [Micro-view] Bỏ video {data.video_id}: {data.watch_duration}s")
        return None  # Không log cái này
    
    # Tiếp tục log bình thường
    log_id = str(ObjectId())
    doc = BehaviorLogInDB(id=log_id, **data.model_dump())
    await self._log_repo.insert_one(doc.model_dump())
    
    # Background processing
    asyncio.create_task(self._process_behavior_log_background(data, log_id, now))
    
    return self._log_to_response(doc)
```

---

### **Giải Pháp 3: Xử Lý Touch Pad Back-and-Forth**

**Vấn đề:** Touch pad tạo lựa nhanh qua lại → nhiều "rời" events.

**Giải pháp:** Debounce hoặc detect pattern gesture.

**Cách A: Debounce Scroll Events**
```tsx
// File: frontend/src/components/Feed.tsx

const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

const handleScroll = (offset: number) => {
  // Clear timeout trước đó
  if (scrollTimeoutRef.current) {
    clearTimeout(scrollTimeoutRef.current);
  }
  
  // MỚI: Debounce - chờ 150ms trước khi xử lý
  // Điều này prevent lướt nhanh qua lại trigger nhiều logs
  scrollTimeoutRef.current = setTimeout(() => {
    processSwipe(offset);
  }, 150);
};
```

**Cách B: Detect Back-and-Forth Pattern**
```tsx
// File: frontend/src/components/Feed.tsx

const swipeHistoryRef = useRef<Array<{
  direction: 'up' | 'down';
  timestamp: number;
  offset: number;
}>>([]);

const detectBackAndForth = () => {
  const history = swipeHistoryRef.current;
  if (history.length < 2) return false;
  
  const now = Date.now();
  const recent = history.filter(h => now - h.timestamp < 500); // 500ms gần nhất
  
  if (recent.length >= 2) {
    // Check xem lướt hay xen kẽ (up → down → up)
    let alternating = true;
    for (let i = 1; i < recent.length; i++) {
      if (recent[i].direction === recent[i - 1].direction) {
        alternating = false;
        break;
      }
    }
    
    if (alternating) {
      console.warn("⚠️ Phát hiện lướt qua lại, bỏ qua log");
      return true; // Bỏ qua log này
    }
  }
  
  return false;
};

const handleVideoLeave = (videoId, duration) => {
  if (detectBackAndForth()) {
    console.warn(`⏭️ Lướt qua lại cho ${videoId}, bỏ qua log`);
    return;
  }
  
  sendBehaviorLogSafe(videoId, topic, duration, swipeSpeed);
};
```

---

## 🎯 Lựa Chọn Fix (Phương án tối ưu)

