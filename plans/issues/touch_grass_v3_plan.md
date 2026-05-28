# 🌿 Touch Grass v3 — Implementation Plan

---

## Vấn đề 1: Session API bị spam liên tục

### Root Cause (chính xác)

Có **2 nguồn** gọi `GET /sessions/{id}` cùng lúc:

```
Nguồn 1: setInterval(3000) trong App.tsx
   → Mỗi 3 giây gọi refreshSessionStats() BẤT KỂ có gì thay đổi không
   → User đang treo 1 video → vẫn cứ gọi mỗi 3s → SPAM

Nguồn 2: sendBehaviorLog().then(() => onRefreshSessionStats())
   → Đã bị xóa ở lần fix trước ✅ (VideoCard.tsx)
```

**Vấn đề thật sự**: `setInterval(3000)` gọi session API mỗi 3 giây dù user **không scroll gì cả**. Fatigue score chỉ thay đổi khi có behavior_log mới → polling khi đứng yên = spam vô ích.

### Fix: Bỏ polling, chuyển sang event-driven

**Ý tưởng**: Chỉ gọi `refreshSessionStats()` **MỘT LẦN** khi user **lướt tới video mới** (sau khi behavior log của video cũ đã gửi xong).

```
User lướt từ Video A → Video B
  │
  ├── VideoCard A cleanup: sendBehaviorLog(A) 
  │      │
  │      └── .then(() => onRefreshSessionStats())  ← GỌI 1 LẦN DUY NHẤT
  │
  └── VideoCard B activate: play video B
```

Khác với cách cũ (bị spam), cách mới **không dùng setInterval** nên:
- Treo 1 video = 0 API call
- Lướt 1 video = 1 call duy nhất (sau khi log gửi xong)

### Thay đổi cụ thể:

#### `App.tsx`:

```diff
- // Polling for Analytics Dashboard
- useEffect(() => {
-   let intervalId: any;
-   if (sessionId) {
-     intervalId = setInterval(() => {
-       refreshSessionStats(sessionId);
-     }, 3000);
-   }
-   return () => clearInterval(intervalId);
- }, [sessionId, isMindfulActive]);
```

→ **XÓA HOÀN TOÀN** block `setInterval`.

#### `VideoCard.tsx`:

```diff
  sendBehaviorLog(
    params.videoId,
    params.topic,
    params.userId,
    params.sessionId,
    params.swipeSpeed,
    duration,
    wasInteracted
- );
+ ).then(() => {
+   onRefreshSessionStats();
+ });
```

→ **THÊM LẠI** `.then()` — nhưng lần này KHÔNG CÓ setInterval nữa nên nó chỉ chạy đúng 1 lần khi rời video.

### Tại sao lần trước bị spam mà lần này không?

Lần trước: cả `.then()` VÀ `setInterval(3000)` chạy song song → mỗi 3s gọi 1 lần + mỗi lần scroll gọi thêm.

Lần này: CHỈ CÓ `.then()`, không có setInterval. Effect `[isActive, isInWindow]` chỉ fire khi `isActive` thật sự thay đổi (true→false hoặc false→true). `seenVideoIdsRef` đã guard `onVideoActivated` không bị gọi lặp.

**Kết quả**: Treo 1 video → 0 session call. Lướt qua video → đúng 1 session call.

---

## Vấn đề 2: Touch Grass 2-stage popup

### Trạng thái hiện tại của code

Code App.tsx hiện đang **lộn xộn** — bạn revert một số chỗ nhưng vẫn còn sót:
- Line 64: `touchGrassStage` state → vẫn còn  
- Line 67-71: 4 refs (warned, videoCount, stage1, localVideoCountRef) → vẫn còn
- Line 190-210: Logic trigger Stage 1 + Stage 2 trong `refreshSessionStats` → vẫn còn
- Line 399-402: Reset refs trong `resetSession` → vẫn còn
- Line 559: `TouchGrassModal` gọi KHÔNG có prop `stage` → thiếu prop

### Plan: Clean up rồi implement lại đúng

#### Bước 1: Xóa sạch code lộn xộn

Xóa tất cả code touch grass cũ ra khỏi App.tsx, giữ lại chỉ:
- `showTouchGrassModal` state
- `showFarewell` state
- `TouchGrassModal` component render
- `FarewellScreen` component render

#### Bước 2: Thêm state/ref mới (sạch)

```tsx
// Touch Grass 2-stage flow
const [showTouchGrassModal, setShowTouchGrassModal] = useState(false);
const [touchGrassStage, setTouchGrassStage] = useState<1 | 2>(1);
const [showFarewell, setShowFarewell] = useState(false);

// Refs (tồn tại trong 1 session, reset khi end session/logout)
const touchGrassWarnedRef = useRef(false);     // đã hiện stage 1 và user chọn "tiếp tục"
const videoCountAtWarningRef = useRef(0);       // số video đã xem lúc stage 1 bị dismiss
const stage1ShownRef = useRef(false);           // guard: không show stage 1 lặp lại
const localVideoCountRef = useRef(0);           // mirror của localVideoCount state
```

#### Bước 3: Logic trigger trong `refreshSessionStats()`

```tsx
// Chỉ chạy SAU KHI setFatigueScore(newScore)

// --- Stage 1: Cảnh báo lần đầu khi fatigue >= 30% ---
if (newScore >= 30 && !stage1ShownRef.current && !touchGrassWarnedRef.current) {
  stage1ShownRef.current = true;
  setTouchGrassStage(1);
  setShowTouchGrassModal(true);
}

// --- Stage 2: Force quit nếu user đã bỏ qua cảnh báo + xem thêm 3 video ---
if (
  touchGrassWarnedRef.current &&
  localVideoCountRef.current - videoCountAtWarningRef.current >= 3
) {
  touchGrassWarnedRef.current = false;  // prevent re-trigger
  setTouchGrassStage(2);
  setShowTouchGrassModal(true);
}
```

> **Khác với v2**: Stage 2 KHÔNG check `newScore >= 30` nữa. Khi user đã bị cảnh báo rồi mà vẫn cố xem thêm 3 video → bắt buộc popup, bất kể điểm.

#### Bước 4: Sync `localVideoCountRef` trong `handleVideoActivated`

```tsx
const handleVideoActivated = useCallback((videoId: string) => {
  if (seenVideoIdsRef.current.has(videoId)) return;
  seenVideoIdsRef.current.add(videoId);
  
  const video = accumulatedVideosRef.current.find((v: any) => v.id === videoId);
  const intensity: string = video?.intensity_level || 'medium';

  setLocalVideoCount(prev => {
    localVideoCountRef.current = prev + 1;  // sync ref
    return prev + 1;
  });
  setIntensityCounts(prev => ({ ...prev, [intensity]: (prev[intensity] || 0) + 1 }));
  
  // Check stage 2 trigger ngay khi video mới được activate
  if (
    touchGrassWarnedRef.current &&
    localVideoCountRef.current - videoCountAtWarningRef.current >= 3
  ) {
    touchGrassWarnedRef.current = false;
    setTouchGrassStage(2);
    setShowTouchGrassModal(true);
  }
}, []);
```

> **Tại sao check ở đây nữa?** Vì `refreshSessionStats` chỉ chạy sau khi `sendBehaviorLog` xong (event-driven). Nhưng `handleVideoActivated` chạy NGAY khi user lướt tới video mới. Stage 2 cần trigger ngay lập tức khi đếm đủ 3 video, không cần đợi API.

#### Bước 5: Handlers

```tsx
// User chọn "Tiếp tục xem" ở Stage 1
const handleContinueWatching = () => {
  setShowTouchGrassModal(false);
  touchGrassWarnedRef.current = true;
  videoCountAtWarningRef.current = localVideoCountRef.current;
};

// User chọn "Chạm cỏ" (cả 2 stage) → logout + farewell
const handleTouchGrass = async () => {
  setShowTouchGrassModal(false);
  // Reset all flags
  touchGrassWarnedRef.current = false;
  videoCountAtWarningRef.current = 0;
  stage1ShownRef.current = false;
  localVideoCountRef.current = 0;
  // End session + logout → farewell screen
  await handleLogout();
  setShowFarewell(true);
};
```

> **Thay đổi quan trọng**: `handleTouchGrass` gọi `handleLogout()` thay vì `resetSession()`. User bị buộc đăng xuất hoàn toàn, không chỉ reset session.

#### Bước 6: Reset flags ở mọi nơi cần

```
Các nơi cần reset touch grass refs:
1. useEffect([user?.id]) — login/logout
2. handleLogout()
3. resetSession()
```

#### Bước 7: TouchGrassModal component

```tsx
// Props:
interface TouchGrassModalProps {
  isOpen: boolean;
  fatigueScore: number;
  stage: 1 | 2;
  onTouchGrass: () => void;
  onContinue?: () => void;  // undefined ở stage 2
}

// Stage 1: 
//   Title: "Này... Bạn đang kiệt sức rồi đó! 🌿"
//   Nút 1: "🌿 Chạm Cỏ Ngay!" → onTouchGrass
//   Nút 2: "Tiếp tục xem" → onContinue

// Stage 2:
//   Title: "Bạn đã xem thêm 3 video rồi... 😤" (rose-400 color)
//   Subtitle: "Đã đến lúc thật sự nghỉ ngơi rồi nhé!"
//   Nút 1 ONLY: "OK, mình đi chạm cỏ đây! 🌱" → onTouchGrass
//   KHÔNG có nút "Tiếp tục"
```

→ **Component này ĐÃ được implement ở bước trước** ✅ (chỉ cần pass đúng prop `stage`)

---

## Flow tổng hợp

```
Login → Session bắt đầu → fatigue = 0%
  │
  ├── User lướt video 1, 2, 3...
  │     mỗi lần lướt: sendBehaviorLog → .then(refreshSessionStats) 
  │     → fatigue tăng dần (GỌI 1 LẦN DUY NHẤT, KHÔNG SPAM)
  │
  ├── fatigue >= 30%
  │     └── Stage 1 Modal hiện lên
  │           ├── "Chạm cỏ" → handleLogout + FarewellScreen
  │           └── "Tiếp tục" → warned=true, ghi videoCount hiện tại
  │
  ├── User tiếp tục xem thêm 3 video
  │     └── Stage 2 Modal hiện lên (ngay khi video thứ 3 activate)
  │           └── "OK chạm cỏ" → handleLogout + FarewellScreen (bắt buộc)
  │
  └── Logout / End session → reset tất cả flags
```

---

## Danh sách file thay đổi

| File | Thay đổi | Loại |
|---|---|---|
| `App.tsx` | Xóa `setInterval(3000)` polling | Bug fix |
| `App.tsx` | Clean up code lộn xộn từ revert | Cleanup |
| `App.tsx` | Thêm lại refs + stage logic (sạch) | Feature |
| `App.tsx` | `handleTouchGrass` gọi `handleLogout()` | Feature |
| `App.tsx` | `handleVideoActivated` sync ref + check stage 2 | Feature |
| `App.tsx` | Pass `stage` prop cho `TouchGrassModal` | Feature |
| `VideoCard.tsx` | Thêm lại `.then(() => onRefreshSessionStats())` | Bug fix |
| `TouchGrassModal.tsx` | Render 2 stage khác nhau (đã implement) | Done ✅ |

---

## Thứ tự triển khai

```
[1] App.tsx: Xóa setInterval polling
[2] VideoCard.tsx: Thêm lại .then(refreshSessionStats)
[3] App.tsx: Clean up code lộn xộn, setup refs/state sạch
[4] App.tsx: Logic trigger trong refreshSessionStats + handleVideoActivated
[5] App.tsx: Handlers (handleTouchGrass gọi handleLogout, handleContinueWatching)
[6] App.tsx: Reset flags ở logout/resetSession/user effect
[7] App.tsx: Pass stage prop cho TouchGrassModal
```
