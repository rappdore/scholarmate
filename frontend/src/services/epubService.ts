import type { EPUBDocument, EPUBDocumentInfo } from '../types/document';
import type { EPUBHighlight } from '../utils/epubHighlights';
import type { HighlightColor } from '../types/highlights';
import { API_BASE_URL } from './config';
import { api } from './http';

export interface EPUBNavigationItem {
  id: string;
  title: string;
  href?: string;
  level: number;
  children: EPUBNavigationItem[];
}

export interface EPUBFlatNavigationItem {
  id: string;
  title: string;
  href?: string;
  level: number;
  parent_id?: string | null;
  order: number;
  spine_positions: number[];
  spine_item_ids?: string[];
  child_count: number;
}

export interface EPUBNavigationResponse {
  navigation: EPUBNavigationItem[];
  flat_navigation?: EPUBFlatNavigationItem[];
  spine_length: number;
  has_toc: boolean;
}

// Chapter content payload returned by GET /epub/{id}/content/{nav_id}
export interface EPUBContentResponse {
  nav_id: string;
  title: string;
  content: string;
  spine_position: number;
  total_sections: number;
  progress_percentage: number;
  previous_nav_id: string | null;
  next_nav_id: string | null;
}

// Sanitized stylesheet payload returned by GET /epub/{id}/styles
export interface EPUBStylesResponse {
  styles: Array<{
    id: string;
    name: string;
    content: string;
  }>;
  count: number;
}

export interface EPUBProgressSaveResponse {
  success: boolean;
  message: string;
  id: number;
  current_nav_id: string;
  progress_percentage: number;
}

export interface EPUBStatusUpdateResponse {
  success: boolean;
  message: string;
  id: number;
  status: string;
  manually_set: boolean;
}

export interface EPUBBookDeletionResponse {
  success: boolean;
  message: string;
  id: number;
  filename: string;
  deletion_details: Record<string, boolean>;
}

// EPUB Progress interfaces
export interface EPUBProgressRequest {
  current_nav_id: string;
  chapter_id?: string;
  chapter_title?: string;
  scroll_position?: number;
  total_sections?: number;
  epub_cfi?: string | null;
  progress_percentage?: number;
  nav_metadata?: Record<string, unknown>;
}

export interface EPUBProgress {
  id: number;
  epub_filename: string;
  current_nav_id: string;
  chapter_id?: string;
  chapter_title?: string;
  scroll_position: number;
  total_sections?: number;
  epub_cfi: string | null;
  progress_percentage: number;
  last_updated: string | null;
  status: string;
  status_updated_at: string | null;
  manually_set: boolean;
  nav_metadata?: Record<string, unknown>;
}

export const epubService = {
  listEPUBs: async (): Promise<EPUBDocument[]> => {
    const response = await api.get('/epub/list');
    return response.data;
  },

  getEPUBInfo: async (epubId: number): Promise<EPUBDocumentInfo> => {
    const response = await api.get(`/epub/${epubId}/info`);
    return response.data;
  },

  getThumbnailUrl: (epubId: number): string => {
    return `${API_BASE_URL}/epub/${epubId}/thumbnail`;
  },

  getNavigation: async (epubId: number): Promise<EPUBNavigationResponse> => {
    const response = await api.get(`/epub/${epubId}/navigation`);
    return response.data;
  },

  getContent: async (
    epubId: number,
    navId: string
  ): Promise<EPUBContentResponse> => {
    const response = await api.get(
      `/epub/${epubId}/content/${encodeURIComponent(navId)}`
    );
    return response.data;
  },

  getStyles: async (epubId: number): Promise<EPUBStylesResponse> => {
    const response = await api.get(`/epub/${epubId}/styles`);
    return response.data;
  },

  // ========================================
  // EPUB PROGRESS TRACKING METHODS
  // ========================================

  saveEPUBProgress: async (
    epubId: number,
    progressData: EPUBProgressRequest
  ): Promise<EPUBProgressSaveResponse> => {
    const response = await api.put(`/epub/${epubId}/progress`, progressData);
    return response.data;
  },

  getEPUBProgress: async (epubId: number): Promise<EPUBProgress> => {
    const response = await api.get(`/epub/${epubId}/progress`);
    return response.data;
  },

  getAllEPUBProgress: async (): Promise<{
    epub_progress: Record<string, EPUBProgress>;
  }> => {
    const response = await api.get('/epub/progress/all');
    return response.data;
  },

  updateEPUBBookStatus: async (
    epubId: number,
    status: string,
    manually_set: boolean = true
  ): Promise<EPUBStatusUpdateResponse> => {
    const response = await api.put(`/epub/${epubId}/status`, {
      status,
      manually_set,
    });
    return response.data;
  },

  getEPUBStatusCounts: async (): Promise<Record<string, number>> => {
    const response = await api.get('/epub/status/counts');
    return response.data;
  },

  deleteEPUBBook: async (epubId: number): Promise<EPUBBookDeletionResponse> => {
    const response = await api.delete(`/epub/${epubId}`);
    return response.data;
  },

  // ========================================
  // EPUB HIGHLIGHTS METHODS
  // ========================================

  createEPUBHighlight: async (
    epubId: number,
    highlightData: {
      nav_id: string;
      chapter_id?: string;
      start_xpath: string;
      start_offset: number;
      end_xpath: string;
      end_offset: number;
      highlight_text: string;
      color: HighlightColor;
    }
  ): Promise<EPUBHighlight> => {
    const response = await api.post(`/epub-highlights/create`, {
      epub_id: epubId,
      nav_id: highlightData.nav_id,
      chapter_id: highlightData.chapter_id,
      start_xpath: highlightData.start_xpath,
      start_offset: highlightData.start_offset,
      end_xpath: highlightData.end_xpath,
      end_offset: highlightData.end_offset,
      highlight_text: highlightData.highlight_text,
      color: highlightData.color,
    });
    return response.data;
  },

  getAllHighlights: async (epubId: number): Promise<EPUBHighlight[]> => {
    const response = await api.get(`/epub-highlights/${epubId}`);
    return response.data;
  },

  getSectionHighlights: async (
    epubId: number,
    navId: string
  ): Promise<EPUBHighlight[]> => {
    const response = await api.get(
      `/epub-highlights/${epubId}/section/${encodeURIComponent(navId)}`
    );
    return response.data;
  },

  getChapterHighlights: async (
    epubId: number,
    chapterId: string
  ): Promise<EPUBHighlight[]> => {
    const response = await api.get(
      `/epub-highlights/${epubId}/chapter/${encodeURIComponent(chapterId)}`
    );
    return response.data;
  },

  deleteEPUBHighlight: async (highlightId: string): Promise<void> => {
    await api.delete(`/epub-highlights/${highlightId}`);
  },

  updateEPUBHighlightColor: async (
    highlightId: number,
    color: HighlightColor
  ): Promise<void> => {
    await api.put(`/epub-highlights/${highlightId}/color`, { color });
  },

  // ========================================
  // EPUB CACHE MANAGEMENT METHODS
  // ========================================

  refreshEPUBCache: async (): Promise<{
    success: boolean;
    cache_built_at: string;
    epub_count: number;
    message: string;
  }> => {
    const response = await api.post('/epub/refresh-cache');
    return response.data;
  },

  // ========================================
  // EPUB READING STATISTICS METHODS
  // ========================================

  updateReadingSession: async (
    sessionId: string,
    epubId: number,
    wordsRead: number,
    timeSpentSeconds: number
  ): Promise<{ message: string; session_id: string }> => {
    const response = await api.put('/epub/reading-statistics/session/update', {
      session_id: sessionId,
      epub_id: epubId,
      words_read: wordsRead,
      time_spent_seconds: timeSpentSeconds,
    });
    return response.data;
  },

  getReadingSessions: async (
    epubId: number
  ): Promise<{
    epub_id: number;
    total_sessions: number;
    sessions: Array<{
      session_id: string;
      session_start: string;
      last_updated: string;
      words_read: number;
      time_spent_seconds: number;
    }>;
  }> => {
    const response = await api.get(
      `/epub/reading-statistics/sessions/${epubId}`
    );
    return response.data;
  },
};
