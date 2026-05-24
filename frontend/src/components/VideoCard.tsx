import React, { useRef, useState, useEffect, useContext } from 'react';
import { Heart, MessageCircle, Bookmark, Share2, Music } from 'lucide-react';
import { useInView } from 'react-intersection-observer';
import { useVideoStats } from '../hooks/useVideoStats';
import { sendInteraction, sendBehaviorLog } from '../api/client';
import { AuthContext } from '../context/AuthContext';

interface VideoCardProps {
  videoUrl: string;
  username: string;
  description: string;
  songName: string;
  likes: number;
  comments: number;
  shares: number;
  bookmarks: number;
  isActive: boolean;
  videoId: string;
  topic: string;
  userId: string | null;
  sessionId: string | null;
  onRefreshSessionStats: (activeSessionId?: string | null) => Promise<void>;
  swipeSpeed: number;
}

export const VideoCard: React.FC<VideoCardProps> = ({
  videoUrl,
  username,
  description,
  songName,
  likes,
  comments,
  shares,
  bookmarks,
  isActive,
  videoId,
  topic,
  userId,
  sessionId,
  onRefreshSessionStats,
  swipeSpeed
}) => {
  const { ref: inViewRef, inView } = useInView({ threshold: 0.7 });
  const { isAuthenticated, openAuthModal } = useContext(AuthContext);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLiked, setIsLiked] = useState(false);
  const [hasCommented, setHasCommented] = useState(false);
  const [isProcessingLike, setIsProcessingLike] = useState(false);
  const [isProcessingComment, setIsProcessingComment] = useState(false);
  const [replayCount, setReplayCount] = useState(0);

  const activeStartTimeRef = useRef<number | null>(null);
  const replayCountRef = useRef(0);

  // Combine refs (intersection observer + video element)
  const setRefs = (node: HTMLVideoElement) => {
    videoRef.current = node;
    inViewRef(node);
  };

  const realTimeStats = useVideoStats(
    videoId, 
    { like_count: likes, view_count: 0, comment_count: comments }, 
    inView
  );

  useEffect(() => {
    replayCountRef.current = replayCount;
  }, [replayCount]);

  // Keep latest parameters in ref to access in cleanup without triggering effect re-runs
  const logParamsRef = useRef({
    userId,
    sessionId,
    videoId,
    topic,
    isLiked,
    hasCommented,
    swipeSpeed
  });

  useEffect(() => {
    logParamsRef.current = {
      userId,
      sessionId,
      videoId,
      topic,
      isLiked,
      hasCommented,
      swipeSpeed
    };
  }, [userId, sessionId, videoId, topic, isLiked, hasCommented, swipeSpeed]);

  useEffect(() => {
    if (isActive) {
      setIsPlaying(true);
      activeStartTimeRef.current = Date.now();
      const playPromise = videoRef.current?.play();
      if (playPromise !== undefined) {
        playPromise.catch((error) => {
          console.warn("Autoplay was prevented by browser policy:", error);
          setIsPlaying(false);
        });
      }
    } else {
      videoRef.current?.pause();
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
      }
      setIsPlaying(false);
    }

    return () => {
      // Cleanup runs when card becomes inactive or unmounts
      if (activeStartTimeRef.current !== null) {
        const duration = (Date.now() - activeStartTimeRef.current) / 1000;
        activeStartTimeRef.current = null;
        
        const params = logParamsRef.current;
        if (params.userId && params.sessionId) {
          const wasInteracted = params.isLiked || params.hasCommented || replayCountRef.current > 0;
          
          sendBehaviorLog(
            params.videoId,
            params.topic,
            params.userId,
            params.sessionId,
            params.swipeSpeed,
            duration,
            wasInteracted
          ).then(() => {
            onRefreshSessionStats();
          });

          // Removed default interactions (skip/passive_view) as requested.
          // Only explicit user actions will trigger sendInteraction now.
        }
      }
    };
  }, [isActive]);

  const handleLike = async () => {
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }
    if (isProcessingLike) return; // blocking state
    
    const newLikedState = !isLiked;
    setIsLiked(newLikedState);
    if (newLikedState) {
      setIsProcessingLike(true);
      try {
        await sendInteraction(
          videoId, 
          'like', 
          0.8, 
          userId || undefined, 
          sessionId || undefined
        );
      } finally {
        setIsProcessingLike(false);
      }
    }
  };

  const handleComment = async () => {
    if (!isAuthenticated) {
      openAuthModal();
      return;
    }
    if (hasCommented || isProcessingComment) return; // block if already commented or processing
    
    setHasCommented(true);
    setIsProcessingComment(true);
    try {
      await sendInteraction(
        videoId, 
        'comment', 
        0.5, 
        userId || undefined, 
        sessionId || undefined
      );
    } finally {
      setIsProcessingComment(false);
    }
  };

  const previousTimeRef = useRef(0);

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const currentTime = videoRef.current.currentTime;
    const duration = videoRef.current.duration;
    
    // Detect loop: if time jumps back from near the end to the beginning
    if (duration > 0 && previousTimeRef.current > duration - 1 && currentTime < 1) {
      handleVideoEnded();
    }
    previousTimeRef.current = currentTime;
  };

  const handleVideoEnded = () => {
    setReplayCount(prev => prev + 1);
    if (videoRef.current && !videoRef.current.loop) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(console.error);
    }
    if (userId && sessionId) {
      sendInteraction(
        videoId,
        'replay',
        1.0,
        userId,
        sessionId,
        videoRef.current?.duration || 10,
        swipeSpeed,
        replayCount + 1
      );
    }
  };

  const togglePlay = () => {
    if (isPlaying) {
      videoRef.current?.pause();
      setIsPlaying(false);
    } else {
      setIsPlaying(true);
      const playPromise = videoRef.current?.play();
      if (playPromise !== undefined) {
        playPromise.catch((error) => {
          console.error("Playback failed:", error);
          setIsPlaying(false);
        });
      }
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  return (
    <div className="relative w-full h-full bg-zinc-900 snap-start shrink-0">
      {/* Video element */}
      <video
        ref={setRefs}
        src={videoUrl}
        className="w-full h-full object-cover"
        muted={false}
        onClick={togglePlay}
        onEnded={handleVideoEnded}
        onTimeUpdate={handleTimeUpdate}
        playsInline
        loop
      />
      
      {/* Overlay controls - only show when paused */}
      {!isPlaying && (
        <div 
          className="absolute inset-0 flex items-center justify-center bg-black/20 pointer-events-none"
        >
          <div className="w-16 h-16 bg-black/50 rounded-full flex items-center justify-center">
            <div className="w-0 h-0 border-t-8 border-t-transparent border-l-[16px] border-l-white border-b-8 border-b-transparent ml-1" />
          </div>
        </div>
      )}

      {/* Right Sidebar Actions */}
      <div className="absolute right-4 bottom-24 flex flex-col items-center gap-6 z-10">
        <div className="w-12 h-12 rounded-full bg-white/20 border border-white/50 flex items-center justify-center overflow-hidden mb-2">
          <img src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${username}`} alt="avatar" className="w-full h-full object-cover" />
        </div>
        
        <button className="flex flex-col items-center gap-1 group" onClick={handleLike}>
          <div className="p-2 rounded-full group-hover:bg-white/10 transition-colors">
            <Heart size={32} className={isLiked ? 'fill-red-500 text-red-500' : 'text-white'} />
          </div>
          <span className="text-white text-xs font-semibold">{formatNumber(realTimeStats.like_count)}</span>
        </button>

        <button className="flex flex-col items-center gap-1 group" onClick={handleComment}>
          <div className="p-2 rounded-full group-hover:bg-white/10 transition-colors">
            <MessageCircle size={32} className="text-white" />
          </div>
          <span className="text-white text-xs font-semibold">{formatNumber(realTimeStats.comment_count)}</span>
        </button>

        <button className="flex flex-col items-center gap-1 group">
          <div className="p-2 rounded-full group-hover:bg-white/10 transition-colors">
            <Bookmark size={32} className="text-white" />
          </div>
          <span className="text-white text-xs font-semibold">{formatNumber(bookmarks)}</span>
        </button>

        <button className="flex flex-col items-center gap-1 group">
          <div className="p-2 rounded-full group-hover:bg-white/10 transition-colors">
            <Share2 size={32} className="text-white" />
          </div>
          <span className="text-white text-xs font-semibold">{formatNumber(shares)}</span>
        </button>

        <div className="w-10 h-10 rounded-full bg-zinc-800 animate-spin mt-4 border-8 border-zinc-700 flex items-center justify-center" style={{ animationDuration: '4s' }}>
          <Music size={14} className="text-white" />
        </div>
      </div>

      {/* Bottom Info */}
      <div className="absolute bottom-4 left-4 right-20 z-10">
        <h3 className="text-white font-semibold text-lg mb-1">@{username}</h3>
        <p className="text-white text-sm line-clamp-2 mb-3">
          {description}
        </p>
        <div className="flex items-center gap-2">
          <Music size={16} className="text-white" />
          <span className="text-white text-sm truncate w-3/4">{songName}</span>
        </div>
      </div>
      
      {/* Gradient to make text readable */}
      <div className="absolute bottom-0 w-full h-1/2 bg-gradient-to-t from-black/80 via-black/40 to-transparent pointer-events-none" />
    </div>
  );
};
