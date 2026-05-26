import React from 'react';
import { Brain, Play, ShieldAlert, Zap, ChevronUp, ChevronDown, Activity } from 'lucide-react';

interface AnalyticsDashboardProps {
  fatigueScore: number;
  fatigueHistory: number[];
  sessionVideoCount: number;
  adaptiveState: 'normal' | 'warning' | 'exhausted';
  topicCounts: Record<string, number>;
  eventLog: { time: string; message: string; type: string }[];
  onSimulateDoomscroll: () => void;
  onResetSession: () => void;
  onTriggerSwipe: (dir: 'up' | 'down', speed: 'slow' | 'fast') => void;
}

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  fatigueScore,
  fatigueHistory,
  sessionVideoCount,
  adaptiveState,
  topicCounts,
  eventLog,
  onSimulateDoomscroll,
  onResetSession,
  onTriggerSwipe
}) => {
  // Feed composition stats based on actual viewed topics
  const CALMING_TOPICS = ['nature', 'meditation', 'calming', 'sleep', 'piano', 'mindfulness'];
  const HIGH_TOPICS = ['sports', 'football', 'gaming', 'dark_humor', 'programming', 'coding', 'lifestyle'];

  const highCount = Object.entries(topicCounts)
    .filter(([t]) => HIGH_TOPICS.some(h => t.toLowerCase().includes(h)))
    .reduce((sum, [, c]) => sum + c, 0);

  const calmCount = Object.entries(topicCounts)
    .filter(([t]) => CALMING_TOPICS.some(h => t.toLowerCase().includes(h)))
    .reduce((sum, [, c]) => sum + c, 0);

  const lowCount = Math.max(0, sessionVideoCount - highCount - calmCount);
  const totalAnalyzed = Math.max(1, sessionVideoCount);

  // Sparkline generator (200x60)
  const sparklinePoints = fatigueHistory.length > 0
    ? fatigueHistory.map((val, i) => {
      const x = (i / Math.max(1, fatigueHistory.length - 1)) * 200;
      const y = 60 - (val / 100) * 60;
      return `${x},${y}`;
    }).join(' ')
    : '0,60';

  return (
    <div className="flex flex-col gap-5 bg-zinc-900/90 border border-zinc-800/80 rounded-[32px] p-5 w-[320px] text-white shadow-2xl backdrop-blur-md max-h-[852px] overflow-y-auto custom-scrollbar">

      {/* Header */}
      <div className="flex items-center gap-2 text-emerald-400 mb-2">
        <Activity size={20} className="animate-pulse" />
        <h3 className="font-bold text-[13px] uppercase tracking-wider font-mono">Live Analytics</h3>
      </div>

      {/* Section 1: Status Cards */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-zinc-950/60 rounded-xl p-2.5 border border-zinc-800/50 flex flex-col items-center text-center justify-center">
          <Brain size={16} className={fatigueScore > 70 ? 'text-rose-400' : fatigueScore > 40 ? 'text-amber-400' : 'text-emerald-400'} mb-1 />
          <span className="text-[10px] text-zinc-500 font-mono">FATIGUE</span>
          <span className="text-sm font-bold">{Math.round(fatigueScore)}%</span>
        </div>
        <div className="bg-zinc-950/60 rounded-xl p-2.5 border border-zinc-800/50 flex flex-col items-center text-center justify-center">
          <Play size={16} className="text-blue-400" mb-1 />
          <span className="text-[10px] text-zinc-500 font-mono">WATCHED</span>
          <span className="text-sm font-bold">{sessionVideoCount}</span>
        </div>
        <div className="bg-zinc-950/60 rounded-xl p-2.5 border border-zinc-800/50 flex flex-col items-center text-center justify-center">
          <ShieldAlert size={16} className={adaptiveState === 'exhausted' ? 'text-rose-400' : adaptiveState === 'warning' ? 'text-amber-400' : 'text-emerald-400'} mb-1 />
          <span className="text-[9px] text-zinc-500 font-mono">PHASE</span>
          <span className={`text-[11px] font-bold ${adaptiveState === 'exhausted' ? 'text-rose-400' : adaptiveState === 'warning' ? 'text-amber-400' : 'text-emerald-400'}`}>
            {adaptiveState.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="h-px bg-zinc-800/50" />

      {/* Section 2: Fatigue Timeline (Sparkline) */}
      <div className="flex flex-col gap-2">
        <span className="text-[10px] text-zinc-400 uppercase tracking-widest font-mono font-bold">Fatigue Timeline</span>
        <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-3 h-[80px] flex items-end relative overflow-hidden">
          <div className="absolute left-2 top-2 text-[9px] text-zinc-600 font-mono">100%</div>
          <div className="absolute left-2 bottom-2 text-[9px] text-zinc-600 font-mono">0%</div>

          {/* Dotted threshold lines */}
          <div className="absolute left-0 right-0 top-[30%] border-t border-dashed border-rose-500/20" /> {/* 70% line */}
          <div className="absolute left-0 right-0 top-[60%] border-t border-dashed border-amber-500/20" /> {/* 40% line */}

          <svg width="100%" height="60" viewBox="0 0 200 60" preserveAspectRatio="none" className="overflow-visible mt-auto">
            <polyline
              points={sparklinePoints}
              fill="none"
              stroke={fatigueScore > 70 ? '#fb7185' : fatigueScore > 40 ? '#fbbf24' : '#34d399'}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>

      {/* Section 3: Feed Composition */}
      <div className="flex flex-col gap-3">
        <span className="text-[10px] text-zinc-400 uppercase tracking-widest font-mono font-bold">Feed Composition</span>
        <div className="flex flex-col gap-2 text-[10px] font-mono">
          <div className="flex items-center gap-2">
            <span className="w-24 text-rose-400">High Intensity</span>
            <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div className="h-full bg-rose-500 rounded-full" style={{ width: `${(highCount / totalAnalyzed) * 100}%` }} />
            </div>
            <span className="w-6 text-right text-zinc-500">{highCount}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-24 text-zinc-400">Low Intensity</span>
            <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div className="h-full bg-zinc-400 rounded-full" style={{ width: `${(lowCount / totalAnalyzed) * 100}%` }} />
            </div>
            <span className="w-6 text-right text-zinc-500">{lowCount}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-24 text-emerald-400">Calming/Nature</span>
            <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${(calmCount / totalAnalyzed) * 100}%` }} />
            </div>
            <span className="w-6 text-right text-zinc-500">{calmCount}</span>
          </div>
        </div>
      </div>

      <div className="h-px bg-zinc-800/50" />

      {/* Section 4: Phase Transition Log */}
      {/* <div className="flex flex-col gap-2">
        <span className="text-[10px] text-zinc-400 uppercase tracking-widest font-mono font-bold">Event Log</span>
        <div className="bg-zinc-950/60 rounded-xl p-3 border border-zinc-800/50 h-[120px] overflow-y-auto custom-scrollbar flex flex-col gap-2">
          {eventLog.length === 0 ? (
            <span className="text-[10px] text-zinc-600 italic">No events yet...</span>
          ) : (
            eventLog.slice().reverse().map((log, idx) => (
              <div key={idx} className="flex gap-2 text-[10px]">
                <span className="text-zinc-500 font-mono shrink-0">[{log.time}]</span>
                <span className={`${log.type === 'danger' ? 'text-rose-400' : log.type === 'warning' ? 'text-amber-400' : log.type === 'success' ? 'text-emerald-400' : 'text-zinc-300'}`}>
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>
      </div> */}

      <div className="h-px bg-zinc-800/50" />

      {/* Section 5: Demo Controls */}
      <div className="flex flex-col gap-3">
        <span className="text-[10px] text-zinc-400 uppercase tracking-widest font-mono font-bold">Demo Controls</span>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onSimulateDoomscroll}
            className="py-2 px-3 bg-rose-500/10 hover:bg-rose-500 hover:text-black border border-rose-500/20 text-rose-400 font-semibold rounded-xl flex items-center justify-center gap-1 transition-all text-[10px]"
          >
            <ShieldAlert size={12} /> Lướt Vô Thức
          </button>
          <button
            onClick={onResetSession}
            className="py-2 px-3 bg-emerald-500/10 hover:bg-emerald-500 hover:text-black border border-emerald-500/20 text-emerald-400 font-semibold rounded-xl flex items-center justify-center gap-1 transition-all text-[10px]"
          >
            <Activity size={12} /> Reset
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2 mt-1">
          <div className="flex flex-col gap-2">
            <span className="text-[9px] text-zinc-500 text-center">Swipe Up (Next)</span>
            <button onClick={() => onTriggerSwipe('up', 'fast')} className="py-1.5 px-2 bg-zinc-800 hover:bg-white hover:text-black rounded text-[10px] flex items-center justify-center gap-1"><Zap size={10} /> Fast</button>
            <button onClick={() => onTriggerSwipe('up', 'slow')} className="py-1.5 px-2 bg-zinc-800 hover:bg-white hover:text-black rounded text-[10px] flex items-center justify-center gap-1"><ChevronDown size={10} /> Slow</button>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-[9px] text-zinc-500 text-center">Swipe Down (Prev)</span>
            <button onClick={() => onTriggerSwipe('down', 'fast')} className="py-1.5 px-2 bg-zinc-800 hover:bg-white hover:text-black rounded text-[10px] flex items-center justify-center gap-1"><Zap size={10} /> Fast</button>
            <button onClick={() => onTriggerSwipe('down', 'slow')} className="py-1.5 px-2 bg-zinc-800 hover:bg-white hover:text-black rounded text-[10px] flex items-center justify-center gap-1"><ChevronUp size={10} /> Slow</button>
          </div>
        </div>
      </div>

    </div>
  );
};
