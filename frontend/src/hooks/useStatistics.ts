/**
 * Custom hook for fetching and calculating reading statistics
 */

import { useMemo } from 'react';
import type {
  SessionsResponse,
  AggregateStats,
  StreakData,
  CalendarDay,
} from '../types/statistics';
import type { Document } from '../types/document';
import type { BookStatus } from '../types/pdf';
import { pdfService } from '../services/api';
import {
  calculateAggregateStats,
  calculateStreak,
  groupByDay,
} from '../utils/statisticsCalculations';
import { useAsyncData } from './useAsyncData';

async function fetchDocumentInfo(pdfId: number): Promise<Document | null> {
  // Fetch PDF info and progress using pdfId
  // Need to fetch both info and progress since /info doesn't include reading_progress
  try {
    const [pdfInfo, readingProgress] = await Promise.all([
      pdfService.getPDFInfo(pdfId),
      pdfService.getReadingProgress(pdfId).catch(() => null),
    ]);

    // Get status from reading progress or default to 'new'
    // The backend already computes and stores the status
    const status = (readingProgress?.status || 'new') as BookStatus;
    const manual_status = readingProgress?.manually_set ? status : undefined;

    // Convert reading progress to the format expected by Document type
    const reading_progress = readingProgress
      ? {
          last_page: readingProgress.last_page,
          total_pages: readingProgress.total_pages || pdfInfo.num_pages,
          progress_percentage: Math.round(
            (readingProgress.last_page /
              (readingProgress.total_pages || pdfInfo.num_pages)) *
              100
          ),
          last_updated: readingProgress.last_updated || '',
          status,
          status_updated_at: readingProgress.status_updated_at || '',
          manually_set: readingProgress.manually_set || false,
        }
      : null;

    return {
      ...pdfInfo,
      type: 'pdf' as const,
      computed_status: status,
      manual_status,
      reading_progress,
    };
  } catch {
    return null;
  }
}

async function fetchPdfStatistics(pdfId: number) {
  // Fetch session data and document info in parallel using pdfId
  const [sessions, documentInfo] = await Promise.all([
    pdfService.getReadingSessions(pdfId) as Promise<SessionsResponse>,
    fetchDocumentInfo(pdfId),
  ]);
  return { sessions, documentInfo };
}

export function useStatistics(pdfId: number | undefined) {
  const { data, loading, error } = useAsyncData(
    pdfId,
    fetchPdfStatistics,
    'Failed to load statistics'
  );

  const sessionsData = data?.sessions ?? null;

  // Calculate derived data using memoization
  const aggregateStats = useMemo<AggregateStats | null>(() => {
    if (!sessionsData?.sessions) return null;
    return calculateAggregateStats(sessionsData.sessions);
  }, [sessionsData]);

  const streakData = useMemo<StreakData | null>(() => {
    if (!sessionsData?.sessions) return null;
    return calculateStreak(sessionsData.sessions);
  }, [sessionsData]);

  const calendarData = useMemo<CalendarDay[] | null>(() => {
    if (!sessionsData?.sessions) return null;
    return groupByDay(sessionsData.sessions);
  }, [sessionsData]);

  return {
    sessions: sessionsData,
    documentInfo: data?.documentInfo ?? null,
    aggregateStats,
    streakData,
    calendarData,
    loading,
    error,
  };
}
