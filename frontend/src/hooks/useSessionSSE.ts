/**
 * useSessionSSE
 *
 * Opens a Server-Sent Events connection to
 *   GET /api/v1/sessions/{sessionId}/events
 * and invokes `onMessage` with each { fatigue_score, adaptive_state } update.
 *
 * Replaces the previous 3-second polling (refreshSessionStats interval).
 * The connection is automatically closed when the component unmounts or
 * when `sessionId` becomes null.
 *
 * Browser support: EventSource is available in all modern browsers.
 * If not available, an alert is shown (per spec for hackathon — no fallback).
 */

import { useEffect } from 'react';

export interface SessionSSEPayload {
  fatigue_score: number;
  adaptive_state: string;
}

export function useSessionSSE(
  sessionId: string | null,
  onMessage: (data: SessionSSEPayload) => void
) {
  useEffect(() => {
    if (!sessionId) return;

    // Browser compatibility guard
    if (!window.EventSource) {
      alert('Trình duyệt của bạn không hỗ trợ EventSource (SSE)!');
      return;
    }

    const url = `http://localhost:8033/api/v1/sessions/${sessionId}/events`;
    const es = new EventSource(url);

    es.onopen = () => {
      console.log(`[SSE] Connected to session stream: ${sessionId}`);
    };

    es.onmessage = (e: MessageEvent) => {
      try {
        const payload: SessionSSEPayload = JSON.parse(e.data);
        onMessage(payload);
      } catch (err) {
        console.error('[SSE] JSON parse error:', err);
      }
    };

    es.onerror = (err) => {
      // EventSource auto-reconnects on error; we just log it.
      console.warn('[SSE] Connection error (will auto-reconnect):', err);
    };

    return () => {
      es.close();
      console.log(`[SSE] Disconnected from session stream: ${sessionId}`);
    };
    // onMessage is intentionally not in deps — callers must wrap it in useCallback
    // to prevent tearing down/recreating the SSE connection on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);
}
