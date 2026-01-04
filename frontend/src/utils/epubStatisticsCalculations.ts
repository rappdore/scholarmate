/**
 * Utility functions for calculating EPUB reading statistics
 */

import type {
  EpubReadingSession,
  EpubAggregateStats,
  EpubStreakData,
  EpubCalendarDay,
} from '../types/epubStatistics';
import { parseISO, format, differenceInDays } from 'date-fns';

// Estimated words per page for conversion to "pages"
const WORDS_PER_PAGE = 250;

/**
 * Calculate aggregate statistics from EPUB session data
 */
export function calculateEpubAggregateStats(
  sessions: EpubReadingSession[]
): EpubAggregateStats {
  if (sessions.length === 0) {
    return {
      total_sessions: 0,
      total_words_read: 0,
      total_time_spent_seconds: 0,
      avg_words_per_minute: 0,
      avg_words_per_session: 0,
      fastest_reading_speed: 0,
      slowest_reading_speed: 0,
      first_read_date: null,
      last_read_date: null,
      longest_session_words: 0,
      estimated_pages_read: 0,
    };
  }

  const totalWords = sessions.reduce((sum, s) => sum + s.words_read, 0);
  const totalTime = sessions.reduce((sum, s) => sum + s.time_spent_seconds, 0);

  // Calculate reading speeds (words per minute) for each session
  const speeds = sessions
    .filter(s => s.time_spent_seconds > 0 && s.words_read > 0)
    .map(s => (s.words_read / s.time_spent_seconds) * 60);

  const wordsPerSession = sessions.map(s => s.words_read);

  // Sort sessions by date to find first and last
  const sortedByDate = [...sessions].sort(
    (a, b) =>
      new Date(a.session_start).getTime() - new Date(b.session_start).getTime()
  );

  return {
    total_sessions: sessions.length,
    total_words_read: totalWords,
    total_time_spent_seconds: totalTime,
    avg_words_per_minute:
      totalTime > 0 ? Math.round((totalWords / totalTime) * 60) : 0,
    avg_words_per_session: Math.round(totalWords / sessions.length),
    fastest_reading_speed:
      speeds.length > 0 ? Math.round(Math.max(...speeds)) : 0,
    slowest_reading_speed:
      speeds.length > 0 ? Math.round(Math.min(...speeds)) : 0,
    first_read_date: sortedByDate[0]?.session_start || null,
    last_read_date:
      sortedByDate[sortedByDate.length - 1]?.session_start || null,
    longest_session_words: Math.max(...wordsPerSession),
    estimated_pages_read: Math.round(totalWords / WORDS_PER_PAGE),
  };
}

/**
 * Calculate reading streak from EPUB session data
 */
export function calculateEpubStreak(
  sessions: EpubReadingSession[]
): EpubStreakData {
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
 * Group EPUB sessions by day for calendar heatmap
 */
export function groupEpubByDay(
  sessions: EpubReadingSession[]
): EpubCalendarDay[] {
  const dayMap = new Map<string, EpubCalendarDay>();

  sessions.forEach(session => {
    const date = format(parseISO(session.session_start), 'yyyy-MM-dd');
    const existing = dayMap.get(date);

    if (existing) {
      existing.sessions += 1;
      existing.words_read += session.words_read;
      existing.total_time_seconds += session.time_spent_seconds;
    } else {
      dayMap.set(date, {
        date,
        sessions: 1,
        words_read: session.words_read,
        total_time_seconds: session.time_spent_seconds,
      });
    }
  });

  return Array.from(dayMap.values()).sort((a, b) =>
    b.date.localeCompare(a.date)
  );
}

/**
 * Format words count for display
 */
export function formatWordsCount(words: number): string {
  if (words < 1000) {
    return `${words}`;
  } else if (words < 1000000) {
    return `${(words / 1000).toFixed(1)}k`;
  } else {
    return `${(words / 1000000).toFixed(2)}M`;
  }
}

/**
 * Format reading speed for display
 */
export function formatReadingSpeed(wordsPerMinute: number): string {
  return `${Math.round(wordsPerMinute)} wpm`;
}

/**
 * Convert words to estimated pages
 */
export function wordsToPages(words: number): number {
  return Math.round(words / WORDS_PER_PAGE);
}
