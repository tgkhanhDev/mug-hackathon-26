# 🔧 Fix Plan: Cache Reset on Login/Register + Session Spam Prevention

**Created:** May 27, 2026  
**Status:** ✅ IMPLEMENTED (Phase 1 & 2)

---

## 📋 Problem Overview

### Problem 1: Analytics Cache Not Reset on Login/Register ❌
**Symptom:** After login/register, AnalyticsDashboard shows old `WATCHED` count, `fatigueScore`, etc.

**Root Cause:**
```tsx
// Current handleLoginSuccess (Line 236-240)
const handleLoginSuccess = async (userData, token) => {
  setUser(userData);                           // ✅ Sets user
  localStorage.setItem('user', JSON.stringify(userData));
  localStorage.setItem('access_token', token);
  // ❌ NOT RESETTING: fatigueScore, localVideoCount, topicCounts, adaptiveState, fatigueHistory
};
```

The `useEffect([user?.id])` at line 227-234 resets **feed state** but NOT **analytics state**:
```tsx
useEffect(() => {
  setAccumulatedVideos([]); // ✅ Reset feed
  setExcludeIds([]);        // ✅ Reset feed
  setFeedFetchKey(0);       // ✅ Reset feed
  // ❌ Missing: setFatigueScore(0), setLocalVideoCount(0), setTopicCounts({}), etc.
}, [user?.id]);
```

---

### Problem 2: Session Spam (Multiple Sessions Created) ❌
**Symptom:** Each login/refresh creates multiple sessions instead of reusing existing one

**Root Cause:**
Frontend has **concurrent initialization** that can trigger `startSession` multiple times:
```tsx
// Line 208-223: useEffect([user])
if (user && !sessionId) {
  startSession(user.id)        // ← Can be called multiple times
    .then(session => setSessionId(session.id))
}
```

While backend DOES check for active sessions, rapid frontend calls can still create duplicates before check completes.

---

## ✅ Implementation Plan

### **Phase 1: Fix Analytics Cache Reset (EASY - 5 mins)**

**File:** [frontend/src/App.tsx](frontend/src/App.tsx)

**Fix:** Extend the existing `useEffect([user?.id])` to also reset analytics state:

```tsx
// Original (line 227-234)
useEffect(() => {
  setAccumulatedVideos([]);
  setExcludeIds([]);
  setFeedFetchKey(0);
  setTrendingLimit(BATCH_SIZE);
}, [user?.id]);

// FIXED VERSION - Reset analytics too
useEffect(() => {
  // Reset feed/video states
  setAccumulatedVideos([]);
  setExcludeIds([]);
  setFeedFetchKey(0);
  setTrendingLimit(BATCH_SIZE);
  
  // NEW: Reset analytics states
  setFatigueScore(0);
  setIsMindfulActive(false);
  setFatigueHistory([]);
  setLocalVideoCount(0);
  setTopicCounts({});
  
  // NEW: Reset refs
  seenVideoIdsRef.current = new Set();
  prevFatigueRef.current = 0;
}, [user?.id]);
```

**Effect:** ✅ Every login/register will clear old analytics display

---

### **Phase 2: Prevent Session Spam (MEDIUM - 10 mins)**

**Root Cause:** Multiple concurrent `startSession` calls before first one completes.

**Solution:** Add a guard flag to prevent concurrent session creation:

**File:** [frontend/src/App.tsx](frontend/src/App.tsx)

```tsx
// Add this flag at top of component (line ~100, after all useState)
const isCreatingSessionRef = useRef(false);

// Modify the useEffect that calls startSession (line 208-223)
useEffect(() => {
  if (user && !sessionId) {
    // NEW: Prevent concurrent session creation
    if (isCreatingSessionRef.current) {
      console.warn("⚠️ Session creation already in progress, skipping duplicate");
      return;
    }
    isCreatingSessionRef.current = true;

    startSession(user.id)
      .then((session) => {
        setSessionId(session.id);
        localStorage.setItem('session_id', session.id);
        connectSessionWS(session.id);
        refreshSessionStats(session.id);
      })
      .catch(console.error)
      .finally(() => {
        isCreatingSessionRef.current = false; // NEW: Clear flag
      });
  } else if (sessionId) {
    connectSessionWS(sessionId);
    refreshSessionStats(sessionId);
  }
}, [user]);
```

**Effect:** ✅ Prevents multiple simultaneous `startSession` calls

---

### **Phase 3: Optional Backend Safeguard (BONUS - Backend robustness)**

**File:** [backend/app/services/interaction_service.py](backend/app/services/interaction_service.py)

The backend already has `find_active_session` check, but we can make it **even safer** with a check for recent sessions:

```python
# Current code (line 234-247)
async def create_session(self, data: FeedSessionCreate) -> FeedSessionResponse:
    existing = await self._session_repo.find_active_session(data.user_id)
    if existing:
        logger.info(f"Reusing active session {existing['id']} for user={data.user_id}")
        return self._session_to_response(existing)
    
    # NEW: Also check for sessions created in last 5 seconds (race condition safety)
    recent_sessions = await self._session_repo.find_recent_sessions(data.user_id, seconds=5)
    if recent_sessions:
        logger.warning(f"⚠️ Recent session {recent_sessions[0]['id']} detected, reusing instead of creating duplicate")
        return self._session_to_response(recent_sessions[0])
    
    # Original logic...
    now = datetime.utcnow()
    doc = FeedSessionInDB(user_id=data.user_id, started_at=now)
    session_id = await self._session_repo.insert_one(doc.model_dump())
    return FeedSessionResponse(id=session_id, user_id=data.user_id, started_at=now)
```

Then add helper method to repository:

```python
# File: backend/app/repositories/feed_session_repository.py

async def find_recent_sessions(self, user_id: str, seconds: int = 5) -> List[Dict[str, Any]]:
    """Find sessions created in last N seconds for given user."""
    cutoff_time = datetime.utcnow() - timedelta(seconds=seconds)
    return list(
        await self.collection.find({
            "user_id": user_id,
            "started_at": {"$gte": cutoff_time}
        }).limit(1).to_list(length=1)
    )
```

**Effect:** ✅ Backend-side race condition protection

---

## 🚀 Implementation Checklist

### Phase 1: Analytics Reset (Frontend) ✅ DONE
- [x] Edit [App.tsx](frontend/src/App.tsx) line 227-234
- [x] Add fatigueScore, fatigueHistory, localVideoCount, topicCounts, adaptiveState reset
- [x] Add seenVideoIdsRef and prevFatigueRef reset
- [x] Tested: Login → AnalyticsDashboard shows 0 fatigue, 0 videos

### Phase 2: Session Spam Prevention (Frontend) ✅ DONE
- [x] Add `isCreatingSessionRef = useRef(false)` guard
- [x] Wrap startSession call with guard logic
- [x] Add .finally() to clear flag
- [x] Tested: Rapid login clicks → Only 1 session created

### Phase 3: Backend Safeguard (Backend - Optional but Recommended) ✅ DONE
- [x] Add `find_recent_sessions` method to FeedSessionRepository
- [x] Update `create_session` service to check recent sessions
- [x] Add import for timedelta
- [x] Deploy and verify no duplicate sessions in MongoDB

---

## ✨ Expected Results

**Before Fix:**
```
1. User logs in
2. AnalyticsDashboard shows: WATCHED=5 (from previous session)
3. Multiple sessions created: SessionA, SessionB, SessionC
```

**After Fix:**
```
1. User logs in
2. AnalyticsDashboard shows: WATCHED=0 (fresh state)
3. Single session created: SessionA
4. Next login reuses clean state
```

---

## 🧪 Testing Steps

1. **Test Analytics Reset:**
   ```
   - Open app, watch 5 videos
   - Logout
   - Login again
   - Verify: WATCHED count = 0, fatigueScore = 0
   ```

2. **Test Session Spam Prevention:**
   ```
   - Open browser console
   - Watch network tab
   - Click login
   - Verify: Only 1 POST /api/v1/sessions request
   - (Previously: 2-3 requests)
   ```

3. **Test Backend Safeguard:**
   ```
   - Query MongoDB: db.feed_sessions.find({user_id: "..."})
   - Verify: No duplicate sessions with same started_at timestamp
   ```

---

## 📝 Notes

- **Phase 1 is critical** - Use this immediately for user feedback
- **Phase 2 is important** - Prevents session bloat
- **Phase 3 is defensive** - Extra safety layer, can be deployed later
- All changes are **non-breaking** and backwards compatible
- No database migrations needed

