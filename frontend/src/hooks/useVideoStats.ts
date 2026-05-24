import { useEffect, useRef, useCallback } from 'react';
import { WS_URL } from '../api/client';

export interface VideoStats {
  like_count: number;
  view_count: number;
  comment_count: number;
}

type StatsListener = (stats: VideoStats) => void;

/**
 * Singleton WebSocket connection manager for a session.
 * Opens ONE connection per session, and multiplexes video
 * subscribe/unsubscribe messages through it.
 */
class SessionWSManager {
  private ws: WebSocket | null = null;
  private sessionId: string | null = null;
  private listeners: Map<string, Set<StatsListener>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isConnecting = false;

  connect(sessionId: string) {
    if (this.sessionId === sessionId && this.ws?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    this.disconnect();
    this.sessionId = sessionId;
    this._doConnect();
  }

  private _doConnect() {
    if (!this.sessionId || this.isConnecting) return;
    this.isConnecting = true;

    const ws = new WebSocket(`${WS_URL}/${this.sessionId}`);

    ws.onopen = () => {
      this.isConnecting = false;
      this.ws = ws;
      // Re-subscribe to any videos that were subscribed before reconnect
      for (const videoId of this.listeners.keys()) {
        if (this.listeners.get(videoId)!.size > 0) {
          ws.send(JSON.stringify({ action: 'subscribe', video_id: videoId }));
        }
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'stats_snapshot' || data.event === 'stats_update') {
          const videoListeners = this.listeners.get(data.video_id);
          if (videoListeners) {
            const stats: VideoStats = {
              like_count: data.like_count,
              view_count: data.view_count,
              comment_count: data.comment_count,
            };
            videoListeners.forEach(fn => fn(stats));
          }
        }
      } catch (err) {
        console.error('WS message parse error:', err);
      }
    };

    ws.onerror = () => {
      this.isConnecting = false;
    };

    ws.onclose = () => {
      this.isConnecting = false;
      this.ws = null;
      // Auto-reconnect after 2s if we still have a sessionId
      if (this.sessionId) {
        this.reconnectTimer = setTimeout(() => this._doConnect(), 2000);
      }
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.sessionId = null;
    this.isConnecting = false;
  }

  subscribe(videoId: string, listener: StatsListener) {
    if (!this.listeners.has(videoId)) {
      this.listeners.set(videoId, new Set());
    }
    const isFirst = this.listeners.get(videoId)!.size === 0;
    this.listeners.get(videoId)!.add(listener);

    // Only send subscribe message if this is the first listener for this video
    if (isFirst && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'subscribe', video_id: videoId }));
    }
  }

  unsubscribe(videoId: string, listener: StatsListener) {
    const videoListeners = this.listeners.get(videoId);
    if (!videoListeners) return;

    videoListeners.delete(listener);

    // Only send unsubscribe message if no more listeners for this video
    if (videoListeners.size === 0) {
      this.listeners.delete(videoId);
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: 'unsubscribe', video_id: videoId }));
      }
    }
  }
}

// Singleton instance — shared across all VideoCard components
const sessionWS = new SessionWSManager();

/**
 * Connect the session-level WebSocket. Call once when session starts.
 */
export function connectSessionWS(sessionId: string) {
  sessionWS.connect(sessionId);
}

/**
 * Disconnect the session-level WebSocket. Call when session ends / logout.
 */
export function disconnectSessionWS() {
  sessionWS.disconnect();
}

/**
 * Hook for individual VideoCard components to subscribe to real-time stats.
 * Internally uses the shared session-level WebSocket — no new connections created.
 */
export function useVideoStats(videoId: string, initialStats: VideoStats, isActive: boolean) {
  const statsRef = useRef<VideoStats>(initialStats);
  const forceUpdate = useForceUpdate();

  const listener = useCallback((newStats: VideoStats) => {
    statsRef.current = newStats;
    forceUpdate();
  }, [forceUpdate]);

  useEffect(() => {
    if (!isActive) return;

    sessionWS.subscribe(videoId, listener);

    return () => {
      sessionWS.unsubscribe(videoId, listener);
    };
  }, [videoId, isActive, listener]);

  return statsRef.current;
}

/** Tiny helper to trigger re-render */
function useForceUpdate() {
  const [, setState] = __useState(0);
  return useCallback(() => setState(c => c + 1), []);
}

// Use React's useState under a different name to avoid lint confusion
import { useState as __useState } from 'react';
