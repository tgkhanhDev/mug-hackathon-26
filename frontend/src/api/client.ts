import useSWR from 'swr';

export const API_URL = 'http://localhost:8033/api/v1';
export const WS_URL = 'ws://localhost:8033/api/v1/ws/stats';

export const fetcher = (url: string) => fetch(url).then((res) => {
  if (!res.ok) {
    return res.json().then(err => { throw err; });
  }
  return res.json();
});

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

export interface SessionResponse {
  id: string;
  user_id: string;
  started_at: string;
  ended_at: string | null;
  total_videos_watched: number;
  fatigue_score: number;
  adaptive_state: string;
  high_intensity_count: number;
  low_intensity_count: number;
  avg_watch_duration: number;
  avg_swipe_speed: number;
}

export interface VectorStatusResponse {
  user_id: string;
  username: string;
  interest_tags: string[];
  vector_dimensions: number;
  vector_magnitude: number;
  has_vector: boolean;
  updated_at: string | null;
}

export function useTrendingVideos(limit: number = 10) {
  const { data, error, isLoading, mutate } = useSWR<VideoResponse[]>(`${API_URL}/videos/trending?limit=${limit}`, fetcher);
  return {
    videos: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function usePersonalizedFeed(userId: string | null, limit: number = 10, fetchKey: number = 0, excludeIds: string[] = []) {
  // Build URL with exclude param so backend can dedup server-side
  const excludeParam = excludeIds.length > 0 ? `&exclude=${excludeIds.join(',')}` : '';
  const { data, error, isLoading, mutate } = useSWR<VideoResponse[]>(
    userId ? `${API_URL}/feed/${userId}?limit=${limit}${excludeParam}&_k=${fetchKey}` : null,
    fetcher,
    { revalidateOnFocus: false, revalidateOnReconnect: false }
  );
  return {
    videos: data,
    isLoading,
    isError: error,
    mutate
  };
}

export async function registerUser(username: string, email?: string, password?: string, interestTags: string[] = []) {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email: email || '', password: password || '', interest_tags: interestTags })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Registration failed');
  }
  return await res.json();
}

export async function loginUser(username: string, password?: string) {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password: password || '' })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Login failed');
  }
  return await res.json();
}

export async function startSession(userId: string): Promise<SessionResponse> {
  const res = await fetch(`${API_URL}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to start session');
  }
  return await res.json();
}

export async function endSession(sessionId: string): Promise<SessionResponse> {
  const res = await fetch(`${API_URL}/sessions/${sessionId}/end`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' }
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to end session');
  }
  return await res.json();
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const res = await fetch(`${API_URL}/sessions/${sessionId}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to fetch session details');
  }
  return await res.json();
}

export async function getUserVectorStatus(userId: string): Promise<VectorStatusResponse> {
  const res = await fetch(`${API_URL}/users/${userId}/vector-status`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to fetch vector status');
  }
  return await res.json();
}

export async function sendInteraction(
  videoId: string,
  type: string,
  percentage: number = 0.5,
  userId?: string,
  sessionId?: string,
  watchDuration: number = 0.0,
  swipeSpeed: number = 0.0,
  replayCount: number = 0
) {
  if (!userId || !sessionId) {
    console.warn('sendInteraction skipped: user or session is missing');
    return;
  }
  try {
    const res = await fetch(`${API_URL}/interactions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: userId,
        video_id: videoId,
        session_id: sessionId,
        type,
        watch_duration: watchDuration,
        watch_percentage: percentage,
        swipe_speed: swipeSpeed,
        replay_count: replayCount
      })
    });
    return await res.json();
  } catch (error) {
    console.error('Error sending interaction:', error);
  }
}

export async function sendBehaviorLog(
  videoId: string,
  topic: string,
  userId?: string,
  sessionId?: string,
  swipeSpeed: number = 0.0,
  watchDuration: number = 0.0,
  isInteraction: boolean = false
) {
  if (!userId || !sessionId) {
    console.warn('sendBehaviorLog skipped: user or session is missing');
    return;
  }
  try {
    const res = await fetch(`${API_URL}/behavior-logs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: userId,
        session_id: sessionId,
        video_id: videoId,
        swipe_speed: swipeSpeed,
        watch_duration: watchDuration,
        is_interaction: isInteraction,
        topic,
        consecutive_same_topic: 0
      })
    });
    return await res.json();
  } catch (error) {
    console.error('Error sending behavior log:', error);
  }
}

