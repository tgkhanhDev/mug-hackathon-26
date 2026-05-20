import { useState, useEffect } from 'react';
import { WS_URL } from '../api/client';

export interface VideoStats {
  like_count: number;
  view_count: number;
  comment_count: number;
}

export function useVideoStats(videoId: string, initialStats: VideoStats, isActive: boolean) {
  const [stats, setStats] = useState<VideoStats>(initialStats);

  useEffect(() => {
    // We only connect when the video is active (in viewport)
    if (!isActive) return;

    let ws: WebSocket;
    
    const connect = () => {
      ws = new WebSocket(`${WS_URL}/${videoId}`);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'stats_snapshot' || data.event === 'stats_update') {
            setStats({
              like_count: data.like_count,
              view_count: data.view_count,
              comment_count: data.comment_count,
            });
          }
        } catch (error) {
          console.error('WebSocket message parsing error:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };

    connect();

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [videoId, isActive]);

  return stats;
}
