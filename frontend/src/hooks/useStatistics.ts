/**
 * Custom hook for fetching and calculating reading statistics
 */

import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import type {
  SessionsResponse,
  AggregateStats,
  StreakData,
  CalendarDay,
} from '../types/statistics';
import {
  calculateAggregateStats,
  calculateStreak,
  groupByDay,
} from '../utils/statisticsCalculations';

export function useStatistics(filename: string) {
  const [sessionsData, setSessionsData] = useState<SessionsResponse | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatistics = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch session data from single endpoint
        const url = `/api/reading-statistics/sessions/${encodeURIComponent(filename)}`;
        console.log('[useStatistics] Fetching from URL:', url);
        const response = await axios.get<SessionsResponse>(url);
        console.log('[useStatistics] Response:', response.data);
        setSessionsData(response.data);
      } catch (err) {
        console.error('[useStatistics] Error fetching statistics:', err);
        setError('Failed to load statistics');
      } finally {
        setLoading(false);
      }
    };

    if (filename) {
      fetchStatistics();
    }
  }, [filename]);

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
    aggregateStats,
    streakData,
    calendarData,
    loading,
    error,
  };
}
