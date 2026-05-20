import useSWR from 'swr';

export const API_URL = 'http://localhost:8000/api/v1';
export const WS_URL = 'ws://localhost:8000/ws/stats';

// A mock user ID and session ID for demo purposes
export const MOCK_USER_ID = '664f3316e11b333444455555';
export const MOCK_SESSION_ID = '664f3316e11b333444455556';

export const fetcher = (url: string) => fetch(url).then((res) => res.json());

export interface VideoResponse {
  id: string;
  title: string;
  description: string;
  url: string;
  thumbnail_url: string;
  tags: string[];
  category: string;
  intensity_level: string;
  view_count: number;
  like_count: number;
  comment_count: number;
  trending_score: number;
  creator_id: string;
}

export function useTrendingVideos() {
  const { data, error, isLoading } = useSWR<VideoResponse[]>(`${API_URL}/videos/trending`, fetcher);
  return {
    videos: data,
    isLoading,
    isError: error
  };
}

export async function sendInteraction(videoId: string, type: string, percentage: number = 0.5) {
  try {
    const res = await fetch(`${API_URL}/interactions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: MOCK_USER_ID,
        video_id: videoId,
        session_id: MOCK_SESSION_ID,
        type,
        watch_duration: 5.0,
        watch_percentage: percentage,
        swipe_speed: 0.0,
        replay_count: 0
      })
    });
    return await res.json();
  } catch (error) {
    console.error('Error sending interaction:', error);
  }
}

export async function sendBehaviorLog(videoId: string, topic: string) {
  try {
    const res = await fetch(`${API_URL}/behavior-logs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: MOCK_USER_ID,
        session_id: MOCK_SESSION_ID,
        video_id: videoId,
        swipe_speed: 100.0,
        watch_duration: 3.0,
        is_interaction: false,
        topic,
        consecutive_same_topic: 0
      })
    });
    return await res.json();
  } catch (error) {
    console.error('Error sending behavior log:', error);
  }
}
