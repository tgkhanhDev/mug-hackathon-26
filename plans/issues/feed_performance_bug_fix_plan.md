# 🐛 Feed Performance & Stability Bug Fix Plan

**Phiên bản:** v2 (Implementation-ready)  
**Cập nhật:** 29 Tháng 5, 2026  
**Trạng thái:** Chờ implementation  

---

## 📋 Tóm tắt Executive

Ba lỗi hiện tại làm ảnh hưởng đến trải nghiệm feed video:

| # | Lỗi | Mức độ | Ảnh hưởng người dùng |
|---|-----|--------|----------------------|
| 🔴 1 | **NS_BINDING_ABORTED** | Trung bình | Lỗi lẻ khi scroll nhanh, không gây crash |
| 🔴 2 | **Feed dừng ở 242/246 video** | Cao | Không thể xem 4 video cuối cùng |
| 🔴 3 | **Desktop freeze (2GB transferred)** | Tới hạn | Máy tính bị đóng băng sau ~200 video |

---

## 🔗 Dependency Graph (Thứ tự Implementation)

```
BUG 3 FIX 3A → Fix 3B → Fix 3C  (Có thể song song)
BUG 2 FIX 2A → Fix 2B          (Fix 2A trước, 2B sau)
BUG 1 FIX 1                   (Độc lập, làm cuối cùng)
```

**Khuyến nghị:** Bắt đầu từ **Bug 3** (freeze tới hạn) trước khi fix Bug 2 và Bug 1.

---

## 🐛 BUG 1: NS_BINDING_ABORTED (Lỗi abort HTTP) 

### Nguyên nhân gốc

Khi user scroll và card video ra khỏi visibility window:

1. **isInWindow thay đổi** `true` → `false`
2. **React render lại:** `<video>` element → `<div>` placeholder
3. **Browser xoá DOM node** của video
4. **HTTP request đang download** segment video bị interrupt
5. **Firefox log:** `NS_BINDING_ABORTED` (Chrome tương tự: `ERR_ABORTED`)

**Đây là hành vi ĐÚNG của sliding window** — browser tự động dừng download video đã lướt qua. Tuy nhiên, lỗi này có thể gây **flicker hoặc chậm hiển thị** khi user quay lại card vừa scroll qua.

### Là gì? Tại sao lại xảy ra?

```
Frontend folder structure:
  src/components/VideoCard.tsx (line 311-330)
  
Hiện tại:
  {isInWindow ? <video /> : <div />}
  
Khi isInWindow = false:
  - React unmount <video> ngay → Browser abort request đang chạy
```

---

## 📌 BUG 1: Implementation Steps

### Bước 1: Mở file VideoCard.tsx

Đường dẫn: `frontend/src/components/VideoCard.tsx`

Tìm phần `useEffect` liên quan tới `isInWindow` dependency.

### Bước 2: Thêm cleanup effect riêng

Thêm một `useEffect` **RIÊNG** để xử lý khi `isInWindow` chuyển sang `false`:

**Vị trí:** Sau các `useEffect` hiện tại, thêm code này (ví dụ sau line 280):

```tsx
// Resource cleanup khi video ra khỏi viewport
useEffect(() => {
  if (!isInWindow && videoRef.current) {
    const video = videoRef.current;
    
    // Chủ động pause trước khi unmount
    video.pause();
    
    // Clear source để browser biết hủy bỏ download  
    video.removeAttribute('src');
    
    // Force browser release GPU decoder + texture cache
    video.load();
  }
}, [isInWindow]);  // ← Chỉ chạy khi isInWindow thay đổi
```

**Context đầy đủ (10 dòng trước/sau):**
```tsx
// Line 275 - code hiện tại đã có
  if (hlsRef.current) {
    hlsRef.current.destroy();
    hlsRef.current = null;
  }
}, [someOtherDependency]);

// ← INSERT: Thêm useEffect mới ở đây (line 285)
useEffect(() => {
  if (!isInWindow && videoRef.current) {
    const video = videoRef.current;
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
}, [isInWindow]);

// Line 295 - code khác tiếp tục
return (
  <div ref={inViewRef} className={...}>
```

### Bước 3: Verify video ref tồn tại

Kiểm tra rằng **`videoRef`** đã được khai báo từ trước:

```tsx
const videoRef = useRef<HTMLVideoElement>(null);
// hoặc setRefs = (el) => ... ?
```

Nếu sử dụng callback ref (`setRefs`), cần chuyển sang `useRef` hoặc thêm guard:

```tsx
const videoElement = videoRef.current || /* fallback nếu cần */;
if (videoElement) {
  // cleanup code
}
```

### Bước 4: Kiểm tra HLS cleanup

Đảm bảo `hlsRef` cũng được cleanup:

Tìm dòng có `hlsRef.current.destroy()` — xác nhận nó nằm trong `useEffect` cleanup.

Nếu chưa có, thêm vào:
```tsx
return () => {
  if (hlsRef.current) {
    hlsRef.current.destroy();
    hlsRef.current = null;
  }
};
```

### Bước 5: Build & test cơ bản

Chạy:
```bash
cd frontend
npm run dev
```

Mở console Firefox (F12) hoặc Chrome DevTools → Network tab.

### Bước 6: Verify NS_BINDING_ABORTED được giảm

Scroll nhanh lên/xuống feed:
- **Trước fix:** Thấy `NS_BINDING_ABORTED` hoặc `ERR_ABORTED` trong Network tab
- **Sau fix:** Lỗi không còn hoặc giảm đáng kể

---

## ✅ BUG 1: Acceptance Criteria

| Criteria | Trạng thái | Ghi chú |
|----------|-----------|--------|
| Tồn tại `useEffect` mới với `[isInWindow]` dependency | ✅ Required | Phải có cleanup khi `isInWindow` đổi |
| Gọi `video.removeAttribute('src')` khi `!isInWindow` | ✅ Required | Báo browser dừng download |
| Gọi `video.load()` sau khi remove src | ✅ Required | Force release texture cache |
| `hlsRef.destroy()` được gọi trong cleanup | ✅ Required | HLS worker phải stop |
| Build successfully (npm run dev) | ✅ Required | Không lỗi syntax |
| Network tab không hiện `NS_BINDING_ABORTED` khi scroll | ✅ Verification | Test bằng Firefox DevTools |

---

## 🐛 BUG 2: Feed dừng ở 242/246 video (Thiếu 4 video cuối)

### Nguyên nhân gốc

User lướt tới video 242, sau đó feed không tải nốt 4 video còn lại (243-246):

**Luồng xảy ra:**
```
1. User xem tới video 240/242
2. Feed detectscroll → gọi onLoadMore()
3. Frontend gửi: 
   GET /feed/{userId}?limit=5&exclude=id1,id2,...,id242
4. URL param "exclude" nay ~5.8KB (242 IDs)
5. Browser/SWR có thể:
   - Cắt URL (browser limit ~2048-8192 char)
   - Parse lỗi exclude param
   - Backend nhận incomplete list → trả []
6. Frontend: "Aha, array rỗng = hết dữ liệu" → dừng load
```

**Root cause:** URL query param quá dài, backend các khi nhận thất lạc.

---

## 📌 BUG 2: Implementation Steps

### PHẦN A: Fix 2A (Chuyển exclude sang POST body)

#### Bước A1: Sửa Frontend API client

Đường dẫn: `frontend/src/api/client.ts`

Tìm function `usePersonalizedFeed` hoặc tương tự. Thay đổi từ:

```tsx
// TRƯỚC (line ~120)
const { data: currentVideos } = useSWR(
  user ? `/feed/${user._id}?limit=${BATCH_SIZE}&exclude=${excludeIds.join(',')}` : null,
  fetcher
);
```

Thành:

```tsx
// SAU
const { data: currentVideos } = useSWR(
  user ? `/feed/${user._id}?_k=${feedFetchKey}` : null,
  async (url) => {
    const response = await fetch(url, {
      method: 'GET',  // Vẫn dùng GET nếu exclude rỗng
      headers: { 'Content-Type': 'application/json' }
    });
    return response.json();
  }
);
```

**Hoặc đơn giản hơn:** Bỏ `excludeIds` hoàn toàn, backend dùng Redis seen-set:

```tsx
// CỐI ĐƠN - BỎ EXCLUDE
const { data: currentVideos } = useSWR(
  user ? `/feed/${user._id}?limit=${BATCH_SIZE}&_k=${feedFetchKey}` : null,
  fetcher
);
```

**Context đầy đủ (8 dòng trước/sau):**
```tsx
// Line 115
const [feedFetchKey, setFeedFetchKey] = useState(0);
const [excludeIds, setExcludeIds] = useState<string[]>([]);

// Line 118 - CŨ
// const { data: currentVideos } = useSWR(
//   user ? `/feed/${user._id}?limit=${BATCH_SIZE}&exclude=${excludeIds.join(',')}` : null,
//   fetcher
// );

// Line 118 - MỚI
const { data: currentVideos } = useSWR(
  user ? `/feed/${user._id}?limit=${BATCH_SIZE}&_k=${feedFetchKey}` : null,
  fetcher
);

// Line 125
const onLoadMore = useCallback(() => {
  if (hasFetchedNextBatch.current) return;
```

#### Bước A2: Cập nhật `onLoadMore` để không gửi `excludeIds`

Tìm function `onLoadMore` trong App.tsx hoặc Feed.tsx:

```tsx
// TRƯỚC (line ~200)
const onLoadMore = useCallback(() => {
  if (hasFetchedNextBatch.current) return;
  hasFetchedNextBatch.current = true;
  if (user) {
    setExcludeIds(prev => [...prev, ...accumulatedVideos.map(v => v.id)]);
    setFeedFetchKey(prev => prev + 1);
  }
}, [user, accumulatedVideos]);
```

Thành:

```tsx
// SAU - Chỉ bump key, backend xử lý dedup qua Redis
const onLoadMore = useCallback(() => {
  if (hasFetchedNextBatch.current) return;
  hasFetchedNextBatch.current = true;
  if (user) {
    // ← Bỏ setExcludeIds
    setFeedFetchKey(prev => prev + 1);
  }
}, [user]);
```

**Context đầy đủ (8 dòng):**
```tsx
// Line 195
  const onLoadMore = useCallback(() => {
    if (hasFetchedNextBatch.current) return;
    hasFetchedNextBatch.current = true;
    if (user) {
      // ← XÓA: setExcludeIds(prev => [...prev, ...accumulatedVideos.map(v => v.id)]);
      setFeedFetchKey(prev => prev + 1);
    } else {
      setTrendingLimit(prev => prev + BATCH_SIZE);
    }
  }, [user]);
```

#### Bước A3: Kiểm tra backend API

Đường dẫn: `backend/app/controllers/feed_controller.py`

Xác nhận endpoint `/feed/{userId}` có thể:
1. Nhận tham số `limit` từ query string
2. **Dùng Redis seen-set** để dedup (không cần client gửi `exclude`)

Code hiện tại nên có:
```python
# Line ~50 (giả định)
@router.get("/feed/{user_id}")
async def get_feed(
    user_id: str,
    limit: int = 5,
    # exclude: List[str] = Query(default=[])  ← CÓ THỂ BỎ
):
    # Backend gọi feed_service.get_feed()
    # Service này PHẢI đọc Redis seen-set thay vì client exclude
    videos = await feed_service.get_feed(
        user_id=user_id,
        limit=limit,
        # exclude_ids=[] ← Không cần nữa
    )
    return videos
```

Nếu backend chưa dùng Redis dedup, tạo session memory note để nhắc implement:

```
TODO: Backend cần dùng Redis seen-set reader thay vì client exclude
File: backend/app/services/feed_service.py get_feed()
```

#### Bước A4: Test API endpoint

Dùng curl hoặc Postman:

```bash
curl -X GET "http://localhost:8000/feed/{user_id}?limit=5&_k=0" \
  -H "Authorization: Bearer {token}"
```

Xác nhận nhận được tối đa 5 video, không có `NS_BINDING_ABORTED`.

#### Bước A5: Build & kiểm tra request

```bash
cd frontend && npm run dev
```

Mở DevTools (Network tab), xác nhận:
- URL **không chứa `&exclude=...` nữa**
- URL dài < 200 characters
- Response là mảng 5 video

#### Bước A6: Verify ở tất cả device

Test trên:
- Desktop Chrome/Firefox
- Mobile Chrome
- ...

---

### PHẦN B: Fix 2B (Detect end-of-content khi batch < BATCH_SIZE)

#### Bước B1: Thêm state tracking "hết dữ liệu"

Đường dẫn: `frontend/src/App.tsx`

Tìm phần declare state:

```tsx
// Line ~80 (giả định)
const [accumulatedVideos, setAccumulatedVideos] = useState<Video[]>([]);
const [feedFetchKey, setFeedFetchKey] = useState(0);
// ← Thêm state mới
const [hasMoreContent, setHasMoreContent] = useState(true);
```

#### Bước B2: Cập nhật logic accumulation

Tìm `useEffect` xử lý `currentVideos`:

```tsx
// TRƯỚC (line ~150)
useEffect(() => {
  if (currentVideos && currentVideos.length > 0) {
    setAccumulatedVideos(prev => {
      const newVids = currentVideos.filter(cv => 
        !prev.find(p => p.id === cv.id)
      );
      if (newVids.length > 0) {
        hasFetchedNextBatch.current = false;
      }
      return newVids.length > 0 ? [...prev, ...newVids] : prev;
    });
  }
}, [currentVideos]);
```

Thành:

```tsx
// SAU
useEffect(() => {
  if (currentVideos) {
    if (currentVideos.length > 0) {
      setAccumulatedVideos(prev => {
        const newVids = currentVideos.filter(cv => 
          !prev.find(p => p.id === cv.id)
        );
        if (newVids.length > 0) {
          hasFetchedNextBatch.current = false;
        }
        
        // 🔑 KEY: Nếu backend trả < BATCH_SIZE → hết content
        if (currentVideos.length < BATCH_SIZE) {
          setHasMoreContent(false);
        }
        
        return newVids.length > 0 ? [...prev, ...newVids] : prev;
      });
    } else if (currentVideos.length === 0) {
      // Backend trả rỗng → chắc chắn hết dữ liệu
      setHasMoreContent(false);
    }
  }
}, [currentVideos]);
```

**Context đầy đủ (10 dòng):**
```tsx
// Line 145
  useEffect(() => {
    if (currentVideos) {
      if (currentVideos.length > 0) {
        setAccumulatedVideos(prev => {
          const newVids = currentVideos.filter(cv => 
            !prev.find(p => p.id === cv.id)
          );
          if (newVids.length > 0) {
            hasFetchedNextBatch.current = false;
          }
          // ← ADD HERE
          if (currentVideos.length < BATCH_SIZE) {
            setHasMoreContent(false);
          }
          return newVids.length > 0 ? [...prev, ...newVids] : prev;
        });
      } else {
        setHasMoreContent(false);
      }
    }
  }, [currentVideos]);
```

#### Bước B3: Cập nhật onLoadMore guard

Tìm `onLoadMore` và thêm check `hasMoreContent`:

```tsx
// TRƯỚC
const onLoadMore = useCallback(() => {
  if (hasFetchedNextBatch.current) return;  // ← Guard chỉ có cái này
  // ...
}, [user]);
```

Thành:

```tsx
// SAU
const onLoadMore = useCallback(() => {
  if (hasFetchedNextBatch.current || !hasMoreContent) return;  // ← Thêm hasMoreContent
  hasFetchedNextBatch.current = true;
  if (user) {
    setFeedFetchKey(prev => prev + 1);
  }
}, [user, hasMoreContent]);  // ← Thêm hasMoreContent dependency
```

#### Bước B4: Test lại flow

```bash
cd frontend && npm run dev
```

Kịch bản test:
1. Scroll feed tới cuối (tất cả 246 video)
2. Verify `hasMoreContent = false` sau khi load xong
3. scroll tới bottom không gọi API lưới (DevTools Network tab)

---

## ✅ BUG 2: Acceptance Criteria

| Criteria | Trạng thái | Ghi chú |
|----------|-----------|--------|
| URL `/feed?` không chứa `&exclude=...` | ✅ Required | Loại bỏ long query param |
| `onLoadMore()` gọi `setFeedFetchKey()` thay vì `setExcludeIds()` | ✅ Required | Backend xử lý dedup qua Redis |
| Tồn tại state `hasMoreContent` | ✅ Required | Track khi có dữ liệu tiếp theo |
| `useEffect` kiểm tra `currentVideos.length < BATCH_SIZE` | ✅ Required | Detect end-of-batch |
| `onLoadMore()` có guard: `!hasMoreContent` | ✅ Required | Ngăn n API call vô ích |
| API call khi batch < BATCH_SIZE được hủy (1 lần duy nhất) | ✅ Verification | Scroll tới cuối, kiểm tra Network tab |
| 246 video được tải xong (không dừng ở 242) | ✅ Verification | Manual test trên feed |

---

## 🐛 BUG 3: Desktop Freeze — 2GB Transferred, GPU/VRAM Exhaustion

### Nguyên nhân gốc - Chi tiết ba phần

#### 3A: GPU Decoder Leak

Khi user scroll ra khỏi viewport:
```
VideoCard: isInWindow = true → false
React: <video /> → <div />
Browser: Xoá DOM node ✅
nhưng: GPU decoder vẫn xử lý texture buffer nếu cleanup chạy muộn
Kết quả: 242 video → 242 GPU decoder instances accumulate → VRAM tràn
```

#### 3B: Network Bandwidth Leak

```tsx
// VideoCard.tsx
const REAL_VIDEO_URLS = [url1, url2, url3, url4, url5];
const getRealVideoUrl = (index) => REAL_VIDEO_URLS[index % 5];
```

- 242 card → 5 URL loop: url1, url2, url3, url4, url5, url1, url2, ...
- Mỗi card tạo `<video>`mới → browser re-load từ server
- Khi scroll back vào viewport, `<video>` tạo lại, tải lại file (không cache được)
- **2GB = 242 video × 8MB × 1.05 re-download factor**

#### 3C: React Component Instances Leak

```tsx
{videos.map(v => <VideoCard />)}  // 242 instances
```

- 242 React component instances giữ trong memory
- 242 `useState`, 242 `useRef`, 242 `useEffect` hooks
- 242 WebSocket subscriptions (nếu `useVideoStats` không có guard)
- **Total: ~100MB+ chỉ cho React overhead**

---

## 📌 BUG 3: Implementation Steps (FIX 3A)

### Bước 3A-1: Mở VideoCard.tsx

Đường dẫn: `frontend/src/components/VideoCard.tsx`

### Bước 3A-2: Tìm code render video

Tìm dòng render:

```tsx
{isInWindow ? (
  <video ref={setRefs} ... />
) : (
  <div className="..." />
)}
```

### Bước 3A-3: Thêm cleanup effect cho GPU

Thêm `useEffect` mới **(RIÊNG)**:

```tsx
// Aggressive GPU cleanup khi ra khỏi viewport (Add after line 280)
useEffect(() => {
  if (!isInWindow && videoRef.current) {
    const video = videoRef.current;
    
    // 1. Dừng playback
    video.pause();
    
    // 2. Clear source → signal browser stop download
    video.removeAttribute('src');
    
    // 3. Force release GPU decoder + texture
    video.load();
    
    // 4. Clear crossorigin preload (nếu có)
    video.preload = 'none';
  }
}, [isInWindow]);
```

**Context đầy đủ (10 dòng trước/sau):**

```tsx
// Line 275 - code hiện tại
  if (hlsRef.current) {
    hlsRef.current.destroy();
    hlsRef.current = null;
  }
}, [someExistingDeps]);

// ← INSERT NEW: useEffect GPU cleanup ở đây (line 285)
useEffect(() => {
  if (!isInWindow && videoRef.current) {
    const video = videoRef.current;
    video.pause();
    video.removeAttribute('src');
    video.load();
    video.preload = 'none';
  }
}, [isInWindow]);

// Line 295 - code tiếp tục
return (
  <div ref={inViewRef} className="w-full h-full relative">
```

### Bước 3A-4: Verify videoRef declaration

Kiểm tra `videoRef` được declare:

```tsx
const videoRef = useRef<HTMLVideoElement>(null);
```

Nếu sử dụng callback ref, convert sang `useRef`:

```tsx
// CŨ (callback)
let videoRefElement: HTMLVideoElement | null = null;
const setRefs = (el: HTMLVideoElement) => {
  videoRefElement = el;
};

// MỚI (useRef)
const videoRef = useRef<HTMLVideoElement>(null);
// Trong JSX: ref={videoRef}
```

### Bước 3A-5: Build & kiểm tra cleanup

```bash
cd frontend && npm run dev
```

### Bước 3A-6: Verify GPU cleanup xảy ra

Công cụ xác nhận (tuỳ theo brower):

**Chrome DevTools:**
- Mở DevTools → Performance tab
- Record 10 giây scroll feed
- Xem flamegraph: GPU time nên giảm khi video ra khỏi window

**Firefox DevTools:**
- Mở DevTools → Memory tab
- Take snapshot trước/sau scroll
- Xem retained objects: `HTMLVideoElement` nên giảm

---

## 📌 BUG 3: Implementation Steps (FIX 3B - DOM Virtualization)

### Bước 3B-1: Mở Feed.tsx

Đường dẫn: `frontend/src/components/Feed.tsx`

### Bước 3B-2: Xác định activeIndex

Tìm cách xác định video nào đang "active" (được xem):

**Option 1: Dùng snap scroll position**
```tsx
const [activeIndex, setActiveIndex] = useState(0);
const handleScroll = (e) => {
  const scrollPosition = e.currentTarget.scrollLeft;
  const index = Math.round(scrollPosition / videoHeight);
  setActiveIndex(index);
};
```

**Option 2: Dùng IntersectionObserver**
```tsx
const [activeIndex, setActiveIndex] = useState(0);

useEffect(() => {
  const observer = new IntersectionObserver(
    (entries) => {
      const activeEntry = entries.find(e => e.isIntersecting);
      if (activeEntry) {
        const index = videos.findIndex(v => v.id === activeEntry.target.id);
        setActiveIndex(index);
      }
    },
    { threshold: 0.5 }
  );
  
  videoRefs.current.forEach(ref => observer.observe(ref));
  return () => observer.disconnect();
}, [videos]);
```

Chọn **Option nào dễ implement nhất** trong codebase hiện tại.

### Bước 3B-3: Thêm RENDER_WINDOW constant

```tsx
// Line 1 (top of Feed.tsx)
const RENDER_WINDOW = 5; // Chỉ render ±5 cards xung quanh active
```

### Bước 3B-4: Refactor video map logic

Tìm code render video (thường là line ~150):

```tsx
// TRƯỚC
{videos.map((video, index) => (
  <VideoCard key={video.id} index={index} video={video} />
))}
```

Thành:

```tsx
// SAU - DOM virtualization
{videos.map((video, index) => {
  // Nếu card quá xa activeIndex → không render component (chỉ render placeholder div)
  if (Math.abs(index - activeIndex) > RENDER_WINDOW) {
    return (
      <div
        key={video.id}
        className="w-full shrink-0 snap-start bg-black"
        style={{ height: '100vh' }}  // Giữ scroll height bình thường
      >
        {/* Placeholder - không có <video> */}
      </div>
    );
  }

  // Cards gần activeIndex → render VideoCard bình thường
  return (
    <VideoCard 
      key={video.id} 
      index={index} 
      video={video}
      activeIndex={activeIndex}
    />
  );
})}
```

**Context đầy đủ (10 dòng):**
```tsx
// Line 145
  const videoRefs = useRef<(HTMLDivElement | null)[]>([]);
  
  // ... (code hiện tại)
  
  // Line 160 - Render section
  <div className="feed-container">
    {videos.map((video, index) => {
      if (Math.abs(index - activeIndex) > RENDER_WINDOW) {
        return (
          <div
            key={video.id}
            className="w-full shrink-0 snap-start bg-black"
            style={{ height: '100vh' }}
          />
        );
      }
      return <VideoCard key={video.id} index={index} video={video} />;
    })}
  </div>
```

### Bước 3B-5: Test virtualization

```bash
cd frontend && npm run dev
```

Tùy từng frame (50 card mỗi frame):
1. **Trước:** 50 `<VideoCard>` render → 50 `<video>` DOM nodes (chỉ 5 visible)
2. **Sau:** ~11 `<VideoCard>` render (5 trước + 1 active + 5 sau) + 39 placeholder `<div>`

Verify trong DevTools:
```
Elements tab → Count `<video>` elements
- Trước fix: 50 `<video>`
- Sau fix:  5 `<video>` (chỉ trong RENDER_WINDOW)
```

### Bước 3B-6: Verify scroll smoothness

Scroll nhanh, xác nhận:
- Scroll vẫn smooth (không stutter)
- Placeholder div giữ height → scroll position không nhảy
- VideoCard unmount/remount khi scroll

---

## 📌 BUG 3: Implementation Steps (FIX 3C - Cap Accumulated Videos)

### Bước 3C-1: Xác định MAX_ACCUMULATED

Quyết định: giữ tối đa bao nhiêu video trong `accumulatedVideos` state?

**Khuyến nghị:** `MAX_ACCUMULATED = 50` (50 cards = ~5-10 lần load)

### Bước 3C-2: Thêm constant

```tsx
// App.tsx - Line 80
const BATCH_SIZE = 5;
const MAX_ACCUMULATED = 50;  // ← Thêm dòng này
```

### Bước 3C-3: Cập nhật accumulation logic

Tìm `setAccumulatedVideos` (thường trong `useEffect` xử lý `currentVideos`):

```tsx
// TRƯỚC (line ~160)
setAccumulatedVideos(prev => {
  const newVids = currentVideos.filter(cv => 
    !prev.find(p => p.id === cv.id)
  );
  if (newVids.length > 0) {
    hasFetchedNextBatch.current = false;
  }
  return newVids.length > 0 ? [...prev, ...newVids] : prev;
});
```

Thành:

```tsx
// SAU
setAccumulatedVideos(prev => {
  const newVids = currentVideos.filter(cv => 
    !prev.find(p => p.id === cv.id)
  );
  if (newVids.length > 0) {
    hasFetchedNextBatch.current = false;
  }
  
  // 🔑 KEY: Cap total accumulated videos
  const combined = newVids.length > 0 ? [...prev, ...newVids] : prev;
  
  if (combined.length > MAX_ACCUMULATED) {
    // Giữ lại ~50 videos gần nhất
    // Start từ end - MAX_ACCUMULATED
    const sliceStart = combined.length - MAX_ACCUMULATED;
    return combined.slice(sliceStart);
  }
  
  return combined;
});
```

**Context đầy đủ (12 dòng):**
```tsx
// Line 155
  setAccumulatedVideos(prev => {
    const newVids = currentVideos.filter(cv => 
      !prev.find(p => p.id === cv.id)
    );
    if (newVids.length > 0) {
      hasFetchedNextBatch.current = false;
    }
    
    const combined = newVids.length > 0 ? [...prev, ...newVids] : prev;
    
    if (combined.length > MAX_ACCUMULATED) {
      const sliceStart = combined.length - MAX_ACCUMULATED;
      return combined.slice(sliceStart);
    }
    
    return combined;
  });
```

### Bước 3C-4: ⚠️ Cân nhắc: Adjust activeIndex

Nếu cap `accumulatedVideos` từ trái (slice start), `activeIndex` có thể mismatch.

**Nếu sử dụng activeIndex = position theo mảng:**
```tsx
// Khi cap từ left, cần adjust activeIndex:
const slicedVideos = combined.slice(sliceStart);
const newActiveIndex = Math.max(0, activeIndex - sliceStart);
setActiveIndex(newActiveIndex);
setAccumulatedVideos(slicedVideos);
```

**Nếu dùng `findIndex` dựa video.id:** Không cần adjust (code tự tìm).

### Bước 3C-5: Build & test

```bash
cd frontend && npm run dev
```

Scroll feed đến 100+ video:
- Kiểm tra `accumulatedVideos.length` không vượt quá 50
- DevTools Elements: `<VideoCard>` components không tăng vô hạn

### Bước 3C-6: Verify memory usage

Scroll 200+ videos, kiểm tra:
- Desktop không freeze
- Performance tab: memory usage ổn định (không tăng linear)

---

## ✅ BUG 3: Acceptance Criteria

### Fix 3A (GPU Cleanup)

| Criteria | Trạng thái | Ghi chú |
|----------|-----------|--------|
| `useEffect` với `[isInWindow]` dependency tồn tại | ✅ Required | Separate effect từ cleanup cũ |
| Gọi `video.pause()` khi `!isInWindow` | ✅ Required | Dừng playback |
| Gọi `video.removeAttribute('src')` | ✅ Required | Signal browser stop download |
| Gọi `video.load()` | ✅ Required | Release GPU decoder |
| Chrome DevTools Performance: GPU time giảm khi scroll | ✅ Verification | Record 10s scroll |

### Fix 3B (DOM Virtualization)

| Criteria | Trạng thái | Ghi chú |
|----------|-----------|--------|
| `activeIndex` state được track (snap or observer) | ✅ Required | Know which video is active |
| `RENDER_WINDOW = 5` constant tồn tại | ✅ Required | ±5 cards margin |
| Placeholder `<div>` render cho cards ngoài window | ✅ Required | Maintain scroll height |
| VideoCard unmount khi > RENDER_WINDOW | ✅ Required | Reduce React instances |
| DevTools Elements: 5 `<video>` thay vì 50 | ✅ Verification | Count video elements |
| Scroll vẫn smooth sau virtualization | ✅ Verification | Manual scroll test |

### Fix 3C (Cap Accumulated)

| Criteria | Trạng thái | Ghi chú |
|----------|-----------|--------|
| `MAX_ACCUMULATED = 50` constant tồn tại | ✅ Required | Cap limit |
| `setAccumulatedVideos` check `combined.length > MAX_ACCUMULATED` | ✅ Required | Slice when over |
| `combined.slice(start)` được gọi | ✅ Required | Remove old videos |
| `activeIndex` được adjust nếu cần | ✅ Conditional | Tuỳ implementation |
| Scroll 200+ videos: không freeze | ✅ Verification | 1-2 phút test |
| Memory usage ổn định sau ~100 videos | ✅ Verification | DevTools Memory snapshot |

---

## 🔄 Verification Flow: Fix 3A → 3B → 3C tuần tự

### Sau khi hoàn thành Fix 3A:

```bash
# 1. Build
cd frontend && npm run dev

# 2. Scroll feed ~20 videos
# DevTools Performance → check GPU time drops when scroll

# 3. Check logs (không có GPU decoder leak)
```

### Sau khi hoàn thành Fix 3B:

```bash
# 1. Build
cd frontend && npm run dev

# 2. Scroll feed ~50 videos  
# DevTools Elements → count <video> elements
# Should be: 5 (not 50)

# 3. Check scroll smoothness
```

### Sau khi hoàn thành Fix 3C:

```bash
# 1. Build
cd frontend && npm run dev

# 2. Scroll feed ~300 videos
# DevTools → accumulatedVideos.length should stay <= 50
# Memory Usage should plateau

# 3. Check desktop performance
# Should not freeze (before: freeze at ~200 videos)
```

---

## 📊 Tóm tắt Implementation Order

```
═══════════════════════════════════════════════════════════════
BUG 3 (CRITICAL) - Fix 3A → Fix 3B → Fix 3C
  ↓
BUG 2 (HIGH) - Fix 2A → Fix 2B
  ↓
BUG 1 (MEDIUM) - Fix 1
═══════════════════════════════════════════════════════════════
```

### Dự kiến hoàn thành

| Fix | Độ phức tạp | Thời gian ước tính | Dependencies |
|-----|-----------|------------------|--------------|
| 3A | Trung bình | 30 phút | Không |
| 3B | Cao | 1 giờ | 3A (khác không bắt buộc) |
| 3C | Thấp | 20 phút | 3A, 3B (khác không bắt buộc) |
| 2A | Trung bình | 45 phút | Không (nhưng nên trước 2B) |
| 2B | Thấp | 30 phút | 2A (recommended) |
| 1  | Thấp | 20 phút | Không |
| **TOTAL** | | **~3 giờ** | |

---

## 🛠️ Debugging Tips

### Nếu Fix 3A không giảm GPU memory:

1. Kiểm tra `videoRef.current` có tồn tại không
2. Thêm `console.log("GPU cleanup called")` trong effect
3. Kiểm tra browser có support `video.removeAttribute('src')`

### Nếu Fix 3B gây scroll bị jump:

1. Verify placeholder `<div>` có `height: 100vh`
2. Check `activeIndex` được update đúng khi scroll
3. Log activeIndex + RENDER_WINDOW range

### Nếu Fix 3C làm lastFeed không hiển thị:

1. Kiểm tra `activeIndex` adjustment logic
2. Đảm bảo `newVids` không bị mất khi slice
3. Kiểm tra `hasMoreContent` logic còn đúng sau khi cap

---

## ✅ Cuối cùng: Verification Checklist

Sau khi implement **tất cả 6 fixes**, chạy:

```bash
# 1. Build frontend
cd frontend && npm run dev

# 2. Scroll 300+ videos
# Check:
# - Không freeze
# - Memory usage ổn định
# - accumulatedVideos.length <= 50
# - <video> count = 5

# 3. Kiểm tra minor issues
# - NS_BINDING_ABORTED không hiện
# - Feed tới 246 video (không dừng)
# - Scroll smooth

# 4. Kiểm tra API calls
# DevTools Network:
#  - Không có URL param quá dài
#  - Không có duplicate request khi batch < BATCH_SIZE
```

---

## 🎯 Hết! Sẵn sàng để AI implement

Document này đã được tổ chức lại với:
✅ 5-7 atomic steps per fix  
✅ Full code context (8-12 dòng)  
✅ Acceptance criteria rõ ràng  
✅ Verification steps cụ thể  
✅ Dependency graph  
✅ Tiếng Việt hoàn toàn

Hãy bắt đầu từ **Fix 3A** (GPU Cleanup)! 🚀

## Bug 1: NS_BINDING_ABORTED

### Giải thích

`NS_BINDING_ABORTED` là mã lỗi **Firefox-specific** (Chrome hiện tương đương `ERR_ABORTED`). Nó xảy ra khi:

```
Browser đang download segment video (.mp4 hoặc .m4s chunk)
    → User scroll → sliding window đổi: isInWindow = false
    → React render: <video> → <div> (placeholder)
    → Video element bị unmount → browser huỷ HTTP kết nối đang mở
    → NS_BINDING_ABORTED
```

**Đây KHÔNG phải lỗi nghiêm trọng** — nó là hành vi đúng của sliding window. Browser huỷ download cho video user đã lướt qua. Tuy nhiên, nếu segment chưa load đủ trước khi bị huỷ → có thể gây flicker khi quay lại.

### Fix

```
File: frontend/src/components/VideoCard.tsx
```

**Hiện tại:** Khi `isInWindow` chuyển `false`, `<video>` bị unmount ngay lập tức → browser abort giữa chừng.

**Giải pháp:** Trước khi unmount `<video>`, chủ động stop loading:

```tsx
// Trong useEffect cleanup ([isInWindow] dependency):
return () => {
  if (videoRef.current) {
    videoRef.current.pause();
    videoRef.current.removeAttribute('src');    // ← Chủ động clear source
    videoRef.current.load();                    // ← Force browser release buffers
  }
  if (hlsRef.current) {
    hlsRef.current.destroy();
    hlsRef.current = null;
  }
};
```

**Kết quả:** Browser nhận tín hiệu "stop" trước khi DOM bị xoá → không còn NS_BINDING_ABORTED vì không còn in-flight request bị abort.

---

## Bug 2: Feed dừng ở 242/246 (Thiếu 4 video cuối)

### Nguyên nhân gốc: Pipeline cứng `limit=5` + Backend trả `[]`

**Luồng hiện tại:**

```
User đang xem video 240/242 (đã accumulated 242 video)
  → Feed.handleScroll: candidateIndex >= videos.length - 2
  → onLoadMore() → setExcludeIds([...242 ids]) + setFeedFetchKey(prev+1)
  → SWR fetch: GET /feed/{userId}?limit=5&exclude=...242ids...
  → Backend: vector_search + $nin(242 ids) → chỉ còn 4 video
  → Backend pipeline trả về 4 video (< limit=5)
  → FE: accumulatedVideos grows to 246
  → User xem đến video 244/246
  → Feed.handleScroll: candidateIndex(244) >= videos.length(246) - 2 = 244 ✅
  → onLoadMore() fires lần nữa
  → Backend: exclude 246 → 0 video còn → trả về []
  → FE: currentVideos = [] → filter → newVids = [] → hasFetchedNextBatch stays true
  ✅ Đến đây hoạt động đúng
```

**VẤN ĐỀ THỰC SỰ:** Xem kỹ lại logic accumulation:

```tsx
// App.tsx line 154-165
useEffect(() => {
  if (currentVideos && currentVideos.length > 0) {   // ← GUARD: length > 0
    setAccumulatedVideos(prev => {
      const newVids = currentVideos.filter(cv => !prev.find(p => p.id === cv.id));
      if (newVids.length > 0) {
        hasFetchedNextBatch.current = false;          // ← Reset guard
      }
      return newVids.length > 0 ? [...prev, ...newVids] : prev;
    });
  }
}, [currentVideos]);
```

Khi backend trả 4 video (< 5), **`hasFetchedNextBatch` vẫn được reset** (line 160). Nên bug thực sự là **backend trả `[]` thay vì 4 video** khi còn 4.

Kiểm tra backend pipeline: `vector_search` có `$limit: limit` ở cuối. Với `limit=5`, nó fetch `vs_limit = limit + num_exclude = 5 + 242 = 247`. Nhưng nếu DB chỉ có 246 video → `$vectorSearch` trả tối đa 246 → post-filter `$nin`(242) → còn 4 → `$limit 5` → output 4. **Đây hoạt động đúng.**

**Vậy bug thực sự ở đâu?** Rất có thể là **SWR caching**. URL tạo ra:

```
GET /feed/{userId}?limit=5&exclude=id1,id2,...,id242&_k=48
```

Nếu `excludeIds` quá dài (242 IDs × ~24 chars = **~5.8KB chỉ riêng exclude param**), request có thể:
1. **Bị cắt bởi URL length limit** (browser 2048-8192 chars tuỳ loại)
2. **SWR cache key quá dài** → hashing issue
3. **Backend parse lỗi** → trả `[]`

### Fix (2 phần)

#### Fix 2A: Chuyển exclude sang POST body (thay vì GET query param)

```
File: frontend/src/api/client.ts — usePersonalizedFeed
File: backend/app/controllers/feed_controller.py
```

**Hiện tại:**
```
GET /feed/{userId}?limit=5&exclude=id1,id2,...,id242&_k=48
```

**Sau fix:**
```
POST /feed/{userId}  body: { limit: 5, exclude: ["id1", ...], _k: 48 }
```

Hoặc đơn giản hơn — **không cần gửi exclude nữa** vì backend đã có Redis seen-set:

```tsx
// App.tsx onLoadMore — bỏ setExcludeIds, chỉ bump fetchKey
onLoadMore={() => {
  if (hasFetchedNextBatch.current) return;
  hasFetchedNextBatch.current = true;
  if (user) {
    setFeedFetchKey(prev => prev + 1);  // Backend dùng Redis dedup
  } else {
    setTrendingLimit(prev => prev + BATCH_SIZE);
  }
}}
```

#### Fix 2B: Backend trả partial batch thay vì `[]`

```
File: backend/app/services/feed_service.py — get_feed()
```

Hiện tại khi còn < `limit` videos, backend vẫn trả đúng số lượng còn lại. **Nhưng FE cần xử lý trường hợp batch < BATCH_SIZE:**

```tsx
// App.tsx — thêm "end of content" detection
const [hasMoreContent, setHasMoreContent] = useState(true);

useEffect(() => {
  if (currentVideos && currentVideos.length > 0) {
    setAccumulatedVideos(prev => {
      const newVids = currentVideos.filter(cv => !prev.find(p => p.id === cv.id));
      if (newVids.length > 0) {
        hasFetchedNextBatch.current = false;
      }
      // Nếu backend trả ít hơn BATCH_SIZE → hết content
      if (currentVideos.length < BATCH_SIZE) {
        setHasMoreContent(false);
      }
      return newVids.length > 0 ? [...prev, ...newVids] : prev;
    });
  } else if (currentVideos && currentVideos.length === 0) {
    // Backend trả rỗng → chắc chắn hết
    setHasMoreContent(false);
  }
}, [currentVideos]);

// Trong onLoadMore guard:
onLoadMore={() => {
  if (hasFetchedNextBatch.current || !hasMoreContent) return;
  // ...
}}
```

---

## Bug 3: Desktop Freeze — 2GB Transferred, GPU/VRAM Exhaustion

### Giải thích chi tiết

Đây là bug **NGHIÊM TRỌNG NHẤT**. Nguyên nhân:

#### 3A. DOM leak — 242 `<video>` elements vẫn tồn tại

Sliding window chuyển `<video>` → `<div>` placeholder khi nằm ngoài `±WINDOW_SIZE`. **ĐÚNG.** Nhưng vấn đề:

```tsx
// VideoCard.tsx line 311-330
{isInWindow ? (
  <video ref={setRefs} ... />    // ← Tạo video element
) : (
  <div ref={inViewRef} ... />    // ← Placeholder
)}
```

Khi `isInWindow` chuyển `false`:
1. React unmount `<video>` → OK, DOM node bị xoá
2. **NHƯNG** browser có thể **chưa release GPU texture/decoder** ngay lập tức
3. Đặc biệt với HLS: `hlsRef.current` chỉ được destroy trong `useEffect` cleanup — nếu cleanup chạy muộn (React batching), HLS worker vẫn hoạt động

#### 3B. Network bandwidth — 5 video URLs giống nhau tải lại liên tục

```tsx
const REAL_VIDEO_URLS = [
  'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
  // ... 5 URLs
];

const getRealVideoUrl = (url: string, index: number): string => {
  return REAL_VIDEO_URLS[index % REAL_VIDEO_URLS.length];  // ← 5 URLs lặp lại
};
```

242 video cards → 242 requests → nhưng chỉ 5 unique URLs. **Browser cache** nên handle, nhưng:
- Mỗi lần `<video>` được tạo lại (scroll back vào window) → browser **re-validate cache** (conditional GET) hoặc **tải lại hoàn toàn** nếu `src` bị `removeAttribute` trong cleanup
- 2GB transferred = ~242 × (~8MB mỗi video) → mỗi video được tải lại ~4 lần

#### 3C. Accumulated DOM nodes — React giữ 242 component instances

```tsx
// Feed.tsx line 161
{videos.map((video, index) => (
  <VideoCard key={video.id} ... />   // ← 242 instances!
))}
```

Dù chỉ 5 cards hiện `<video>`, **242 React component instances** vẫn tồn tại:
- 242 `useEffect` hooks
- 242 `useState` instances  
- 242 `useRef` instances
- 242 `useVideoStats` WebSocket subscriptions (nếu `isActive` guard không đủ)

### Fix (3 phần)

#### Fix 3A: Aggressive resource cleanup khi ra khỏi window

```
File: frontend/src/components/VideoCard.tsx
```

```tsx
// Thêm cleanup effect riêng cho window transition
useEffect(() => {
  if (!isInWindow && videoRef.current) {
    // Force release GPU resources TRƯỚC KHI React unmount <video>
    const video = videoRef.current;
    video.pause();
    video.removeAttribute('src');
    video.load();  // ← Trigger browser to release decoder + texture
  }
}, [isInWindow]);
```

#### Fix 3B: DOM virtualization — chỉ render ±N cards trong DOM

```
File: frontend/src/components/Feed.tsx
```

Thay vì render ALL 242 cards (kể cả placeholder `<div>`):

```tsx
const RENDER_WINDOW = 5; // Chỉ render ±5 cards xung quanh activeIndex

{videos.map((video, index) => {
  // Cards quá xa → không render gì cả (kể cả placeholder)
  if (Math.abs(index - activeIndex) > RENDER_WINDOW) {
    return (
      <div
        key={video.id}
        className="w-full shrink-0 snap-start"
        style={{ height: '100%' }}  // Giữ scroll height
      />
    );
  }

  return (
    <VideoCard key={video.id} index={index} ... />
  );
})}
```

**Hiệu quả:** Từ 242 React component instances → chỉ 11 (5 trước + 1 active + 5 sau).

#### Fix 3C: Limit total accumulated videos — cap DOM list

```
File: frontend/src/App.tsx hoặc Feed.tsx
```

Nếu user đã lướt 200+ videos, giữ tối đa N videos gần nhất trong state:

```tsx
const MAX_ACCUMULATED = 50; // Giới hạn DOM nodes

// Trong accumulateVideos logic:
setAccumulatedVideos(prev => {
  const combined = [...prev, ...newVids];
  if (combined.length > MAX_ACCUMULATED) {
    // Giữ lại videos xung quanh activeIndex
    const start = Math.max(0, activeIndex - 10);
    return combined.slice(start, start + MAX_ACCUMULATED);
  }
  return combined;
});
```

> ⚠️ Cách này cần cẩn thận với `activeIndex` offset — sẽ cần adjust index mapping.

---

## ✅ Checklist triển khai

| # | Task | File(s) | Priority | Status |
|---|------|---------|----------|--------|
| 1 | Cleanup video src trước unmount (fix NS_BINDING_ABORTED) | `VideoCard.tsx` | P2 | ⬜ |
| 2 | Detect end-of-content khi batch < BATCH_SIZE | `App.tsx` | P1 | ⬜ |
| 3 | Bỏ exclude IDs khỏi URL (dùng Redis dedup thay thế) **HOẶC** chuyển sang POST | `client.ts` + `feed_controller.py` | P1 | ⬜ |
| 4 | DOM virtualization — chỉ render ±N cards | `Feed.tsx` | P0 | ⬜ |
| 5 | Aggressive GPU cleanup khi exit window | `VideoCard.tsx` | P0 | ⬜ |
| 6 | Cap total accumulated videos | `App.tsx` | P1 | ⬜ |

### Thứ tự triển khai khuyến nghị

```
P0: Bug 3 (Desktop freeze) → Fix 3A + 3B trước
P1: Bug 2 (Feed stops) → Fix 2A hoặc 2B
P2: Bug 1 (NS_BINDING_ABORTED) → Fix 1 (sẽ được giải quyết phần lớn bởi Fix 3A)
```

---

## 📊 Dự kiến impact

| Metric | Trước fix | Sau fix |
|--------|-----------|---------|
| DOM nodes | 242 VideoCard + 237 `<div>` + 5 `<video>` | 11 VideoCard + 6 `<div>` + 5 `<video>` |
| React instances | 242 | 11 |
| GPU decoders active | 5 (window) + leaked từ cũ | 5 (clean) |
| Network transferred | ~2GB (re-downloads) | ~40MB (cache-friendly) |
| Desktop freeze | Có (sau ~200 videos) | Không |
