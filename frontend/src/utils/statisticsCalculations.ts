/**
 * Utility functions for calculating reading statistics
 */

import type {
  ReadingSession,
  AggregateStats,
  StreakData,
  CalendarDay,
} from '../types/statistics';
import {
  parseISO,
  format,
  isToday,
  isYesterday,
  differenceInDays,
} from 'date-fns';

/**
 * Calculate aggregate statistics from session data
 */
export function calculateAggregateStats(
  sessions: ReadingSession[]
): AggregateStats {
  if (sessions.length === 0) {
    return {
      total_sessions: 0,
      total_pages_read: 0,
      total_time_spent_seconds: 0,
      overall_avg_time_per_page: 0,
      fastest_page_time: 0,
      slowest_page_time: 0,
      first_read_date: '',
      last_read_date: '',
      longest_session_pages: 0,
      shortest_session_pages: 0,
      avg_pages_per_session: 0,
    };
  }

  const totalPages = sessions.reduce((sum, s) => sum + s.pages_read, 0);
  const totalTime = sessions.reduce(
    (sum, s) => sum + s.pages_read * s.average_time_per_page,
    0
  );
  const avgTimesPerPage = sessions.map(s => s.average_time_per_page);
  const pagesPerSession = sessions.map(s => s.pages_read);

  return {
    total_sessions: sessions.length,
    total_pages_read: totalPages,
    total_time_spent_seconds: totalTime,
    overall_avg_time_per_page: totalPages > 0 ? totalTime / totalPages : 0,
    fastest_page_time: Math.min(...avgTimesPerPage),
    slowest_page_time: Math.max(...avgTimesPerPage),
    first_read_date: sessions[sessions.length - 1].session_start, // Sessions are DESC
    last_read_date: sessions[0].session_start, // Most recent session start time
    longest_session_pages: Math.max(...pagesPerSession),
    shortest_session_pages: Math.min(...pagesPerSession),
    avg_pages_per_session: totalPages / sessions.length,
  };
}

/**
 * Calculate reading streak from session data
 */
export function calculateStreak(sessions: ReadingSession[]): StreakData {
  if (sessions.length === 0) {
    return {
      current_streak: 0,
      longest_streak: 0,
      reading_days: [],
    };
  }

  // Get unique dates (YYYY-MM-DD format)
  const uniqueDates = Array.from(
    new Set(sessions.map(s => format(parseISO(s.session_start), 'yyyy-MM-dd')))
  )
    .sort()
    .reverse(); // Most recent first

  // Calculate current streak
  let currentStreak = 0;
  const today = format(new Date(), 'yyyy-MM-dd');
  const yesterday = format(new Date(Date.now() - 86400000), 'yyyy-MM-dd');

  // Check if we have activity today or yesterday (streak is still alive)
  if (uniqueDates[0] === today || uniqueDates[0] === yesterday) {
    currentStreak = 1;
    let checkDate = parseISO(uniqueDates[0]);

    for (let i = 1; i < uniqueDates.length; i++) {
      const prevDate = parseISO(uniqueDates[i]);
      const diff = differenceInDays(checkDate, prevDate);

      if (diff === 1) {
        currentStreak++;
        checkDate = prevDate;
      } else {
        break;
      }
    }
  }

  // Calculate longest streak
  let longestStreak = 0;
  let tempStreak = 1;

  for (let i = 1; i < uniqueDates.length; i++) {
    const diff = differenceInDays(
      parseISO(uniqueDates[i - 1]),
      parseISO(uniqueDates[i])
    );

    if (diff === 1) {
      tempStreak++;
      longestStreak = Math.max(longestStreak, tempStreak);
    } else {
      tempStreak = 1;
    }
  }
  longestStreak = Math.max(longestStreak, tempStreak);

  return {
    current_streak: currentStreak,
    longest_streak: longestStreak,
    reading_days: uniqueDates,
  };
}

/**
 * Group sessions by day for calendar heatmap
 */
export function groupByDay(sessions: ReadingSession[]): CalendarDay[] {
  const dayMap = new Map<string, CalendarDay>();

  sessions.forEach(session => {
    const date = format(parseISO(session.session_start), 'yyyy-MM-dd');
    const existing = dayMap.get(date);

    if (existing) {
      existing.sessions += 1;
      existing.pages_read += session.pages_read;
      existing.total_time_seconds +=
        session.pages_read * session.average_time_per_page;
    } else {
      dayMap.set(date, {
        date,
        sessions: 1,
        pages_read: session.pages_read,
        total_time_seconds: session.pages_read * session.average_time_per_page,
      });
    }
  });

  return Array.from(dayMap.values()).sort((a, b) =>
    b.date.localeCompare(a.date)
  );
}

/**
 * Format seconds into human-readable time string
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.round((seconds % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
}

/**
 * Format date for display
 */
export function formatReadableDate(dateString: string): string {
  const date = parseISO(dateString);

  if (isToday(date)) {
    return `Today, ${format(date, 'h:mm a')}`;
  } else if (isYesterday(date)) {
    return `Yesterday, ${format(date, 'h:mm a')}`;
  } else {
    return format(date, 'MMM d, yyyy, h:mm a');
  }
}
