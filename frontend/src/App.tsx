import { useState, useEffect, useRef } from 'react';
import { connectSessionWS, disconnectSessionWS } from './hooks/useVideoStats';
import { Feed } from './components/Feed';
import { BottomNav } from './components/BottomNav';
import { AuthPopup } from './components/AuthPopup';
import { AuthContext } from './context/AuthContext';
import { Sparkles, Brain, Leaf, ShieldAlert, ChevronUp, ChevronDown, Zap, Gauge } from 'lucide-react';
import {
  useTrendingVideos,
  usePersonalizedFeed,
  startSession,
  endSession,
  getSession,
  sendBehaviorLog,
  sendInteraction
} from './api/client';

// Mock vertical-clipped video dataset
const MOCK_VIDEOS = [
  {
    id: '1',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
    username: 'developer_meme',
    description: 'Khi bạn cố gắng sửa 1 bug và tạo ra thêm 10 bug mới... 💻☠️ #coding #programmers #devlife #funny',
    songName: 'Coding Lofi Beats - developer_life',
    likes: 124300,
    comments: 890,
    shares: 4320,
    bookmarks: 2310,
    tags: ['programming']
  },
  {
    id: '2',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4',
    username: 'cristiano_fans',
    description: 'Khoảnh khắc không thể tin nổi của CR7 ở phút bù giờ cuối cùng! 🐐⚽ #football #cr7 #ronaldo #epic',
    songName: 'Phonk Remix - SoundKing',
    likes: 980200,
    comments: 12430,
    shares: 89400,
    bookmarks: 54100,
    tags: ['sports']
  },
  {
    id: '3',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4',
    username: 'nature_heals',
    description: 'Dừng lại 10 giây để ngắm nhìn vẻ đẹp yên bình này và hít thở thật sâu bạn nhé... 🍃⛰️ #mindfulness #gotouchgrass #calming',
    songName: 'Âm thanh tự nhiên làm dịu tâm hồn',
    likes: 54300,
    comments: 1200,
    shares: 8900,
    bookmarks: 9820,
    tags: ['nature']
  },
  {
    id: '4',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4',
    username: 'dark_humor_hub',
    description: 'Thứ Hai đầu tuần của tôi khi nghe sếp bảo dự án cần làm gấp trong tối nay. 💀🙃 #darkhumor #worklife #burnout',
    songName: 'Sad Violin - Instrumental Player',
    likes: 320100,
    comments: 4210,
    shares: 12900,
    bookmarks: 7600,
    tags: ['lifestyle']
  },
  {
    id: '5',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    username: 'mindful_piano',
    description: 'Hãy để bản nhạc piano nhẹ nhàng này gột rửa mọi áp lực ngày hôm nay của bạn. 🎹🌧️ #meditation #sleepmusic #piano',
    songName: 'Raindrops & Melodies - Zen Garden',
    likes: 87100,
    comments: 2100,
    shares: 15400,
    bookmarks: 18200,
    tags: ['meditation']
  }
];

function App() {
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

  // Pagination / Infinite Scroll states
  // feedLimit is kept CONSTANT — backend dedup ($nin seen_video_ids) ensures each
  // mutateFeed() call returns a fresh batch of BATCH_SIZE videos never seen before.
  const BATCH_SIZE = 5;
  const [feedLimit] = useState(BATCH_SIZE);
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

  // Fetch feed based on auth state
  const { videos: apiVideos, mutate: mutateFeed } = usePersonalizedFeed(user ? user.id : null, feedLimit);
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
  })) : MOCK_VIDEOS;

  const refreshSessionStats = async (activeSessionId?: string | null) => {
    const sid = activeSessionId !== undefined ? activeSessionId : sessionId;
    if (!sid) return;
    try {
      const sessionData = await getSession(sid);
      const newScore = Math.round(sessionData.fatigue_score);
      const isExhaustedOrWarning = sessionData.adaptive_state === 'warning' || sessionData.adaptive_state === 'exhausted';

      setFatigueScore(newScore);

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
    } catch (error) {
      console.error('Error fetching session stats:', error);
    }
  };

  // Recover or start session on mount / user change
  useEffect(() => {
    if (user && !sessionId) {
      startSession(user.id)
        .then((session) => {
          setSessionId(session.id);
          localStorage.setItem('session_id', session.id);
          connectSessionWS(session.id);
          refreshSessionStats(session.id);
        })
        .catch(console.error);
    } else if (sessionId) {
      connectSessionWS(sessionId);
      refreshSessionStats(sessionId);
    }
  }, [user]);

  // Reset accumulated videos and limits on user login/logout
  useEffect(() => {
    setAccumulatedVideos([]);
    // feedLimit is constant (BATCH_SIZE), no need to reset it
    setTrendingLimit(BATCH_SIZE);
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
      setTimeout(() => {
        refreshSessionStats();
      }, 500);
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
        setAccumulatedVideos([]);
        // feedLimit is constant (BATCH_SIZE), no setter needed
        mutateFeed();
      } catch (error) {
        console.error('Error resetting session:', error);
      }
    } else {
      setFatigueScore(25);
      setIsMindfulActive(false);
      setAccumulatedVideos([]);
      setTrendingLimit(BATCH_SIZE);
      mutateTrending();
    }
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
          <div className={`absolute top-16 left-4 right-4 z-40 backdrop-blur-md rounded-2xl p-3 border shadow-lg transition-all duration-700 ${fatigueScore > 70
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
                    {fatigueScore > 70 ? (
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
              videos={feedVideos}
              userId={user ? user.id : null}
              sessionId={sessionId}
              onRefreshSessionStats={refreshSessionStats}
              swipeTrigger={swipeTrigger}
              onLoadMore={() => {
                if (hasFetchedNextBatch.current) return; // already fetching this batch
                hasFetchedNextBatch.current = true;
                if (user) {
                  // feedLimit stays constant (BATCH_SIZE=5). mutateFeed() re-fetches
                  // /feed?limit=5 and the backend's $nin dedup filter guarantees
                  // a fresh batch of videos never seen in this session.
                  mutateFeed();
                } else {
                  // Trending has no session-based dedup on BE → still increase limit
                  // so the endpoint returns more results for FE to filter duplicates.
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

        </div>

        {/* Control Panel (Outside phone frame) */}
        <div className="hidden md:flex flex-col gap-5 bg-zinc-900/90 border border-zinc-800/80 rounded-[32px] p-5 w-64 text-white shadow-2xl backdrop-blur-md">
          <div className="flex items-center gap-2 text-emerald-400">
            <Gauge size={20} className="animate-pulse" />
            <h3 className="font-bold text-xs uppercase tracking-wider font-mono">Bảng Điều Khiển Vuốt</h3>
          </div>

          <p className="text-zinc-500 text-[10px] leading-relaxed">
            Mô phỏng hành động vuốt màn hình (Swipe Gesture) bên ngoài khung điện thoại để kiểm thử thuật toán mệt mỏi và đề xuất nội dung.
          </p>

          <div className="h-px bg-zinc-800/50" />

          <div className="flex flex-col gap-3">
            <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono font-bold">Lướt Tiếp (Tiến)</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => triggerSwipe('up', 'fast')}
                className="py-2.5 px-3 bg-rose-500/10 hover:bg-rose-500 hover:text-black border border-rose-500/20 text-rose-400 font-semibold rounded-xl flex flex-col items-center justify-center gap-1 transition-all text-[10px]"
              >
                <Zap size={14} />
                Nhanh (Doom)
              </button>
              <button
                onClick={() => triggerSwipe('up', 'slow')}
                className="py-2.5 px-3 bg-emerald-500/10 hover:bg-emerald-500 hover:text-black border border-emerald-500/20 text-emerald-400 font-semibold rounded-xl flex flex-col items-center justify-center gap-1 transition-all text-[10px]"
              >
                <ChevronDown size={14} />
                Chậm (Mindful)
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono font-bold">Lướt Về (Lùi)</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => triggerSwipe('down', 'fast')}
                className="py-2.5 px-3 bg-zinc-800 hover:bg-white hover:text-black border border-zinc-700 text-zinc-300 font-semibold rounded-xl flex flex-col items-center justify-center gap-1 transition-all text-[10px]"
              >
                <Zap size={14} />
                Nhanh
              </button>
              <button
                onClick={() => triggerSwipe('down', 'slow')}
                className="py-2.5 px-3 bg-zinc-800 hover:bg-white hover:text-black border border-zinc-700 text-zinc-300 font-semibold rounded-xl flex flex-col items-center justify-center gap-1 transition-all text-[10px]"
              >
                <ChevronUp size={14} />
                Chậm
              </button>
            </div>
          </div>

          <div className="h-px bg-zinc-800/50" />

          <div className="bg-zinc-950/60 rounded-xl p-3 border border-zinc-800/50 flex flex-col gap-1.5">
            <span className="text-[9px] text-zinc-500 font-mono">THÔNG SỐ GIẢ LẬP:</span>
            <div className="flex justify-between text-[10px] text-zinc-400 font-mono">
              <span>Tốc độ nhanh:</span>
              <span className="text-rose-400">950 px/s</span>
            </div>
            <div className="flex justify-between text-[10px] text-zinc-400 font-mono">
              <span>Tốc độ chậm:</span>
              <span className="text-emerald-400">150 px/s</span>
            </div>
          </div>
        </div>

      </div>
    </AuthContext.Provider>
  );
}

export default App;
