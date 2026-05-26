# 📊 Analytics Dashboard — Implementation Plan

**Ngày:** 26/05/2026
**Scope:** Tạo màn hình Dashboard để demo cho BGK thấy real-time data của hệ thống

---

## 1. Phân tích hiện trạng

### Những gì đã có sẵn (Tái sử dụng được)

| Thứ | Mô tả | Cần bổ sung |
|---|---|---|
| `getSession(sessionId)` | Đã có API, trả về `fatigue_score`, `adaptive_state`, `total_videos_watched` | Không |
| `/ws/stats/{session_id}` | WebSocket broadcast khi video counter thay đổi | Không |
| Fatigue Bar trên FE | Đang hiển thị `fatigueScore` live | Không |
| `isMindfulActive` state | Biết khi nào phase 3 kích hoạt | Không |
| Nút "Lướt Vô Thức" | Mô phỏng doomscroll để trigger fatigue | Không |
| Control Panel bên phải | Panel desktop đã có, nhưng chỉ có swipe controls | Cần thêm Analytics |

### Những gì CÒN THIẾU cho dashboard

1. **Không có màn hình riêng** để BGK thấy toàn bộ số liệu một cách trực quan.
2. **Không hiển thị** feed transition log (video nào đã được đổi, tại sao).
3. **Không có biểu đồ** fatigue theo thời gian (timeline).
4. **Không có** thông tin session: số video đã xem, tỉ lệ high/low intensity.

---

## 2. Chiến lược Implement

### Cách tiếp cận: Mở rộng Control Panel hiện có (không tạo trang mới)

**Lý do chọn cách này:**
- Control Panel bên phải (`.hidden md:flex`) đã hiển thị khi desktop → **đây chính là vị trí demo cho BGK**.
- Không cần thêm routing (React Router), không cần backend endpoint mới.
- Tái sử dụng state sẵn có (`fatigueScore`, `isMindfulActive`, `accumulatedVideos`).
- Nhanh hơn ít nhất 2x so với tạo trang riêng.

### Layout đề xuất (thay thế hoàn toàn Control Panel hiện tại)

```
┌──────────────────────────────────────────┐
│ 📊 GoTouchGrass — Live Analytics         │  ← Header
├──────────────────────────────────────────┤
│                                          │
│  🟢 TRẠNG THÁI HỆ THỐNG                 │  ← Section 1: Status Cards
│  ┌──────────┬──────────┬──────────┐      │
│  │ Fatigue  │  Videos  │  Phase   │      │
│  │   82%    │   watched│  EXHAUSTED│     │
│  └──────────┴──────────┴──────────┘      │
│                                          │
│  📈 FATIGUE TIMELINE                    │  ← Section 2: Chart (mini sparkline)
│  [sparkline: 0→15→30→50→82]            │
│                                          │
│  🎯 FEED COMPOSITION                    │  ← Section 3: Video type breakdown
│  High Intensity  ██████░░░░ 6          │
│  Low Intensity   ████████░░ 8          │
│  Calming         ████░░░░░░ 4          │
│                                          │
│  🔀 PHASE TRANSITION LOG                │  ← Section 4: Recent events
│  14:32 Fatigue 70% → Phase 3 ON        │
│  14:31 Video "Rain ASMR" injected      │
│  14:30 Swipe fast detected             │
│                                          │
├──────────────────────────────────────────┤
│ ⚡ DEMO CONTROLS                        │  ← Section 5: Keep demo buttons
│  [Lướt Vô Thức] [Reset Session]        │
│  [Fast↑] [Slow↑] [Fast↓] [Slow↓]      │
└──────────────────────────────────────────┘
```

---

## 3. Chi tiết từng Section

### Section 1: Status Cards (3 cards ngang)

**Data source:** `fatigueScore`, `accumulatedVideos.length`, `isMindfulActive`

```
Card 1: Fatigue Score
  - Giá trị: fatigueScore (0-100)
  - Màu: xanh < 40, vàng 40-70, đỏ > 70
  - Icon: Brain

Card 2: Videos Watched  
  - Giá trị: sessionVideoCount (cần fetch từ getSession().total_videos_watched)
  - Icon: Play

Card 3: Adaptive Phase
  - Giá trị: "NORMAL" / "WARNING" / "EXHAUSTED"
  - Màu theo state
  - Icon: Leaf/Shield
```

**Polling:** `getSession(sessionId)` mỗi 3 giây để cập nhật.

---

### Section 2: Fatigue Timeline (Sparkline Chart)

**Data source:** State mới `fatigueHistory: number[]` — mỗi lần `fatigueScore` thay đổi thì push vào.

**Render:** Không dùng thư viện chart nặng. Dùng SVG polyline đơn giản (tự vẽ).

```tsx
// Ví dụ: [0, 15, 30, 50, 82] → vẽ SVG polyline 200x60px
const points = history.map((v, i) => 
  `${(i / (history.length - 1)) * 200},${60 - (v / 100) * 60}`
).join(' ')
// <polyline points={points} />
```

**Tại sao SVG thay vì Recharts?**
- Không cần cài thêm package.
- Nhẹ hơn, render nhanh hơn.
- Đủ đẹp để demo.

---

### Section 3: Feed Composition Bar

**Data source:** `accumulatedVideos` (đã có trong App.tsx L161) — đếm theo `intensity` field.

```tsx
const highCount = accumulatedVideos.filter(v => v.intensity === 'high').length
const lowCount  = accumulatedVideos.filter(v => v.intensity === 'low').length
const calmCount = accumulatedVideos.filter(v => v.category === 'calming' || v.category === 'nature').length
```

**Render:** Progress bar đơn giản với màu tương ứng.

---

### Section 4: Phase Transition Event Log

**Data source:** State mới `eventLog: string[]` — tự generate message khi:
- `fatigueScore` vượt ngưỡng 40 → push "⚠️ Bước vào trạng thái Warning"
- `fatigueScore` vượt ngưỡng 70 → push "🔥 Phase 3 kích hoạt — Feed đang được can thiệp"
- `isMindfulActive` bật → push "🌿 Palette Cleanser đã được inject vào feed"
- Session reset → push "🔄 Session mới bắt đầu"

**Render:** Danh sách 5 events gần nhất, mới nhất trên đầu, có timestamp.

---

### Section 5: Demo Controls

Giữ nguyên các nút hiện tại, chỉ đổi style nhỏ cho đồng bộ với dashboard.

---

## 4. Các thay đổi cần làm

### 4.1 Frontend — `App.tsx`

| Thay đổi | Mô tả |
|---|---|
| Thêm state `fatigueHistory: number[]` | Lưu lịch sử fatigue score để vẽ sparkline |
| Thêm state `eventLog: string[]` | Lưu log sự kiện phase transition |
| Thêm state `sessionVideoCount: number` | Fetch từ getSession() |
| Sửa `refreshSessionStats()` | Append vào `fatigueHistory` và `eventLog` mỗi lần poll |
| Thêm effect polling mỗi 3s | Gọi `getSession()` → cập nhật toàn bộ dashboard state |

### 4.2 Frontend — Component mới `AnalyticsDashboard.tsx`

Tách toàn bộ Control Panel ra thành component riêng để App.tsx sạch hơn.

**Props:**
```tsx
interface AnalyticsDashboardProps {
  fatigueScore: number
  fatigueHistory: number[]
  isMindfulActive: boolean
  sessionVideoCount: number
  adaptiveState: 'normal' | 'warning' | 'exhausted'
  accumulatedVideos: any[]
  eventLog: string[]
  onSimulateDoomscroll: () => void
  onResetSession: () => void
  onTriggerSwipe: (dir: 'up'|'down', speed: 'slow'|'fast') => void
}
```

### 4.3 Backend — Không cần thay đổi gì

`GET /sessions/{id}` đã trả về `fatigue_score`, `adaptive_state`, `total_videos_watched`. Đủ dùng.

---

## 5. Thứ tự implement

```
Bước 1 (10 phút): Thêm state mới vào App.tsx (fatigueHistory, eventLog, sessionVideoCount)
Bước 2 (5 phút):  Sửa refreshSessionStats() để append vào history + log
Bước 3 (20 phút): Tạo AnalyticsDashboard.tsx với layout đầy đủ
Bước 4 (10 phút): SVG Sparkline chart đơn giản
Bước 5 (5 phút):  Tích hợp vào App.tsx thay thế Control Panel cũ
```

**Ước tính tổng: ~50 phút**

---

## 6. Những gì KHÔNG làm (để tiết kiệm thời gian)

- ❌ Không dùng Recharts / Chart.js / D3 — chỉ SVG thuần
- ❌ Không tạo route `/dashboard` — embed thẳng vào Control Panel desktop
- ❌ Không thêm backend endpoint mới — tái sử dụng `getSession()` hiện có
- ❌ Không làm mobile layout cho dashboard — BGK sẽ xem trên màn hình rộng khi pitch

---

## 7. Kết quả kỳ vọng sau khi hoàn thành

Khi demo cho BGK:
1. Bên trái: màn hình điện thoại với feed video đang chạy.
2. Bên phải: Analytics Dashboard hiển thị real-time:
   - Fatigue đang tăng dần khi lướt nhanh.
   - Sparkline vẽ đường cong fatigue.
   - Event log ghi lại từng bước: "Phase 3 ON → Palette Cleanser injected".
   - Feed composition tự động chuyển từ High → Low intensity.
3. BGK thấy rõ **"hộp đen"** của thuật toán đang hoạt động như thế nào.
