/**
 * Type definitions for reading statistics
 */

export interface ReadingSession {
  session_id: string;
  session_start: string; // ISO timestamp
  last_updated: string; // ISO timestamp
  pages_read: number;
  average_time_per_page: number;
}

export interface AggregateStats {
  total_sessions: number;
  total_pages_read: number;
  total_time_spent_seconds: number;
  overall_avg_time_per_page: number;
  fastest_page_time: number;
  slowest_page_time: number;
  first_read_date: string;
  last_read_date: string;
  longest_session_pages: number;
  shortest_session_pages: number;
  avg_pages_per_session: number;
}

export interface StreakData {
  current_streak: number;
  longest_streak: number;
  reading_days: string[];
}

export interface CalendarDay {
  date: string;
  sessions: number;
  pages_read: number;
  total_time_seconds: number;
}

export interface SessionsResponse {
  pdf_id: number; // Primary identifier for the PDF document
  pdf_filename: string; // Keep for backward compatibility and display
  total_sessions: number;
  sessions: ReadingSession[];
}
