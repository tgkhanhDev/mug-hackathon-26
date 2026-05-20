import React, { useState, useRef } from 'react';
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
}

export const Feed: React.FC<FeedProps> = ({ videos }) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const container = e.currentTarget;
    const scrollPos = container.scrollTop;
    const cardHeight = container.clientHeight;
    
    // Calculate current active index
    const index = Math.round(scrollPos / cardHeight);
    if (index !== activeIndex && index >= 0 && index < videos.length) {
      setActiveIndex(index);
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
        />
      ))}
    </div>
  );
};
