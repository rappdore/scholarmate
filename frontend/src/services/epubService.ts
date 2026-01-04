import axios from 'axios';
import type { EPUBDocument, EPUBDocumentInfo } from '../types/document';
import type { EPUBHighlight } from '../utils/epubHighlights';
import { API_BASE_URL } from './config';

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

const api = axios.create({
  baseURL: API_BASE_URL,
});

// EPUB Progress interfaces
export interface EPUBProgressRequest {
  current_nav_id: string;
  chapter_id?: string;
  chapter_title?: string;
  scroll_position?: number;
  total_sections?: number;
  progress_percentage?: number;
  nav_metadata?: Record<string, any>;
}

export interface EPUBProgress {
  id: number;
  epub_filename: string;
  current_nav_id: string;
  chapter_id?: string;
  chapter_title?: string;
  scroll_position: number;
  total_sections?: number;
  progress_percentage: number;
  last_updated: string | null;
  status: string;
  status_updated_at: string | null;
  manually_set: boolean;
  nav_metadata?: Record<string, any>;
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

  getEPUBFile: async (epubId: number): Promise<any> => {
    // This will return 404 for now as per the plan
    const response = await api.get(`/epub/${epubId}/file`);
    return response.data;
  },

  getThumbnailUrl: (epubId: number): string => {
    return `${API_BASE_URL}/epub/${epubId}/thumbnail`;
  },

  getNavigation: async (epubId: number): Promise<EPUBNavigationResponse> => {
    const response = await api.get(`/epub/${epubId}/navigation`);
    return response.data;
  },

  getContent: async (epubId: number, navId: string): Promise<any> => {
    const response = await api.get(
      `/epub/${epubId}/content/${encodeURIComponent(navId)}`
    );
    return response.data;
  },

  getStyles: async (epubId: number): Promise<any> => {
    const response = await api.get(`/epub/${epubId}/styles`);
    return response.data;
  },

  // ========================================
  // EPUB PROGRESS TRACKING METHODS
  // ========================================

  saveEPUBProgress: async (
    epubId: number,
    progressData: EPUBProgressRequest
  ): Promise<any> => {
    const response = await api.put(`/epub/${epubId}/progress`, progressData);
    return response.data;
  },

  getEPUBProgress: async (epubId: number): Promise<EPUBProgress> => {
    const response = await api.get(`/epub/${epubId}/progress`);
    return response.data;
  },

  getAllEPUBProgress: async (): Promise<{
    epub_progress: Record<string, any>;
  }> => {
    const response = await api.get('/epub/progress/all');
    return response.data;
  },

  updateEPUBBookStatus: async (
    epubId: number,
    status: string,
    manually_set: boolean = true
  ): Promise<any> => {
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

  deleteEPUBBook: async (epubId: number): Promise<any> => {
    const response = await api.delete(`/epub/${epubId}`);
    return response.data;
  },

  getEPUBChapterProgress: async (
    epubId: number,
    chapterId: string
  ): Promise<any> => {
    const response = await api.get(
      `/epub/${epubId}/chapter-progress/${chapterId}`
    );
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
      color: string;
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
    color: string
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
