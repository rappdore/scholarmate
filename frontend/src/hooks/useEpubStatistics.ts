/**
 * Custom hook for fetching and calculating EPUB reading statistics
 */

import { useMemo } from 'react';
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
import { useAsyncData } from './useAsyncData';

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

async function fetchEpubStatistics(epubId: number) {
  // Fetch session data, document info, and progress in parallel
  const [sessions, documentInfo, progress] = await Promise.all([
    epubService.getReadingSessions(epubId),
    epubService.getEPUBInfo(epubId).catch(() => null),
    epubService.getEPUBProgress(epubId).catch(() => null),
  ]);
  return { sessions, documentInfo, progress };
}

export function useEpubStatistics(
  epubId: number | undefined
): UseEpubStatisticsReturn {
  const { data, loading, error } = useAsyncData(
    epubId,
    fetchEpubStatistics,
    'Failed to load statistics'
  );

  const sessionsData = (data?.sessions as EpubSessionsResponse | null) ?? null;

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
    documentInfo: data?.documentInfo ?? null,
    progress: data?.progress ?? null,
    aggregateStats,
    streakData,
    calendarData,
    loading,
    error,
  };
}
