🔧 Kế Hoạch Fix: Duplicate Behavior Log + Các Edge Case Touch Pad
Ngày tạo: 27/05/2026
Vấn đề: CÓ NHIỀU behavior_log được tạo cho cùng 1 video trong 1 session
Trạng thái: Chờ Review

📋 Phân Tích Vấn Đề
Luồng Hiện Tại (CÓ BUG) ❌
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
Các Nguyên Nhân Gốc 🎯
Log ngay khi video được kích hoạt

Khi video hiện lên, log được tạo ngay với watch_duration=0
Vấn đề: User chưa xem gì cả
Nên: Chỉ log khi rời video (khi biết thời gian xem thực)
Không có Deduplication

Cùng (sessionId, videoId) có thể được log nhiều lần
Touch pad tạo events nhanh
Không kiểm tra xem log trùng không
Touch Pad Edge Case

Touch pad tạo events scroll nhanh qua lại
Mỗi "rời" video = 1 log
Chuột bình thường không có vấn đề này
Lướt Qua Lại (Back-and-Forth)

Khi user lướt Video 1 → 70% → 30% → quay lại 70%
Code hiện tại cứ mỗi thay đổi là tính "rời" video trước
Nên: Bỏ qua lướt qua lại nếu trong cùng 1 gesture
✅ Các Giải Pháp Được Đề Xuất
Giải Pháp 1: Bỏ Log Ngay Khi Kích Hoạt (RECOMMENDED)
Cách tiếp cận: Chỉ log khi user rời video, KHÔNG log khi nó hiện ra.

Điểm trừ vs điểm cộng:

CŨ (Hiện tại - Có bug):
  ✅ Capture mọi video vào viewport
  ❌ Log videos user chưa xem thực sự (duration=0)
  ❌ Duplicate logs cho cùng video

MỚI (Đề xuất):
  ✅ Chỉ log xem thực tế (khi rời)
  ✅ Luôn có watch_duration thực
  ❌ Có thể miss video đầu nếu user đóng app (hiếm)
  ❌ Video đầu không được log nếu session kết thúc ngay
Cài đặt:

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
Giải Pháp 2: Thêm Deduplication (Bảo Vệ)
Mục đích: Prevent cùng (sessionId, videoId) không được log 2 lần.

Vị trí cài đặt: Frontend (Feed.tsx) + Backend (InteractionService)

Deduplication ở Frontend:

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
Deduplication ở Backend:

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
Giải Pháp 3: Xử Lý Touch Pad Back-and-Forth
Vấn đề: Touch pad tạo lựa nhanh qua lại → nhiều "rời" events.

Giải pháp: Debounce hoặc detect pattern gesture.

Cách A: Debounce Scroll Events

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
Cách B: Detect Back-and-Forth Pattern

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
🎯 Lựa Chọn Fix (Phương án tối ưu)
✅ Chọn: Giải Pháp 1 + UI Scroll Threshold 20%
Tóm tắt:

✅ Chỉ log xem thực tế (khi rời video)
✅ Luôn có watch_duration thực
✅ Gate index change bằng ngưỡng 20%: User phải scroll ≥ 20% chiều cao card mới cho phép setActiveIndex + bắn sendBehaviorLog
✅ Ngăn touchpad lướt nhẹ (ví dụ: 5-15%) gây index flicker + log rác
Kịch bản:

User lướt/scroll (touch pad: Video 1→85%, Video 2→15%)
  ↓ Scroll offset < 20% → KHÔNG đổi index, KHÔNG log
  ↓
User thả tay → snap lại Video 1 (100%)
  ↓ Không có gì xảy ra ✅

---

User lướt mạnh (touch pad: Video 1→30%, Video 2→70%)
  ↓ Scroll offset ≥ 20% → CHO PHÉP setActiveIndex(2)
  ↓
Video 1 cleanup effect fires → sendBehaviorLog(video1, duration=5.9s) ✅
Video 2 starts playing ✅
📝 Implementation Plan
Phase 1: UI Scroll Threshold Gate (Feed.tsx)
File: frontend/src/components/Feed.tsx

Mục tiêu: Chỉ cho phép setActiveIndex khi scroll offset vượt ngưỡng 20% chiều cao card.

Thay đổi:

 // Feed.tsx – handleScroll function

+ const SCROLL_THRESHOLD = 0.20; // 20% card height

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const container = e.currentTarget;
    const scrollPos = container.scrollTop;
    const cardHeight = container.clientHeight;

    // Detect scroll start
    if (scrollStartTime.current === null) {
      scrollStartTime.current = Date.now();
      scrollStartTop.current = scrollPos;
    }

    if (scrollTimeout.current) {
      clearTimeout(scrollTimeout.current);
    }

    scrollTimeout.current = setTimeout(() => {
      scrollStartTime.current = null;
      scrollStartTop.current = null;
    }, 150);

-   // Calculate current active index
-   const index = Math.round(scrollPos / cardHeight);
-   if (index !== activeIndex && index >= 0 && index < videos.length) {
+   // Calculate candidate index + displacement from current active position
+   const rawOffset = scrollPos / cardHeight;
+   const candidateIndex = Math.round(rawOffset);
+   // How far user has scrolled away from the current active card (0.0–1.0)
+   const displacement = Math.abs(rawOffset - activeIndex);
+
+   if (
+     candidateIndex !== activeIndex &&
+     candidateIndex >= 0 &&
+     candidateIndex < videos.length &&
+     displacement >= SCROLL_THRESHOLD  // ← Gate: ≥20% mới cho đổi index
+   ) {
      // Calculate speed immediately on index change
      if (isProgrammaticScroll.current) {
        // ... (speed logic unchanged)
      }
      // ...
-     setActiveIndex(index);
+     setActiveIndex(candidateIndex);
    }
  };
Chi tiết logic:

rawOffset = scrollPos / cardHeight → vị trí scroll dạng float (ví dụ: 0.15 = 15% qua card 1)
displacement = |rawOffset - activeIndex| → khoảng cách từ vị trí hiện tại
Nếu displacement < 0.20 → KHÔNG cho đổi index → snap CSS (snap-y mandatory) sẽ kéo lại card cũ
Nếu displacement >= 0.20 → CHO PHÉP đổi index → trigger cleanup effect trong VideoCard → log behavior
[!IMPORTANT] snap-y snap-mandatory trên container sẽ tự động snap card về đúng vị trí sau khi user thả tay. Threshold 20% chỉ gate logic setActiveIndex, KHÔNG ảnh hưởng đến CSS scroll behavior.

Phase 2: Bỏ Log Ngay Khi Kích Hoạt (VideoCard.tsx)
File: frontend/src/components/VideoCard.tsx

Mục tiêu: Đảm bảo behavior log chỉ được bắn trong cleanup (khi rời video), KHÔNG bắn khi video mới hiện ra.

Kiểm tra code hiện tại:

// VideoCard.tsx – useEffect [isActive, isInWindow]
// Lines 111-167

useEffect(() => {
  if (isActive && isInWindow) {
    onVideoActivated?.(videoId);       // ← Chỉ count view, KHÔNG log behavior
    setIsPlaying(true);
    activeStartTimeRef.current = Date.now();  // ← Bắt đầu đo thời gian
    // ...play video...
  }

  return () => {
    // Cleanup: BẮN LOG Ở ĐÂY
    if (activeStartTimeRef.current !== null) {
      const duration = (Date.now() - activeStartTimeRef.current) / 1000;
      activeStartTimeRef.current = null;
      // sendBehaviorLog(...)  ← ✅ Đã đúng: chỉ log khi rời
    }
  };
}, [isActive, isInWindow]);
Trạng thái: ✅ Code hiện tại đã đúng — log chỉ bắn trong cleanup. Vấn đề duplicate đến từ việc setActiveIndex bị trigger quá nhạy (khi scroll < 20%), gây:

isActive=false cho Video 1 → cleanup fires → log #1
isActive=true cho Video 2 → start timer
Touchpad snap lại → isActive=false cho Video 2 → cleanup fires → log #2 (duration ≈ 0.5s)
isActive=true cho Video 1 → start timer
User rời Video 1 thực sự → cleanup fires → log #3
→ 3 logs cho 1 lần xem ❌

Với threshold 20%, bước 1-4 sẽ KHÔNG xảy ra vì scroll chưa vượt ngưỡng.

📋 Checklist Implementation
#	Task	File	Trạng thái
1	Thêm SCROLL_THRESHOLD = 0.20 constant	Feed.tsx	✅ Đã xong
2	Tính displacement từ rawOffset và activeIndex	Feed.tsx	✅ Đã xong
3	Thêm điều kiện displacement >= SCROLL_THRESHOLD vào if-block	Feed.tsx	✅ Đã xong
4	Phase 2: Xác nhận VideoCard.tsx đã bỏ log lúc init	VideoCard.tsx	✅ Đã xong
5	Test: Touchpad lướt nhẹ (< 20%) → KHÔNG đổi index	Manual QA	⬜
6	Test: Touchpad lướt mạnh (≥ 20%) → ĐỔI index + 1 log	Manual QA	⬜
7	Test: Scroll chuột bình thường → hoạt động đúng	Manual QA	⬜
8	Test: Swipe gesture (up/down button) → hoạt động đúng	Manual QA	⬜
9	Verify: Analytics dashboard nhận đúng số lượng logs	Manual QA	⬜
🧪 Test Cases
Test 1: Touchpad Lướt Nhẹ (< 20%)
Hành động: Dùng touchpad scroll nhẹ xuống ~10-15%
Kỳ vọng:
  - Video 1 vẫn active (index không đổi)
  - CSS snap kéo lại Video 1
  - Không có behavior_log nào được tạo
  - Console: không có log message
Test 2: Touchpad Lướt Đủ Mạnh (≥ 20%)
Hành động: Dùng touchpad scroll xuống > 20%
Kỳ vọng:
  - Index đổi từ 0 → 1
  - Video 1 cleanup fires → 1 behavior_log (duration > 0.5s)
  - Video 2 starts playing
  - Console: "✅ [Log] Video {id}: duration=X.Xs"
Test 3: Lướt Qua Lại Nhanh (Back-and-Forth)
Hành động: Scroll nhanh xuống rồi kéo lại ngay (trong 300ms)
Kỳ vọng:
  - Nếu chưa vượt 20%: KHÔNG đổi index, KHÔNG log
  - Nếu vượt 20% nhưng kéo lại: index đổi rồi đổi lại, log với duration < 0.5s → bị filter
Test 4: Programmatic Swipe (Button/Gesture Trigger)
Hành động: Trigger swipeTrigger prop (direction='up')
Kỳ vọng:
  - isProgrammaticScroll = true → bypass threshold (scroll programmatic luôn đi đủ 1 card)
  - Index đổi bình thường
  - Behavior log được tạo đúng khi rời video
[!WARNING] Test 4 cần verify: isProgrammaticScroll.current = true đã được set TRƯỚC khi scrollTo() gọi handleScroll. Kiểm tra timing: isProgrammaticScroll phải là true khi handleScroll fires, nếu không threshold sẽ block programmatic scroll.

⚠️ Edge Cases Cần Lưu Ý
Programmatic scroll bypass: isProgrammaticScroll.current === true → bỏ qua threshold check (đã OK vì scroll programmatic luôn đi full 1 card)
Video đầu tiên: Khi mở feed, Video 1 active tại index=0, displacement=0 → không trigger change → OK (video đầu tiên play bình thường)
Video cuối cùng: Nếu user scroll ở video cuối, candidateIndex >= videos.length bị filter → OK
CSS snap conflict: snap-y mandatory sẽ snap card về integer positions. Threshold 20% chỉ gate JS logic, CSS vẫn hoạt động độc lập → OK
Session unmount: Khi user đóng tab/navigate away, cleanup fires → log final video. Duration filter < 0.5s có thể miss video cuối nếu user đóng nhanh → acceptable tradeoff