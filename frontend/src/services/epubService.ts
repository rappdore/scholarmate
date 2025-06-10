import axios from 'axios';
import type { EPUBDocument, EPUBDocumentInfo } from '../types/document';
import type { EPUBHighlight } from '../utils/epubHighlights';

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

  getEPUBInfo: async (filename: string): Promise<EPUBDocumentInfo> => {
    const response = await api.get(`/epub/${filename}/info`);
    return response.data;
  },

  getEPUBFile: async (filename: string): Promise<any> => {
    // This will return 404 for now as per the plan
    const response = await api.get(`/epub/${filename}/file`);
    return response.data;
  },

  getThumbnailUrl: (filename: string): string => {
    return `http://localhost:8000/epub/${encodeURIComponent(filename)}/thumbnail`;
  },

  getNavigation: async (filename: string): Promise<any> => {
    const response = await api.get(
      `/epub/${encodeURIComponent(filename)}/navigation`
    );
    return response.data;
  },

  getContent: async (filename: string, navId: string): Promise<any> => {
    const response = await api.get(
      `/epub/${encodeURIComponent(filename)}/content/${encodeURIComponent(navId)}`
    );
    return response.data;
  },

  getStyles: async (filename: string): Promise<any> => {
    const response = await api.get(
      `/epub/${encodeURIComponent(filename)}/styles`
    );
    return response.data;
  },

  // ========================================
  // EPUB PROGRESS TRACKING METHODS
  // ========================================

  saveEPUBProgress: async (
    filename: string,
    progressData: EPUBProgressRequest
  ): Promise<any> => {
    const response = await api.put(
      `/epub/${encodeURIComponent(filename)}/progress`,
      progressData
    );
    return response.data;
  },

  getEPUBProgress: async (filename: string): Promise<EPUBProgress> => {
    const response = await api.get(
      `/epub/${encodeURIComponent(filename)}/progress`
    );
    return response.data;
  },

  getAllEPUBProgress: async (): Promise<{
    epub_progress: Record<string, any>;
  }> => {
    const response = await api.get('/epub/progress/all');
    return response.data;
  },

  updateEPUBBookStatus: async (
    filename: string,
    status: string,
    manually_set: boolean = true
  ): Promise<any> => {
    const response = await api.put(
      `/epub/${encodeURIComponent(filename)}/status`,
      {
        status,
        manually_set,
      }
    );
    return response.data;
  },

  getEPUBStatusCounts: async (): Promise<Record<string, number>> => {
    const response = await api.get('/epub/status/counts');
    return response.data;
  },

  deleteEPUBBook: async (filename: string): Promise<any> => {
    const response = await api.delete(`/epub/${encodeURIComponent(filename)}`);
    return response.data;
  },

  getEPUBChapterProgress: async (
    filename: string,
    chapterId: string
  ): Promise<any> => {
    const response = await api.get(
      `/epub/${encodeURIComponent(filename)}/chapter-progress/${chapterId}`
    );
    return response.data;
  },

  // ========================================
  // EPUB HIGHLIGHTS METHODS
  // ========================================

  createEPUBHighlight: async (
    filename: string,
    highlightData: Omit<EPUBHighlight, 'id' | 'created_at' | 'document_id'>
  ): Promise<EPUBHighlight> => {
    const response = await api.post(`/epub-highlights/create`, {
      ...highlightData,
      document_id: filename,
    });
    return response.data;
  },

  getSectionHighlights: async (
    filename: string,
    navId: string
  ): Promise<EPUBHighlight[]> => {
    const response = await api.get(
      `/epub-highlights/${encodeURIComponent(filename)}/section/${encodeURIComponent(navId)}`
    );
    return response.data;
  },

  getChapterHighlights: async (
    filename: string,
    chapterId: string
  ): Promise<EPUBHighlight[]> => {
    const response = await api.get(
      `/epub-highlights/${encodeURIComponent(filename)}/chapter/${encodeURIComponent(chapterId)}`
    );
    return response.data;
  },

  deleteEPUBHighlight: async (highlightId: string): Promise<void> => {
    await api.delete(`/epub-highlights/${highlightId}`);
  },
};
