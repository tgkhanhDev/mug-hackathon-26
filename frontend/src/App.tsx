import { useState, useEffect, useRef, useCallback } from 'react';
import { connectSessionWS, disconnectSessionWS } from './hooks/useVideoStats';
import { useSessionSSE } from './hooks/useSessionSSE';
import { Feed } from './components/Feed';
import { BottomNav } from './components/BottomNav';
import { AuthPopup } from './components/AuthPopup';
import { AuthContext } from './context/AuthContext';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';
import { TouchGrassModal } from './components/TouchGrassModal';
import { FarewellScreen } from './components/FarewellScreen';
import { Sparkles, Brain, Leaf, ShieldAlert } from 'lucide-react';
import {
  useTrendingVideos,
  usePersonalizedFeed,
  startSession,
  endSession,
  sendBehaviorLog,
  sendInteraction
} from './api/client';



function App() {
  const feedRef = useRef<FeedHandle>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Auth state
  const [user, setUser] = useState<{ id: string; username: string } | null>(() => {
    const saved = localStorage.getItem('user');
    if (!saved) return null;
    try {
      const parsed = JSON.parse(saved);
      if (parsed && parsed.id && parsed.username) {
        return parsed;
      }
    } catch (e) {
      // ignore
    }
    return null;
  });
  const [sessionId, setSessionId] = useState<string | null>(() => {
    return localStorage.getItem('session_id');
  });
  const [, setAccessToken] = useState<string | null>(() => {
    return localStorage.getItem('access_token');
  });

  // Fatigue and Adaptive Feed states
  const [fatigueScore, setFatigueScore] = useState(0);
  const [isMindfulActive, setIsMindfulActive] = useState(false);

  // Analytics Dashboard states
  const [fatigueHistory, setFatigueHistory] = useState<number[]>([]);
  const [localVideoCount, setLocalVideoCount] = useState(0);
  const [intensityCounts, setIntensityCounts] = useState<Record<string, number>>({});
  const [adaptiveState, setAdaptiveState] = useState<'normal' | 'warning' | 'exhausted' | 'critical'>('normal');
  const prevFatigueRef = useRef(0);
  // Ref for seen-set dedup: tracks unique videoIds seen this session
  const seenVideoIdsRef = useRef<Set<string>>(new Set());
  // Ref mirror of accumulatedVideos for stable read inside callbacks
  const accumulatedVideosRef = useRef<any[]>([]);

  // Touch Grass 2-stage flow
  const [showTouchGrassModal, setShowTouchGrassModal] = useState(false);
  const [touchGrassStage, setTouchGrassStage] = useState<1 | 2>(1);
  const [showFarewell, setShowFarewell] = useState(false);

  // Refs (tồn tại trong 1 session, reset khi end session/logout)
  const touchGrassWarnedRef = useRef(false);     // đã hiện stage 1 và user chọn "tiếp tục"
  const videoCountAtWarningRef = useRef(0);       // số video đã xem lúc stage 1 bị dismiss
  const stage1ShownRef = useRef(false);           // guard: không show stage 1 lặp lại
  const localVideoCountRef = useRef(0);           // mirror của localVideoCount state

  const handleVideoActivated = useCallback((videoId: string) => {
    if (seenVideoIdsRef.current.has(videoId)) return; // Already counted
    seenVideoIdsRef.current.add(videoId);

    // Look up intensity_level from the video list (read from ref, no closure issue)
    const video = accumulatedVideosRef.current.find((v: any) => v.id === videoId);
    const intensity: string = video?.intensity_level || 'medium';

    setLocalVideoCount(prev => {
      localVideoCountRef.current = prev + 1;
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

  // Pagination / Infinite Scroll states
  // feedLimit is kept CONSTANT — backend dedup ($nin seen_video_ids) ensures each
  // mutateFeed() call returns a fresh batch of BATCH_SIZE videos never seen before.
  const BATCH_SIZE = 5;
  const [feedLimit] = useState(BATCH_SIZE);
  // feedFetchKey: incrementing this changes the SWR cache key, forcing a real
  // network request even when limit stays constant (bypasses SWR cache).
  const [feedFetchKey, setFeedFetchKey] = useState(0);
  const [trendingLimit, setTrendingLimit] = useState(BATCH_SIZE);

  // Track if the initial SWR fetch has happened, so we don't double-fetch
  const hasInitialFeedFetched = useRef(false);

  const [swipeTrigger, setSwipeTrigger] = useState<{ direction: 'up' | 'down'; speed: 'slow' | 'fast'; timestamp: number } | null>(null);

  const triggerSwipe = (direction: 'up' | 'down', speed: 'slow' | 'fast') => {
    setSwipeTrigger({ direction, speed, timestamp: Date.now() });
  };

  // hasFetchedNextBatch: prevents triggering multiple fetches for the same batch.
  // It is reset inside Feed whenever the videos array grows (new batch arrived).
  const hasFetchedNextBatch = useRef(false);

  // excludeIds: snapshot of video IDs already displayed, set in onLoadMore handler
  // right before incrementing feedFetchKey. Both state updates are batched by React
  // into a single render, so SWR sees the correct exclude list + new fetchKey together.
  const [excludeIds, setExcludeIds] = useState<string[]>([]);

  // Fetch feed based on auth state
  const { videos: apiVideos, mutate: mutateFeed } = usePersonalizedFeed(user ? user.id : null, feedLimit, feedFetchKey, excludeIds);
  const { videos: trendingVideos, mutate: mutateTrending } = useTrendingVideos(trendingLimit);

  // Select video source
  const currentVideos = user ? apiVideos : trendingVideos;

  // Fallback URLs for video playback when API contains dummy/placeholder URLs (like cdn.example.com or gotouchgrass.demo)
  const REAL_VIDEO_URLS = [
    'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
    'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4',
    'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4',
    'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4',
    'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4'
  ];

  const getRealVideoUrl = (url: string, index: number): string => {
    if (!url || url.includes('example.com') || url.includes('gotouchgrass.demo') || !url.startsWith('http')) {
      return REAL_VIDEO_URLS[index % REAL_VIDEO_URLS.length];
    }
    return url;
  };

  const [accumulatedVideos, setAccumulatedVideos] = useState<any[]>([]);

  // Guard to prevent concurrent session creation (race condition safeguard)
  const isCreatingSessionRef = useRef(false);

  useEffect(() => {
    if (currentVideos && currentVideos.length > 0) {
      setAccumulatedVideos(prev => {
        const newVids = currentVideos.filter(cv => !prev.find(p => p.id === cv.id));
        if (newVids.length > 0) {
          // New batch arrived → reset the guard so the next batch can be fetched
          hasFetchedNextBatch.current = false;
        }
        return newVids.length > 0 ? [...prev, ...newVids] : prev;
      });
    }
  }, [currentVideos]);

  // Keep accumulatedVideosRef in sync for stable reads in handleVideoActivated
  useEffect(() => {
    accumulatedVideosRef.current = accumulatedVideos;
  }, [accumulatedVideos]);

  // Handle page close/refresh to flush logs for active video
  useEffect(() => {
    const handleBeforeUnload = () => {
      feedRef.current?.flushActiveLog();
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // Handle tab switch/minimize to flush logs for active video
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        feedRef.current?.flushActiveLog();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // Map API videos to the format expected by Feed
  const feedVideos = accumulatedVideos && accumulatedVideos.length > 0 ? accumulatedVideos.map((v, index) => ({
    id: v.id,
    videoUrl: getRealVideoUrl(v.url, index),
    username: v.creator_id,
    description: v.description,
    songName: v.title || 'Original Sound',
    likes: v.like_count,
    comments: v.comment_count,
    shares: 0,
    bookmarks: 0,
    tags: v.tags
  })) : [];

  // ── SSE: receive real-time fatigue updates (replaces 3s polling) ──────────
  const handleSSEMessage = useCallback(({ fatigue_score, adaptive_state }: { fatigue_score: number; adaptive_state: string }) => {
    const newScore = Math.round(fatigue_score);
    const isExhaustedOrWarning =
      adaptive_state === 'warning' ||
      adaptive_state === 'exhausted' ||
      adaptive_state === 'critical';

    setAdaptiveState(adaptive_state as 'normal' | 'warning' | 'exhausted' | 'critical');
    setFatigueScore(newScore);

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
      touchGrassWarnedRef.current = false;
      setTouchGrassStage(2);
      setShowTouchGrassModal(true);
    }

    // Only trigger feed refetch when mindful state ACTUALLY changes,
    // AND not on the very first load (SWR already fetched automatically)
    if (isExhaustedOrWarning !== isMindfulActive && hasInitialFeedFetched.current) {
      setIsMindfulActive(isExhaustedOrWarning);
      if (user) {
        mutateFeed();
      }
    } else {
      setIsMindfulActive(isExhaustedOrWarning);
    }
    hasInitialFeedFetched.current = true;
  }, [isMindfulActive, user, mutateFeed]);

  useSessionSSE(sessionId, handleSSEMessage);

  // Track fatigue thresholds for sparkline and future event log re-enablement
  useEffect(() => {
    const curr = fatigueScore;

    setFatigueHistory(h => {
      if (h.length === 0 || h[h.length - 1] !== curr) {
        return [...h.slice(-49), curr];
      }
      return h;
    });

    prevFatigueRef.current = curr;
  }, [fatigueScore]);

  // Recover or start session on mount / user change
  useEffect(() => {
    if (user && !sessionId) {
      // NEW: Prevent concurrent session creation (race condition safeguard)
      if (isCreatingSessionRef.current) {
        console.warn('⚠️ Session creation already in progress, skipping duplicate');
        return;
      }
      isCreatingSessionRef.current = true;

      startSession(user.id)
        .then((session) => {
          setSessionId(session.id);
          localStorage.setItem('session_id', session.id);
          connectSessionWS(session.id);
          // SSE will push the initial state once connected — no manual fetch needed
        })
        .catch(console.error)
        .finally(() => {
          // NEW: Clear flag to allow future session creation if needed
          isCreatingSessionRef.current = false;
        });
    } else if (sessionId) {
      connectSessionWS(sessionId);
      // SSE stream starts automatically via useSessionSSE hook
    }
  }, [user]);

  // Reset accumulated videos and limits on user login/logout
  useEffect(() => {
    // Reset feed/video states
    setAccumulatedVideos([]);
    setExcludeIds([]); // clear exclude list for fresh user
    setFeedFetchKey(0); // reset fetch key so new user starts from batch 0
    // feedLimit is constant (BATCH_SIZE), no need to reset it
    setTrendingLimit(BATCH_SIZE);

    // NEW: Reset analytics states (fix for cache not clearing on login/register)
    setFatigueScore(0);
    setIsMindfulActive(false);
    setFatigueHistory([]);
    setLocalVideoCount(0);
    setIntensityCounts({});
    setAdaptiveState('normal');
    setShowTouchGrassModal(false);

    // NEW: Reset refs for analytics tracking
    seenVideoIdsRef.current = new Set();
    prevFatigueRef.current = 0;
    touchGrassWarnedRef.current = false;
    videoCountAtWarningRef.current = 0;
    stage1ShownRef.current = false;
    localVideoCountRef.current = 0;
  }, [user?.id]);

  const handleLoginSuccess = async (userData: { id: string; username: string }, token: string) => {
    setUser(userData);
    setAccessToken(token);
    localStorage.setItem('user', JSON.stringify(userData));
    localStorage.setItem('access_token', token);
  };

  const handleRegisterSuccess = async (userData: { id: string; username: string }, token: string) => {
    setUser(userData);
    setAccessToken(token);
    localStorage.setItem('user', JSON.stringify(userData));
    localStorage.setItem('access_token', token);
  };

  const handleLogout = async () => {
    feedRef.current?.flushActiveLog();
    disconnectSessionWS();
    if (sessionId) {
      try {
        await endSession(sessionId);
      } catch (error) {
        console.error('Failed to end session on logout:', error);
      }
    }
    setUser(null);
    setSessionId(null);
    setAccessToken(null);
    localStorage.removeItem('user');
    localStorage.removeItem('session_id');
    localStorage.removeItem('access_token');

    setFatigueScore(0);
    setIsMindfulActive(false);
    setShowTouchGrassModal(false);
    touchGrassWarnedRef.current = false;
    videoCountAtWarningRef.current = 0;
    stage1ShownRef.current = false;
    localVideoCountRef.current = 0;
  };

  const simulateDoomscroll = async () => {
    if (user && sessionId && feedVideos && feedVideos.length > 0) {
      const activeVideo = feedVideos[0];
      await sendBehaviorLog(
        activeVideo.id,
        activeVideo.tags?.[0] || 'general',
        user.id,
        sessionId,
        950.0, // High swipe speed
        0.5,   // Short watch duration
        false  // No interaction
      );
      await sendInteraction(
        activeVideo.id,
        'skip',
        0.05,
        user.id,
        sessionId,
        0.5,
        950.0
      );
      // SSE will push the updated fatigue score automatically — no setTimeout needed
    } else {
      // Fallback simulation when logged out
      setFatigueScore(prev => {
        const next = Math.min(prev + 15, 100);
        if (next >= 75) {
          setIsMindfulActive(true);
        }
        return next;
      });
    }
  };

  const resetSession = async () => {
    feedRef.current?.flushActiveLog();
    if (user && sessionId) {
      try {
        disconnectSessionWS();
        await endSession(sessionId);
        const newSession = await startSession(user.id);
        setSessionId(newSession.id);
        localStorage.setItem('session_id', newSession.id);
        connectSessionWS(newSession.id);
        setFatigueScore(0);
        setIsMindfulActive(false);
        setFatigueHistory([]);
        setLocalVideoCount(0);
        setIntensityCounts({});
        seenVideoIdsRef.current = new Set();
        prevFatigueRef.current = 0;
        touchGrassWarnedRef.current = false;
        videoCountAtWarningRef.current = 0;
        stage1ShownRef.current = false;
        localVideoCountRef.current = 0;
        setAccumulatedVideos([]);
        setExcludeIds([]); // clear exclude list for fresh session
        // Reset fetch key to 1 → new SWR cache key → forces fresh fetch for new session
        setFeedFetchKey(1);
      } catch (error) {
        console.error('Error resetting session:', error);
      }
    } else {
      setFatigueScore(25);
      setIsMindfulActive(false);
      setFatigueHistory([]);
      setLocalVideoCount(0);
      setIntensityCounts({});
      seenVideoIdsRef.current = new Set();
      prevFatigueRef.current = 0;
      touchGrassWarnedRef.current = false;
      videoCountAtWarningRef.current = 0;
      stage1ShownRef.current = false;
      localVideoCountRef.current = 0;
      setAccumulatedVideos([]);
      setTrendingLimit(BATCH_SIZE);
      mutateTrending();
    }
  };

  const handleTouchGrass = async () => {
    feedRef.current?.flushActiveLog();
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

  const handleContinueWatching = () => {
    setShowTouchGrassModal(false);
    touchGrassWarnedRef.current = true;
    videoCountAtWarningRef.current = localVideoCountRef.current;
  };

  return (
    <AuthContext.Provider value={{
      userId: user ? user.id : null,
      sessionId: sessionId,
      isAuthenticated: !!user,
      openAuthModal: () => setIsAuthOpen(true)
    }}>
      <div className="w-full h-full bg-zinc-950 flex flex-col md:flex-row items-center justify-center gap-6 p-0 md:p-4 font-sans select-none">

        {/* Smartphone frame shell for high fidelity desktop presentation */}
        <div className="relative w-full h-full md:w-[393px] md:h-[852px] bg-black md:rounded-[48px] md:border-[10px] md:border-zinc-800 md:shadow-[0_0_50px_rgba(0,0,0,0.8)] overflow-hidden flex flex-col justify-between">

          {/* Dynamic Island / Notch Mock */}
          <div className="hidden md:block absolute top-2 left-1/2 -translate-x-1/2 w-28 h-6 bg-black rounded-full z-50 flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-zinc-900 absolute left-4" />
          </div>

          {/* Top Header Controls (For You / Following / Mindful Status Indicator) */}
          <div className="absolute top-0 left-0 right-0 h-16 bg-gradient-to-b from-black/80 to-transparent flex items-center justify-between px-6 z-40">

            {/* Brand/Indicator Logo */}
            <div className="flex items-center gap-1">
              <Leaf className={`transition-colors duration-500 ${isMindfulActive ? 'text-emerald-400 animate-bounce' : 'text-zinc-500'}`} size={18} />
              <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider hidden xs:inline">GoTouchGrass</span>
            </div>

            {/* Primary Tabs */}
            <div className="flex gap-4 text-sm font-semibold">
              <span className="text-zinc-400 cursor-pointer transition-colors hover:text-white">Đang Follow</span>
              <span className="text-white cursor-pointer relative after:content-[''] after:absolute after:bottom-[-6px] after:left-1/2 after:-translate-x-1/2 after:w-4 after:h-0.5 after:bg-white">Dành cho bạn</span>
            </div>

            {/* Sparkle Demo Button */}
            <button
              onClick={() => setIsAuthOpen(true)}
              className="p-1.5 rounded-full bg-white/10 hover:bg-white/20 transition-colors text-white z-50"
            >
              <Sparkles size={16} />
            </button>

          </div>

          {/* Real-time Well-being Overlay Indicator (Premium Animated Bar) */}
          <div className={`absolute top-16 left-4 right-4 z-40 backdrop-blur-md rounded-2xl p-3 border shadow-lg transition-all duration-700 ${fatigueScore >= 80
            ? 'bg-rose-950/90 border-rose-500/70 shadow-rose-500/50 animate-pulse ring-1 ring-rose-500/30'
            : fatigueScore > 70
              ? 'bg-rose-950/80 border-rose-500/40 shadow-rose-500/20'
              : fatigueScore > 40
                ? 'bg-amber-950/80 border-amber-500/30 shadow-amber-500/10'
                : 'bg-zinc-900/80 border-zinc-800/80'
            }`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Brain size={18} className={`transition-all duration-500 ${fatigueScore > 70 ? 'text-rose-400 animate-pulse' : fatigueScore > 40 ? 'text-amber-400' : 'text-emerald-400'
                  }`} />
                <div className="flex flex-col">
                  <span className="text-[10px] text-zinc-400 font-medium">Chỉ số Mệt mỏi (Fatigue)</span>
                  <span className="text-xs font-bold text-white flex items-center gap-1.5">
                    {fatigueScore}%
                    {fatigueScore >= 80 ? (
                      <span className="text-[9px] bg-rose-600/30 text-rose-300 px-1.5 py-0.5 rounded-full font-semibold border border-rose-500/50 animate-pulse shadow-[0_0_8px_rgba(225,29,72,0.4)]">
                        💀 Nguy hiểm — Hãy nghỉ ngơi ngay!
                      </span>
                    ) : fatigueScore > 70 ? (
                      <span className="text-[9px] bg-rose-500/20 text-rose-300 px-1.5 py-0.5 rounded-full font-semibold border border-rose-500/30 animate-pulse">
                        🔥 Kiệt sức — Đang can thiệp
                      </span>
                    ) : fatigueScore > 40 ? (
                      <span className="text-[9px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded-full font-semibold border border-amber-500/30">
                        ⚠️ Cảnh báo
                      </span>
                    ) : (
                      <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded-full font-semibold border border-emerald-500/30">
                        ✅ Bình thường
                      </span>
                    )}
                  </span>
                </div>
              </div>
            </div>

            {/* Full-width animated progress bar */}
            <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-700 ease-out rounded-full ${fatigueScore > 70
                  ? 'bg-gradient-to-r from-rose-600 via-rose-400 to-red-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]'
                  : fatigueScore > 40
                    ? 'bg-gradient-to-r from-amber-600 via-amber-400 to-yellow-400 shadow-[0_0_6px_rgba(245,158,11,0.4)]'
                    : 'bg-gradient-to-r from-emerald-600 via-emerald-400 to-green-400 shadow-[0_0_4px_rgba(52,211,153,0.3)]'
                  }`}
                style={{ width: `${fatigueScore}%` }}
              />
            </div>
          </div>

          {/* Demo Simulator Control Hub (Floating sidebar for Pitching/Demo presentation) */}
          <div className="absolute left-4 bottom-24 z-40 flex flex-col gap-2 pointer-events-auto">
            <button
              onClick={simulateDoomscroll}
              className="px-3 py-1.5 bg-zinc-900/90 hover:bg-zinc-800 text-rose-300 border border-rose-500/30 rounded-xl text-[10px] font-semibold flex items-center gap-1 transition-all shadow-md active:scale-95"
              title="Mô phỏng hành vi vuốt nhanh và liên tục để kích hoạt cảnh báo"
            >
              <ShieldAlert size={12} />
              Lướt Vô Thức (+15%)
            </button>

            <button
              onClick={resetSession}
              className="px-3 py-1.5 bg-zinc-900/90 hover:bg-zinc-800 text-emerald-300 border border-emerald-500/30 rounded-xl text-[10px] font-semibold flex items-center gap-1 transition-all shadow-md active:scale-95"
            >
              <Leaf size={12} />
              Reset Trạng Thái
            </button>
          </div>

          {/* Adaptive Rerank/Mindful Injection Banner Alert */}
          {isMindfulActive && (
            <div className="absolute top-[120px] left-4 right-4 z-40 bg-emerald-950/90 border border-emerald-500/30 text-emerald-200 rounded-xl px-3 py-2 text-[10px] flex items-center gap-2 shadow-lg animate-bounce">
              <Leaf size={14} className="text-emerald-400 shrink-0" />
              <p className="leading-tight font-medium">
                <strong>Tự động can thiệp Mindful Feed!</strong> Đã lọc bớt các video kích thích, ưu tiên nhạc thư giãn và thiên nhiên.
              </p>
            </div>
          )}

          {/* Main Snapping Feed Container */}
          <div className="flex-1 w-full h-full relative z-0">
            <Feed
              ref={feedRef}
              videos={feedVideos}
              userId={user ? user.id : null}
              sessionId={sessionId}
              swipeTrigger={swipeTrigger}
              onVideoActivated={handleVideoActivated}
              onLoadMore={() => {
                if (hasFetchedNextBatch.current) return; // guard: already triggered for this batch
                hasFetchedNextBatch.current = true;
                if (user) {
                  // Snapshot current accumulated IDs → backend will exclude these
                  // React 18 batches both setState calls into one render.
                  setExcludeIds(accumulatedVideos.map((v: any) => v.id));
                  setFeedFetchKey(prev => prev + 1);
                } else {
                  // Trending: increase limit so backend returns more results
                  setTrendingLimit(prev => prev + BATCH_SIZE);
                }
              }}
            />
          </div>

          {/* Navigation bottom menu */}
          <BottomNav
            onProfileClick={() => setIsAuthOpen(true)}
            onHomeClick={resetSession}
          />

          {/* Simple pop up authentication modal */}
          <AuthPopup
            isOpen={isAuthOpen}
            onClose={() => setIsAuthOpen(false)}
            user={user}
            sessionId={sessionId}
            onLoginSuccess={handleLoginSuccess}
            onRegisterSuccess={handleRegisterSuccess}
            onLogout={handleLogout}
          />

          {/* Touch Grass Overlay Components */}
          <TouchGrassModal
            isOpen={showTouchGrassModal}
            fatigueScore={fatigueScore}
            stage={touchGrassStage}
            onTouchGrass={handleTouchGrass}
            onContinue={handleContinueWatching}
          />
          {showFarewell && <FarewellScreen onDismiss={() => setShowFarewell(false)} />}

        </div>

        {/* Analytics Dashboard (Outside phone frame, replacing old Control Panel) */}
        <div className="hidden md:block">
          <AnalyticsDashboard
            fatigueScore={fatigueScore}
            fatigueHistory={fatigueHistory}
            sessionVideoCount={localVideoCount}
            adaptiveState={adaptiveState}
            intensityCounts={intensityCounts}
            onSimulateDoomscroll={simulateDoomscroll}
            onResetSession={resetSession}
            onTriggerSwipe={triggerSwipe}
          />
        </div>

      </div>
    </AuthContext.Provider>
  );
}

export default App;
