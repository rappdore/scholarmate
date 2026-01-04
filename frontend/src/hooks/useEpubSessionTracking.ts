/**
 * Custom hook for tracking EPUB reading sessions.
 *
 * Tracks scroll progress through sections and calculates words read.
 * Sends updates to backend on section change, unmount, and visibility change.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { epubService } from '../services/epubService';
import { API_BASE_URL } from '../services/config';
import type { NavSection } from '../types/epubStatistics';

// Generate UUID using crypto API (available in modern browsers)
const generateUUID = (): string => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

interface UseEpubSessionTrackingProps {
  epubId: number | undefined;
  navSections: NavSection[] | undefined;
  currentNavId: string | null;
  scrollProgress: number; // 0.0 - 1.0 within current section
  bookStatus: 'new' | 'reading' | 'finished';
}

interface UseEpubSessionTrackingReturn {
  trackingEnabled: boolean;
  setTrackingEnabled: (enabled: boolean) => void;
  wordsRead: number;
  sessionId: string;
}

export function useEpubSessionTracking({
  epubId,
  navSections,
  currentNavId,
  scrollProgress,
  bookStatus,
}: UseEpubSessionTrackingProps): UseEpubSessionTrackingReturn {
  // Generate session ID once per mount
  const [sessionId] = useState(() => generateUUID());

  // Tracking is ON by default only if book status is 'reading'
  const [trackingEnabled, setTrackingEnabled] = useState(
    bookStatus === 'reading'
  );

  // Track scroll progress per section
  const sectionProgressRef = useRef<Map<string, number>>(new Map());

  // Session start time for calculating time spent
  const sessionStartTimeRef = useRef<number>(Date.now());

  // Track previous nav ID to detect section changes
  const prevNavIdRef = useRef<string | null>(null);

  // Flag to track if we've sent at least one update
  const hasUpdatedRef = useRef<boolean>(false);

  // Refs to avoid stale closures in cleanup effect
  const trackingEnabledRef = useRef(trackingEnabled);
  const epubIdRef = useRef(epubId);

  // Keep refs in sync with state
  useEffect(() => {
    trackingEnabledRef.current = trackingEnabled;
  }, [trackingEnabled]);

  useEffect(() => {
    epubIdRef.current = epubId;
  }, [epubId]);

  // Update tracking enabled when book status changes
  useEffect(() => {
    setTrackingEnabled(bookStatus === 'reading');
  }, [bookStatus]);

  // Update section progress when scroll changes
  useEffect(() => {
    if (!trackingEnabled || !currentNavId) return;

    const currentProgress = sectionProgressRef.current.get(currentNavId) || 0;
    // Only update if progress increased (user scrolled down)
    if (scrollProgress > currentProgress) {
      sectionProgressRef.current.set(currentNavId, scrollProgress);
    }
  }, [currentNavId, scrollProgress, trackingEnabled]);

  // Calculate total words read based on section progress
  const calculateWordsRead = useCallback((): number => {
    if (!navSections || navSections.length === 0) return 0;

    let totalWords = 0;
    for (const section of navSections) {
      const progress = sectionProgressRef.current.get(section.id) || 0;
      const wordCount = section.word_count || 0;
      totalWords += Math.floor(wordCount * progress);
    }
    return totalWords;
  }, [navSections]);

  // Send update to backend
  const sendUpdate = useCallback(async () => {
    if (!trackingEnabled || !epubId) return;

    const wordsRead = calculateWordsRead();
    const timeSpentSeconds = (Date.now() - sessionStartTimeRef.current) / 1000;

    // Skip trivial sessions (less than 5 seconds and no words)
    if (wordsRead === 0 && timeSpentSeconds < 5) return;

    try {
      await epubService.updateReadingSession(
        sessionId,
        epubId,
        wordsRead,
        timeSpentSeconds
      );
      hasUpdatedRef.current = true;
      console.log(
        `[EPUB Session] Updated: ${wordsRead} words, ${timeSpentSeconds.toFixed(1)}s`
      );
    } catch (error) {
      // Fire-and-forget: log but don't throw
      console.error('[EPUB Session] Failed to update:', error);
    }
  }, [sessionId, epubId, trackingEnabled, calculateWordsRead]);

  // Trigger: Section change
  useEffect(() => {
    if (!currentNavId || currentNavId === prevNavIdRef.current) return;

    // Don't send update on first section load (no previous section)
    if (prevNavIdRef.current !== null) {
      sendUpdate();
    }

    prevNavIdRef.current = currentNavId;
  }, [currentNavId, sendUpdate]);

  // Trigger: Unmount (cleanup)
  // Uses refs to read current values, avoiding stale closure issues
  useEffect(() => {
    return () => {
      // Send final update on unmount
      // We need to call the update synchronously since async won't complete on unmount
      // Use a synchronous approach via beacon API if available, otherwise best-effort
      // Read from refs to get current values, not stale closure values
      if (!trackingEnabledRef.current || !epubIdRef.current) return;

      const wordsRead = calculateWordsRead();
      const timeSpentSeconds =
        (Date.now() - sessionStartTimeRef.current) / 1000;

      if (wordsRead === 0 && timeSpentSeconds < 5) return;

      // Use navigator.sendBeacon for reliable delivery on page unload
      const data = JSON.stringify({
        session_id: sessionId,
        epub_id: epubIdRef.current,
        words_read: wordsRead,
        time_spent_seconds: timeSpentSeconds,
      });

      const blob = new Blob([data], { type: 'application/json' });
      const url = `${API_BASE_URL}/api/epub/reading-statistics/session/update`;

      if (navigator.sendBeacon) {
        navigator.sendBeacon(url, blob);
        console.log('[EPUB Session] Sent final update via beacon');
      } else {
        // Fallback: try async (may not complete)
        fetch(url, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: data,
          keepalive: true,
        }).catch(() => {
          // Ignore errors on unmount
        });
      }
    };
  }, [sessionId, calculateWordsRead]);

  // Trigger: Visibility change (user switches tabs/minimizes)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        sendUpdate();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [sendUpdate]);

  return {
    trackingEnabled,
    setTrackingEnabled,
    wordsRead: calculateWordsRead(),
    sessionId,
  };
}
