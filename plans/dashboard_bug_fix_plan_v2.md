# 🐛 Bug Fix Plan: Feed Composition + Event Log chạy theo behavior_log

**Ngày:** 26/05/2026

---

## Root Cause Analysis

### Bug #1 — Feed Composition luôn = 0

**Vấn đề:** Code hiện tại đang filter `accumulatedVideos` theo field `intensity` và `category`:
```tsx
const highCount = accumulatedVideos.filter(v => v.intensity === 'high').length; // WRONG
const calmCount = accumulatedVideos.filter(v => v.category === 'calming').length; // WRONG
```

Nhưng `accumulatedVideos` từ API thực ra chứa object với field là `intensity_level`, không phải `intensity`. Ngoài ra các video mock trong App.tsx thì KHÔNG có field này luôn → cả 3 bar đều = 0.

**Thêm vào đó:** `accumulatedVideos` được cập nhật theo batch (khi fetch thêm), không phải theo hành động thực của user → count sẽ lệch với những gì user thực sự đã *xem xong*.

**Fix đúng:** Đếm THỰC TẾ những video user đã xem xong dựa vào `sendBehaviorLog` thành công (giống cách đếm `localVideoCount`). Thêm `topic` vào callback để phân loại category.

---

### Bug #2 — Event Log không cập nhật kịp

**Vấn đề:** Event Log hiện chỉ được cập nhật khi:
1. `fatigueScore` vượt ngưỡng 40/70 (từ polling `getSession()` mỗi 3s)
2. Session reset

Nếu user đang lướt bình thường, Event Log im lặng hoàn toàn → nhìn như bị treo.

**Fix đúng:** Mỗi lần `sendBehaviorLog` thành công → push 1 event log thể hiện hành vi lướt vừa xảy ra (instant, không cần đợi poll).

---

## Solution: Mở rộng callback `onBehaviorLogged`

### Cơ chế mới

Thay vì truyền `onVideoWatched: () => void` đơn giản, nâng cấp thành:

```tsx
onBehaviorLogged: (data: { topic: string; swipeSpeed: number; duration: number }) => void
```

**Flow:**
```
User swipes → VideoCard cleanup → sendBehaviorLog().then(() => {
  onRefreshSessionStats()    ← unchanged
  onBehaviorLogged({         ← extended callback
    topic,
    swipeSpeed,
    duration
  })
})
```

---

## Thay đổi chi tiết

### 1. `VideoCard.tsx`

Đổi prop `onVideoWatched?` → `onBehaviorLogged?`:
```tsx
onBehaviorLogged?: (data: { topic: string; swipeSpeed: number; duration: number }) => void;
```

Gọi trong cleanup:
```tsx
sendBehaviorLog(...).then(() => {
  onRefreshSessionStats();
  onBehaviorLogged?.({
    topic: params.topic,
    swipeSpeed: params.swipeSpeed,
    duration
  });
});
```

### 2. `Feed.tsx`

Đổi prop `onVideoWatched?` → `onBehaviorLogged?`, pass xuống VideoCard.

### 3. `App.tsx`

**Thêm state:**
```tsx
const [topicCounts, setTopicCounts] = useState<Record<string, number>>({});
```

**Thêm constant mapping:**
```tsx
const CALMING_TOPICS = ['nature', 'meditation', 'calming', 'sleep', 'piano', 'mindfulness'];
const HIGH_TOPICS    = ['sports', 'football', 'gaming', 'dark_humor', 'programming', 'coding', 'lifestyle'];
// anything else → Low
```

**Thêm handler:**
```tsx
const handleBehaviorLogged = useCallback(({ topic, swipeSpeed, duration }: { topic: string; swipeSpeed: number; duration: number }) => {
  // 1) Increment local video count
  setLocalVideoCount(prev => prev + 1);

  // 2) Update topic counts for Feed Composition
  setTopicCounts(prev => ({ ...prev, [topic]: (prev[topic] || 0) + 1 }));

  // 3) Push event log immediately (no polling needed)
  const isDoom   = swipeSpeed > 500;
  const isCalm   = CALMING_TOPICS.some(t => topic.toLowerCase().includes(t));
  const emoji    = isDoom ? '⚡' : isCalm ? '🌿' : '📹';
  const label    = isDoom ? 'Lướt nhanh' : isCalm ? 'Mindful view' : 'Đã xem';
  setEventLog(prev => [...prev.slice(-29), {
    time: new Date().toLocaleTimeString(),
    message: `${emoji} ${label}: "${topic}" (${Math.round(duration)}s)`,
    type: isDoom ? 'warning' : isCalm ? 'success' : 'info'
  }]);
}, []);
```

**Reset khi session mới:**
```tsx
setTopicCounts({});
```

**Truyền xuống Feed và Dashboard:**
```tsx
<Feed
  ...
  onBehaviorLogged={handleBehaviorLogged}
/>

<AnalyticsDashboard
  ...
  topicCounts={topicCounts}
  // Bỏ accumulatedVideos
/>
```

### 4. `AnalyticsDashboard.tsx`

**Đổi prop:**
```tsx
// Bỏ: accumulatedVideos: any[]
// Thêm: topicCounts: Record<string, number>
```

**Tính toán composition từ topicCounts:**
```tsx
const CALMING_TOPICS = ['nature', 'meditation', 'calming', 'sleep', 'piano', 'mindfulness'];
const HIGH_TOPICS    = ['sports', 'football', 'gaming', 'dark_humor', 'programming', 'coding', 'lifestyle'];

const highCount = Object.entries(topicCounts)
  .filter(([t]) => HIGH_TOPICS.some(h => t.toLowerCase().includes(h)))
  .reduce((sum, [, c]) => sum + c, 0);

const calmCount = Object.entries(topicCounts)
  .filter(([t]) => CALMING_TOPICS.some(h => t.toLowerCase().includes(h)))
  .reduce((sum, [, c]) => sum + c, 0);

const lowCount = sessionVideoCount - highCount - calmCount;

const totalAnalyzed = Math.max(1, sessionVideoCount);
```

---

## Tóm tắt thay đổi

| File | Thay đổi |
|---|---|
| `VideoCard.tsx` | `onVideoWatched` → `onBehaviorLogged({ topic, swipeSpeed, duration })` |
| `Feed.tsx` | Đổi prop name tương ứng |
| `App.tsx` | Thêm `topicCounts` state, `handleBehaviorLogged`, reset khi session mới |
| `AnalyticsDashboard.tsx` | Nhận `topicCounts` thay `accumulatedVideos`, tính composition từ đó |

**Ước tính:** ~15 phút implement.
