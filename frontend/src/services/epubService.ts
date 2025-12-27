import axios from 'axios';
import type { EPUBDocument, EPUBDocumentInfo } from '../types/document';
import type { EPUBHighlight } from '../utils/epubHighlights';

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
  baseURL: 'http://localhost:8000',
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
    return `http://localhost:8000/epub/${epubId}/thumbnail`;
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
    highlightData: Omit<EPUBHighlight, 'id' | 'created_at' | 'epub_id'>
  ): Promise<EPUBHighlight> => {
    const response = await api.post(`/epub-highlights/create`, {
      ...highlightData,
      epub_id: epubId,
    });
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
};
