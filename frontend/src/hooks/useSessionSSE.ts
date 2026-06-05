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

import { useEffect, useRef } from 'react';

export interface SessionSSEPayload {
  fatigue_score: number;
  adaptive_state: string;
}

export function useSessionSSE(
  sessionId: string | null,
  onMessage: (data: SessionSSEPayload) => void
) {
  // Use a mutable ref to store the latest callback.
  // This avoids stale closures without having to teardown and recreate the EventSource connection.
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }); // Runs on every render to ensure the ref has the latest callback with correct closure variables

  useEffect(() => {
    if (!sessionId) return;

    // Browser compatibility guard
    if (!window.EventSource) {
      alert('Trình duyệt của bạn không hỗ trợ EventSource (SSE)!');
      return;
    }

    const url = `/api/v1/sessions/${sessionId}/events`;
    const es = new EventSource(url);

    es.onopen = () => {
      console.log(`[SSE] Connected to session stream: ${sessionId}`);
    };

    es.onmessage = (e: MessageEvent) => {
      try {
        const payload: SessionSSEPayload = JSON.parse(e.data);
        onMessageRef.current(payload);
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
  }, [sessionId]);
}
