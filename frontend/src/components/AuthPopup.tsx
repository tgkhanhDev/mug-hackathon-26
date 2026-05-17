import React from 'react';
import { X, Mail, ShieldAlert, Sparkles } from 'lucide-react';

interface AuthPopupProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthPopup: React.FC<AuthPopupProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end justify-center transition-all duration-300">
      {/* Background click to close */}
      <div className="absolute inset-0" onClick={onClose} />
      
      {/* Drawer-like design for mobile friendliness */}
      <div className="relative w-full max-w-md bg-zinc-900 border-t border-zinc-800 rounded-t-3xl p-6 flex flex-col items-center gap-6 z-10 shadow-2xl animate-in slide-in-from-bottom duration-300">
        
        {/* Pull bar */}
        <div className="w-12 h-1 bg-zinc-700 rounded-full mb-2" />
        
        {/* Close Button */}
        <button 
          onClick={onClose} 
          className="absolute top-4 right-4 p-2 rounded-full hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>

        {/* Title & Brand */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-2 text-emerald-400">
            <Sparkles size={24} className="animate-pulse" />
            <h2 className="text-xl font-bold text-white tracking-wide">GoTouchGrass</h2>
          </div>
          <p className="text-zinc-400 text-xs px-4">
            Đăng nhập để cá nhân hóa nguồn cấp dữ liệu, theo dõi sức khỏe số và bảo vệ tâm trí của bạn.
          </p>
        </div>

        {/* Options */}
        <div className="w-full flex flex-col gap-3">
          <button 
            className="w-full py-3.5 px-4 bg-emerald-500 hover:bg-emerald-400 text-black font-semibold rounded-xl flex items-center justify-center gap-3 transition-colors text-sm"
            onClick={onClose}
          >
            <Mail size={18} />
            Tiếp tục với Email
          </button>
          
          <button 
            className="w-full py-3.5 px-4 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 hover:border-zinc-600 text-white font-semibold rounded-xl flex items-center justify-center gap-3 transition-colors text-sm"
            onClick={onClose}
          >
            {/* Simple Mock Google Icon */}
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="currentColor"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="currentColor"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="currentColor"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Tiếp tục với Google
          </button>
        </div>

        {/* Info Box */}
        <div className="w-full bg-zinc-800/50 rounded-xl p-3.5 flex items-start gap-3 border border-zinc-800/80">
          <ShieldAlert size={20} className="text-emerald-400 shrink-0 mt-0.5" />
          <p className="text-[11px] text-zinc-400 leading-normal">
            Bằng cách tiếp tục, bạn đồng ý kích hoạt tính năng tự động theo dõi thời gian thực để ngăn ngừa hành vi doomscrolling. GoTouchGrass bảo mật quyền riêng tư của bạn.
          </p>
        </div>

        {/* Footer info */}
        <div className="text-[10px] text-zinc-600">
          GoTouchGrass - Hackathon MVP v1.0
        </div>
      </div>
    </div>
  );
};
