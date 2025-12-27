// Book status type for library management
export type BookStatus = 'new' | 'reading' | 'finished';

export interface ReadingProgress {
  last_page: number;
  total_pages: number;
  progress_percentage: number;
  last_updated: string;
  // New status management fields
  status: BookStatus;
  status_updated_at: string;
  manually_set: boolean;
}

export interface NotesInfo {
  notes_count: number;
  latest_note_date: string;
  latest_note_title: string;
}

export interface HighlightsInfo {
  highlights_count: number;
}

export interface PDF {
  id: number; // Primary identifier (pdf_id from backend)
  pdf_id: number; // Alias for id (explicit for PDF context)
  filename: string; // Keep for display purposes
  title: string;
  author: string;
  num_pages: number;
  file_size: number;
  modified_date: string;
  created_date: string;
  reading_progress?: ReadingProgress | null;
  notes_info?: NotesInfo | null;
  highlights_info?: HighlightsInfo | null;
  error?: string;
  // Status fields for smart categorization
  computed_status: BookStatus; // Based on progress
  manual_status?: BookStatus; // User override
}

export interface PDFInfo extends PDF {
  subject?: string;
  creator?: string;
  producer?: string;
  creation_date?: string;
  modification_date?: string;
}
