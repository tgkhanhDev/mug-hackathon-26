import React, { useEffect } from 'react';
import grassImg from '../assets/grass.png';

interface FarewellScreenProps {
  onDismiss: () => void;
}

export const FarewellScreen: React.FC<FarewellScreenProps> = ({ onDismiss }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss();
    }, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div 
      className="absolute inset-0 z-[100] flex flex-col items-center justify-center bg-gradient-to-b from-emerald-950 to-black animate-in fade-in duration-1000 cursor-pointer overflow-hidden"
      onClick={onDismiss}
    >
      <div className="relative mb-8 transform hover:scale-110 transition-transform duration-700 ease-out animate-bounce">
        <div className="absolute inset-0 bg-emerald-500 blur-[60px] opacity-30 rounded-full animate-pulse" />
        <img src={grassImg} alt="Touch Grass" className="w-48 h-48 object-contain drop-shadow-[0_0_30px_rgba(16,185,129,0.5)] relative z-10" />
      </div>
      
      <h1 className="text-2xl font-black text-white mb-4 text-center px-6 leading-tight drop-shadow-md">
        Tuyệt vời! <br/> Bước ra ngoài và <br/> <span className="text-emerald-400">chạm cỏ</span> đi nhé 🌱
      </h1>
      
      <p className="text-emerald-200/60 text-[10px] mt-4 animate-pulse uppercase tracking-wider font-bold">
        Chạm vào màn hình để đóng
      </p>

      {/* Confetti (Simple CSS implementation) */}
      <div className="absolute inset-0 pointer-events-none">
        {[...Array(25)].map((_, i) => (
          <div 
            key={i}
            className="absolute bg-emerald-400 w-2 h-2 rounded-sm opacity-60"
            style={{
              left: `${Math.random() * 100}%`,
              top: `-20px`,
              animation: `fall ${Math.random() * 3 + 2}s linear infinite`,
              animationDelay: `${Math.random() * 2}s`,
              transform: `rotate(${Math.random() * 360}deg)`
            }}
          />
        ))}
      </div>
      <style>{`
        @keyframes fall {
          to {
            transform: translateY(100vh) rotate(720deg);
          }
        }
      `}</style>
    </div>
  );
};
