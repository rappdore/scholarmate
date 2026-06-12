/**
 * Type definitions for EPUB reading statistics
 */

import type { StreakData } from './statistics';

export interface EpubReadingSession {
  session_id: string;
  session_start: string; // ISO timestamp
  last_updated: string; // ISO timestamp
  words_read: number;
  time_spent_seconds: number;
}

export interface EpubAggregateStats {
  total_sessions: number;
  total_words_read: number;
  total_time_spent_seconds: number;
  avg_words_per_minute: number;
  avg_words_per_session: number;
  fastest_reading_speed: number; // words per minute
  slowest_reading_speed: number; // words per minute
  first_read_date: string | null;
  last_read_date: string | null;
  longest_session_words: number;
  estimated_pages_read: number; // based on 250 words/page
}

// Streaks are unit-agnostic; the EPUB shape is identical to the PDF one.
export type EpubStreakData = StreakData;

export interface EpubCalendarDay {
  date: string;
  sessions: number;
  words_read: number;
  total_time_seconds: number;
}

export interface EpubSessionsResponse {
  epub_id: number;
  total_sessions: number;
  sessions: EpubReadingSession[];
}

export interface NavSection {
  id: string;
  title: string;
  href: string;
  word_count: number;
  level?: number;
  parent_id?: string | null;
  order?: number;
}
