import React, { useState, useRef, useEffect } from 'react';
import { VideoCard } from './VideoCard';

interface VideoData {
  id: string;
  videoUrl: string;
  username: string;
  description: string;
  songName: string;
  likes: number;
  comments: number;
  shares: number;
  bookmarks: number;
  tags?: string[];
}

interface FeedProps {
  videos: VideoData[];
  userId: string | null;
  sessionId: string | null;
  onRefreshSessionStats: (activeSessionId?: string | null) => Promise<void>;
  onLoadMore?: () => void;
  swipeTrigger?: { direction: 'up' | 'down'; speed: 'slow' | 'fast'; timestamp: number } | null;
  onVideoActivated?: (videoId: string) => void;
}

export const Feed: React.FC<FeedProps> = ({
  videos,
  userId,
  sessionId,
  onRefreshSessionStats,
  onLoadMore,
  swipeTrigger,
  onVideoActivated
}) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const [swipeSpeed, setSwipeSpeed] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const isProgrammaticScroll = useRef(false);
  const programmaticSpeed = useRef<number | null>(null);
  // Track the videos.length at which we last triggered onLoadMore,
  // so we don't spam it for every index that passes the threshold.
  const lastLoadMoreAt = useRef<number>(-1);

  // When new videos arrive (batch appended), reset the guard so the NEXT
  // batch boundary can be triggered when user reaches the new end.
  useEffect(() => {
    // lastLoadMoreAt holds the old videos.length when we fired. If videos.length
    // is now bigger, a fresh batch landed → allow firing again at the new threshold.
    if (lastLoadMoreAt.current > 0 && videos.length > lastLoadMoreAt.current) {
      lastLoadMoreAt.current = -1;
    }
  }, [videos.length]);

  useEffect(() => {
    if (!swipeTrigger || !containerRef.current) return;

    const container = containerRef.current;
    const cardHeight = container.clientHeight;
    let targetIndex = activeIndex;

    if (swipeTrigger.direction === 'up') {
      targetIndex = Math.min(videos.length - 1, activeIndex + 1);
    } else {
      targetIndex = Math.max(0, activeIndex - 1);
    }

    if (targetIndex === activeIndex) return;

    isProgrammaticScroll.current = true;
    const speedVal = swipeTrigger.speed === 'fast' ? 950 : 150;
    programmaticSpeed.current = speedVal;
    setSwipeSpeed(speedVal);

    const targetScrollTop = targetIndex * cardHeight;
    container.scrollTo({ top: targetScrollTop, behavior: 'smooth' });

    const timer = setTimeout(() => {
      isProgrammaticScroll.current = false;
      programmaticSpeed.current = null;
    }, 600);

    return () => clearTimeout(timer);
  }, [swipeTrigger]);
  const scrollStartTime = useRef<number | null>(null);
  const scrollStartTop = useRef<number | null>(null);
  const scrollTimeout = useRef<any>(null);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const container = e.currentTarget;
    const scrollPos = container.scrollTop;
    const cardHeight = container.clientHeight;

    // Detect scroll start
    if (scrollStartTime.current === null) {
      scrollStartTime.current = Date.now();
      scrollStartTop.current = scrollPos;
    }

    if (scrollTimeout.current) {
      clearTimeout(scrollTimeout.current);
    }

    // Reset trackers on scroll stop (so next scroll is clean)
    scrollTimeout.current = setTimeout(() => {
      scrollStartTime.current = null;
      scrollStartTop.current = null;
    }, 150);

    // Calculate candidate index + displacement from current active position
    const rawOffset = scrollPos / cardHeight;
    const candidateIndex = Math.round(rawOffset);
    // How far user has scrolled away from the current active card (0.0-1.0)
    const displacement = Math.abs(rawOffset - activeIndex);

    const SCROLL_THRESHOLD = 0.20; // 20% card height

    if (
      candidateIndex !== activeIndex &&
      candidateIndex >= 0 &&
      candidateIndex < videos.length &&
      displacement >= SCROLL_THRESHOLD
    ) {
      // Calculate speed immediately on index change
      if (isProgrammaticScroll.current) {
        if (programmaticSpeed.current !== null) {
          setSwipeSpeed(programmaticSpeed.current);
        }
      } else if (scrollStartTime.current !== null && scrollStartTop.current !== null) {
        const dt = (Date.now() - scrollStartTime.current) / 1000;
        const dy = Math.abs(scrollPos - scrollStartTop.current);
        const speed = dt > 0.05 ? dy / dt : 0;
        setSwipeSpeed(speed);

        // Reset scroll start trackers for the next swipe
        scrollStartTime.current = Date.now();
        scrollStartTop.current = scrollPos;
      }
      // Trigger fetch when approaching the end of the current batch (last 2 videos).
      // Guard: only fire once per batch size boundary to prevent spam.
      if (
        candidateIndex > activeIndex &&
        candidateIndex >= videos.length - 2 &&
        lastLoadMoreAt.current !== videos.length
      ) {
        lastLoadMoreAt.current = videos.length;
        if (onLoadMore) {
          onLoadMore();
        }
      }
      setActiveIndex(candidateIndex);
    }
  };

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="w-full h-full overflow-y-scroll snap-y snap-mandatory no-scrollbar flex flex-col scroll-smooth"
      style={{ scrollSnapType: 'y mandatory' }}
    >
      {videos.map((video, index) => (
        <VideoCard
          key={video.id}
          index={index}
          activeIndex={activeIndex}
          videoUrl={video.videoUrl}
          username={video.username}
          description={video.description}
          songName={video.songName}
          likes={video.likes}
          comments={video.comments}
          shares={video.shares}
          bookmarks={video.bookmarks}
          isActive={index === activeIndex}
          videoId={video.id}
          topic={video.tags && video.tags.length > 0 ? video.tags[0] : 'general'}
          userId={userId}
          sessionId={sessionId}
          onRefreshSessionStats={onRefreshSessionStats}
          swipeSpeed={swipeSpeed}
          onVideoActivated={onVideoActivated}
        />
      ))}
    </div>
  );
};
