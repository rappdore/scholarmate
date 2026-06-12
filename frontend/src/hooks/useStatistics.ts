/**
 * Custom hook for fetching and calculating reading statistics
 */

import { useState, useEffect, useMemo } from 'react';
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

export function useStatistics(pdfId: number | undefined) {
  const [sessionsData, setSessionsData] = useState<SessionsResponse | null>(
    null
  );
  const [documentInfo, setDocumentInfo] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Cancellation guard: a slow response for a previous pdfId must not
    // overwrite newer state (and no setState after unmount).
    let cancelled = false;

    const fetchStatistics = async () => {
      if (pdfId === undefined) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Fetch session data and document info in parallel using pdfId
        const [sessionResponse, documentData] = await Promise.all([
          pdfService.getReadingSessions(pdfId) as Promise<SessionsResponse>,
          // Fetch PDF info and progress using pdfId
          // Need to fetch both info and progress since /info doesn't include reading_progress
          Promise.all([
            pdfService.getPDFInfo(pdfId),
            pdfService.getReadingProgress(pdfId).catch(() => null),
          ])
            .then(([pdfInfo, readingProgress]): Document => {
              // Get status from reading progress or default to 'new'
              // The backend already computes and stores the status
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const status = (readingProgress?.status || 'new') as any;
              const computed_status = status;
              const manual_status = readingProgress?.manually_set
                ? status
                : undefined;

              // Convert reading progress to the format expected by Document type
              const reading_progress = readingProgress
                ? {
                    last_page: readingProgress.last_page,
                    total_pages:
                      readingProgress.total_pages || pdfInfo.num_pages,
                    progress_percentage: Math.round(
                      (readingProgress.last_page /
                        (readingProgress.total_pages || pdfInfo.num_pages)) *
                        100
                    ),
                    last_updated: readingProgress.last_updated || '',
                    status: (readingProgress.status ?? 'new') as BookStatus,
                    status_updated_at: readingProgress.status_updated_at || '',
                    manually_set: readingProgress.manually_set || false,
                  }
                : null;

              return {
                ...pdfInfo,
                type: 'pdf' as const,
                computed_status,
                manual_status,
                reading_progress,
              };
            })
            .catch(() => null),
        ]);

        if (cancelled) return;
        setSessionsData(sessionResponse);
        setDocumentInfo(documentData);
      } catch (err) {
        console.error('[useStatistics] Error fetching statistics:', err);
        if (cancelled) return;
        setError('Failed to load statistics');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    if (pdfId !== undefined) {
      fetchStatistics();
    } else {
      setLoading(false);
    }

    return () => {
      cancelled = true;
    };
  }, [pdfId]);

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
    documentInfo,
    aggregateStats,
    streakData,
    calendarData,
    loading,
    error,
  };
}
