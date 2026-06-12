/**
 * Reading-streak calculation shared by the PDF and EPUB statistics modules.
 * Streaks only depend on *when* sessions happened, so the session unit
 * (pages vs words) is irrelevant here.
 */

import type { StreakData } from '../types/statistics';
import { parseISO, format, differenceInDays, subDays } from 'date-fns';

export function calculateReadingStreak(
  sessions: Array<{ session_start: string }>
): StreakData {
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
  // Use subDays (not now - 24h) so DST-transition days resolve correctly
  const yesterday = format(subDays(new Date(), 1), 'yyyy-MM-dd');

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
