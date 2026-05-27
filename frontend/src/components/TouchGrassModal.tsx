import React from 'react';
import grassImg from '../assets/grass.png';
import { Leaf, ArrowRight } from 'lucide-react';

interface TouchGrassModalProps {
  isOpen: boolean;
  fatigueScore: number;
  onTouchGrass: () => void;
  onContinue: () => void;
}

export const TouchGrassModal: React.FC<TouchGrassModalProps> = ({
  isOpen,
  fatigueScore,
  onTouchGrass,
  onContinue
}) => {
  if (!isOpen) return null;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xl animate-in fade-in duration-500">
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-3xl p-6 w-full max-w-sm flex flex-col items-center text-center shadow-2xl relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 to-rose-500/10 pointer-events-none" />

        <div className="relative mb-6 mt-4 animate-bounce">
          <img src={grassImg} alt="Touch Grass" className="w-32 h-32 object-contain drop-shadow-2xl" />
        </div>

        <h2 className="text-xl font-bold text-white mb-2 leading-tight">Này... Bạn đang <br/> kiệt sức rồi đó! 🌿</h2>
        
        <div className="flex flex-col items-center gap-1 mb-6 mt-2">
          <span className="text-zinc-400 text-[10px] uppercase font-bold tracking-wider">Chỉ số mệt mỏi</span>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-black text-rose-400">{fatigueScore}%</span>
            <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
               <div className="h-full bg-rose-500 animate-pulse w-full rounded-full shadow-[0_0_10px_rgba(244,63,94,0.5)]" />
            </div>
          </div>
        </div>

        <p className="text-xs text-zinc-400 mb-8 px-2">
          Hệ thống phát hiện bạn đã lướt liên tục quá lâu. Đã đến lúc đặt điện thoại xuống và bước ra ngoài.
        </p>

        <div className="flex flex-col w-full gap-3">
          <button
            onClick={onTouchGrass}
            className="w-full py-3.5 bg-emerald-500 hover:bg-emerald-400 text-black font-bold rounded-xl flex items-center justify-center gap-2 transition-all active:scale-95 shadow-[0_0_20px_rgba(16,185,129,0.3)]"
          >
            <Leaf size={18} />
            Chạm Cỏ Ngay!
          </button>
          
          <button
            onClick={onContinue}
            className="w-full py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold rounded-xl flex items-center justify-center gap-2 transition-all active:scale-95"
          >
            Tiếp tục xem <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
};
