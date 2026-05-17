import { useState } from 'react';
import { Feed } from './components/Feed';
import { BottomNav } from './components/BottomNav';
import { AuthPopup } from './components/AuthPopup';
import { Sparkles, Brain, Leaf, ShieldAlert } from 'lucide-react';

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
  }
];

function App() {
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  
  // States to simulate Phase 2 & 3 for presentation & demo purposes
  const [fatigueScore, setFatigueScore] = useState(25);
  const [isMindfulActive, setIsMindfulActive] = useState(false);

  const simulateDoomscroll = () => {
    // Simulate doomscroll fatigue increase
    setFatigueScore(prev => {
      const next = Math.min(prev + 15, 100);
      if (next >= 75) {
        setIsMindfulActive(true);
      }
      return next;
    });
  };

  const resetSession = () => {
    setFatigueScore(25);
    setIsMindfulActive(false);
  };

  return (
    <div className="w-full h-full bg-zinc-950 flex items-center justify-center p-0 md:p-4 font-sans select-none">
      
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

        {/* Real-time Well-being Overlay Indicator (Low Cognitive Load UI) */}
        <div className="absolute top-16 left-4 right-4 z-40 bg-zinc-900/80 backdrop-blur-md rounded-2xl p-3 border border-zinc-800/80 flex items-center justify-between shadow-lg">
          <div className="flex items-center gap-2">
            <Brain size={18} className={fatigueScore > 70 ? 'text-rose-400 animate-pulse' : 'text-emerald-400'} />
            <div className="flex flex-col">
              <span className="text-[10px] text-zinc-400 font-medium">Chỉ số Mệt mỏi (Fatigue)</span>
              <span className="text-xs font-bold text-white flex items-center gap-1.5">
                {fatigueScore}% 
                {fatigueScore >= 75 && (
                  <span className="text-[9px] bg-rose-500/20 text-rose-300 px-1 rounded font-normal border border-rose-500/30">
                    Doomscrolling!
                  </span>
                )}
              </span>
            </div>
          </div>
          
          {/* Small progress bar */}
          <div className="w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-500 rounded-full ${
                fatigueScore > 70 ? 'bg-rose-500' : fatigueScore > 40 ? 'bg-amber-400' : 'bg-emerald-500'
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
            videos={
              isMindfulActive 
                ? [
                    // Mindful Injection: Prioritize tranquil and calming videos, filter out Fast-cut or dark humor
                    MOCK_VIDEOS[2], // Nature heals
                    MOCK_VIDEOS[4], // Mindful piano
                    MOCK_VIDEOS[0], // Dev life (slightly lighter than football edits)
                  ]
                : MOCK_VIDEOS // Normal personalized feed
            } 
          />
        </div>

        {/* Navigation bottom menu */}
        <BottomNav 
          onProfileClick={() => setIsAuthOpen(true)} 
          onHomeClick={resetSession}
        />

        {/* Simple pop up authentication modal */}
        <AuthPopup isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />

      </div>
    </div>
  );
}

export default App;
