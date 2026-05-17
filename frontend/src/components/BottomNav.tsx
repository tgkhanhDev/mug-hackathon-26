import React from 'react';
import { Home, Compass, MessageSquare, User, Plus } from 'lucide-react';

interface BottomNavProps {
  onProfileClick: () => void;
  onHomeClick: () => void;
}

export const BottomNav: React.FC<BottomNavProps> = ({ onProfileClick, onHomeClick }) => {
  return (
    <div className="absolute bottom-0 w-full h-[64px] bg-black border-t border-zinc-800 flex items-center justify-around px-2 z-40 pb-safe">
      
      {/* Home */}
      <button 
        onClick={onHomeClick}
        className="flex flex-col items-center justify-center w-12 h-full text-white hover:opacity-80 transition-opacity"
      >
        <Home size={22} className="stroke-[2.5]" />
        <span className="text-[10px] mt-0.5 font-medium">Trang chủ</span>
      </button>

      {/* Discover */}
      <button 
        className="flex flex-col items-center justify-center w-12 h-full text-zinc-500 hover:text-white transition-colors"
      >
        <Compass size={22} />
        <span className="text-[10px] mt-0.5 font-medium">Khám phá</span>
      </button>

      {/* Upload button (TikTok style) */}
      <button 
        className="relative flex items-center justify-center w-11 h-8 group hover:scale-105 transition-transform"
      >
        <div className="absolute left-[-3px] w-full h-full bg-cyan-400 rounded-lg opacity-70" />
        <div className="absolute right-[-3px] w-full h-full bg-rose-500 rounded-lg opacity-70" />
        <div className="absolute inset-0 bg-white rounded-lg flex items-center justify-center text-black font-bold">
          <Plus size={18} className="stroke-[3]" />
        </div>
      </button>

      {/* Inbox */}
      <button 
        className="flex flex-col items-center justify-center w-12 h-full text-zinc-500 hover:text-white transition-colors"
      >
        <MessageSquare size={22} />
        <span className="text-[10px] mt-0.5 font-medium">Hộp thư</span>
      </button>

      {/* Profile */}
      <button 
        onClick={onProfileClick}
        className="flex flex-col items-center justify-center w-12 h-full text-zinc-500 hover:text-white transition-colors"
      >
        <User size={22} />
        <span className="text-[10px] mt-0.5 font-medium">Hồ sơ</span>
      </button>

    </div>
  );
};
