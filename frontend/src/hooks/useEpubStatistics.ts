/**
 * Custom hook for fetching and calculating EPUB reading statistics
 */

import { useState, useEffect, useMemo } from 'react';
import type {
  EpubSessionsResponse,
  EpubAggregateStats,
  EpubStreakData,
  EpubCalendarDay,
} from '../types/epubStatistics';
import type { EPUBDocumentInfo } from '../types/document';
import { epubService, type EPUBProgress } from '../services/epubService';
import {
  calculateEpubAggregateStats,
  calculateEpubStreak,
  groupEpubByDay,
} from '../utils/epubStatisticsCalculations';

interface UseEpubStatisticsReturn {
  sessions: EpubSessionsResponse | null;
  documentInfo: EPUBDocumentInfo | null;
  progress: EPUBProgress | null;
  aggregateStats: EpubAggregateStats | null;
  streakData: EpubStreakData | null;
  calendarData: EpubCalendarDay[] | null;
  loading: boolean;
  error: string | null;
}

export function useEpubStatistics(
  epubId: number | undefined
): UseEpubStatisticsReturn {
  const [sessionsData, setSessionsData] = useState<EpubSessionsResponse | null>(
    null
  );
  const [documentInfo, setDocumentInfo] = useState<EPUBDocumentInfo | null>(
    null
  );
  const [progress, setProgress] = useState<EPUBProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatistics = async () => {
      if (epubId === undefined) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Fetch session data, document info, and progress in parallel
        const [sessionsResponse, epubInfo, epubProgress] = await Promise.all([
          epubService.getReadingSessions(epubId),
          epubService.getEPUBInfo(epubId).catch(() => null),
          epubService.getEPUBProgress(epubId).catch(() => null),
        ]);

        console.log('[useEpubStatistics] Sessions Response:', sessionsResponse);
        console.log('[useEpubStatistics] Document Info:', epubInfo);
        console.log('[useEpubStatistics] Progress:', epubProgress);

        setSessionsData(sessionsResponse);
        setDocumentInfo(epubInfo);
        setProgress(epubProgress);
      } catch (err) {
        console.error('[useEpubStatistics] Error fetching statistics:', err);
        setError('Failed to load statistics');
      } finally {
        setLoading(false);
      }
    };

    if (epubId !== undefined) {
      fetchStatistics();
    } else {
      setLoading(false);
    }
  }, [epubId]);

  // Calculate derived data using memoization
  const aggregateStats = useMemo<EpubAggregateStats | null>(() => {
    if (!sessionsData?.sessions) return null;
    return calculateEpubAggregateStats(sessionsData.sessions);
  }, [sessionsData]);

  const streakData = useMemo<EpubStreakData | null>(() => {
    if (!sessionsData?.sessions) return null;
    return calculateEpubStreak(sessionsData.sessions);
  }, [sessionsData]);

  const calendarData = useMemo<EpubCalendarDay[] | null>(() => {
    if (!sessionsData?.sessions) return null;
    return groupEpubByDay(sessionsData.sessions);
  }, [sessionsData]);

  return {
    sessions: sessionsData,
    documentInfo,
    progress,
    aggregateStats,
    streakData,
    calendarData,
    loading,
    error,
  };
}
