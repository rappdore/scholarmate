// TZ must be applied before date-fns / the module under test load (see helper)
import './setNewYorkTimezone';

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import type { ReadingSession } from '../../src/types/statistics';
import { calculateStreak } from '../../src/utils/statisticsCalculations';

function createSession(
  sessionStart: string,
  overrides: Partial<ReadingSession> = {}
): ReadingSession {
  return {
    session_id: 'session-1',
    session_start: sessionStart,
    last_updated: sessionStart,
    pages_read: 5,
    average_time_per_page: 30,
    ...overrides,
  };
}

describe('calculateStreak', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('runs in the America/New_York timezone (TZ helper applied)', () => {
    // EDT is UTC-4 => offset of 240 minutes in June
    expect(new Date('2026-06-01T12:00:00Z').getTimezoneOffset()).toBe(240);
  });

  it('returns zeros for empty sessions', () => {
    expect(calculateStreak([])).toEqual({
      current_streak: 0,
      longest_streak: 0,
      reading_days: [],
    });
  });

  it('counts consecutive days ending today', () => {
    vi.setSystemTime(new Date('2026-06-10T12:00:00-04:00'));

    const sessions = [
      createSession('2026-06-10T09:00:00-04:00'),
      createSession('2026-06-09T09:00:00-04:00'),
      createSession('2026-06-08T09:00:00-04:00'),
    ];

    expect(calculateStreak(sessions).current_streak).toBe(3);
  });

  it('returns 0 current streak when last activity is older than yesterday', () => {
    vi.setSystemTime(new Date('2026-06-10T12:00:00-04:00'));

    const sessions = [createSession('2026-06-07T09:00:00-04:00')];

    const result = calculateStreak(sessions);
    expect(result.current_streak).toBe(0);
    expect(result.longest_streak).toBe(1);
  });

  it('keeps the streak alive across the spring-forward DST transition', () => {
    // US DST 2026 starts Sunday 2026-03-08 at 2am (America/New_York).
    // Just after midnight on March 9 (EDT), "now - 24h" lands on March 7
    // 23:30 EST, so the naive calculation skips March 8 entirely.
    vi.setSystemTime(new Date('2026-03-09T00:30:00-04:00'));

    const sessions = [
      createSession('2026-03-08T10:00:00-04:00'), // yesterday (EDT)
      createSession('2026-03-07T10:00:00-05:00'), // two days ago (EST)
    ];

    expect(calculateStreak(sessions).current_streak).toBe(2);
  });

  it('recognizes yesterday-only activity on a DST-transition boundary', () => {
    vi.setSystemTime(new Date('2026-03-09T00:30:00-04:00'));

    const sessions = [createSession('2026-03-08T10:00:00-04:00')];

    expect(calculateStreak(sessions).current_streak).toBe(1);
  });
});
