import axios from 'axios';
import type { PDF, PDFInfo, ReadingProgress } from '../types/pdf';
import type {
  Highlight,
  HighlightCoordinates,
  HighlightRequest,
  HighlightColor,
} from '../types/highlights';
import { highlightColorHex, toHighlightColor } from '../types/highlights';
import { API_BASE_URL } from './config';
import { api, devLog, streamSSE } from './http';
import type { ReadingSession } from '../types/statistics';

// ============================================
// Wire-shape types (mirror backend responses)
// ============================================

export interface ProgressSaveResponse {
  success: boolean;
  message: string;
  pdf_id: number;
  last_page: number;
}

export interface StatusUpdateResponse {
  success: boolean;
  message: string;
  pdf_id: number;
  filename: string;
  status: string;
  manually_set: boolean;
}

export interface BookDeletionDetails {
  reading_progress: boolean;
  notes: boolean;
  highlights: boolean;
  pdf_file: boolean;
  thumbnail: boolean;
}

export interface BookDeletionResponse {
  success: boolean;
  message: string;
  pdf_id: number;
  filename: string;
  deletion_details: BookDeletionDetails;
}

export interface ReadingSessionsResponse {
  pdf_id: number;
  total_sessions: number;
  sessions: ReadingSession[];
}

export interface SessionUpdateResponse {
  message: string;
  session_id: string;
}

export interface ChatNote {
  id: number;
  pdf_filename: string;
  page_number: number;
  title: string;
  chat_content: string;
  created_at: string;
  updated_at: string;
}

export interface ChatNoteSaveResponse {
  success: boolean;
  message: string;
  note_id: number;
}

export interface ChatNoteDeleteResponse {
  success: boolean;
  message: string;
}

export interface EPUBChatNote {
  id: number;
  epub_filename: string;
  nav_id: string;
  chapter_id: string;
  chapter_title: string;
  title: string;
  chat_content: string;
  context_sections: string[] | null;
  scroll_position: number;
  created_at: string;
  updated_at: string;
}

export interface EPUBChatNoteSaveResponse {
  note_id: number;
  message: string;
  epub_id: number;
  epub_filename: string;
  nav_id: string;
  chapter_id: string;
}

export interface EPUBChatNoteDeleteResponse {
  success: boolean;
  message: string;
  note_id: number;
}

/** Per-document note statistics, keyed by filename. */
export interface NotesStats {
  notes_count: number;
  latest_note_date: string | null;
  latest_note_title: string | null;
}

/** Per-document highlight statistics, keyed by filename. */
export interface HighlightStats {
  highlights_count: number;
  latest_highlight_date: string | null;
  latest_highlight_text: string | null;
}

/** Snake_case highlight payload as returned by the backend API. */
export interface BackendHighlight {
  id: number;
  pdf_id: number;
  pdf_filename: string;
  page_number: number;
  selected_text: string;
  start_offset: number;
  end_offset: number;
  color: string;
  coordinates: string | HighlightCoordinates[];
  created_at: string;
  updated_at: string;
}

export const pdfService = {
  listPDFs: async (status?: string): Promise<PDF[]> => {
    const url = status ? `/pdf/list?status=${status}` : '/pdf/list';
    const response = await api.get(url);
    return response.data;
  },

  getPDFInfo: async (pdfId: number): Promise<PDFInfo> => {
    const response = await api.get(`/pdf/${pdfId}/info`);
    return response.data;
  },

  getPageText: async (pdfId: number, pageNum: number): Promise<string> => {
    const response = await api.get(`/pdf/${pdfId}/text/${pageNum}`);
    return response.data;
  },

  saveReadingProgress: async (
    pdfId: number,
    lastPage: number,
    totalPages: number
  ): Promise<ProgressSaveResponse> => {
    const response = await api.put(`/pdf/${pdfId}/progress`, {
      last_page: lastPage,
      total_pages: totalPages,
    });
    return response.data;
  },

  getReadingProgress: async (
    pdfId: number
  ): Promise<{
    pdf_id: number;
    pdf_filename: string;
    last_page: number;
    total_pages: number | null;
    last_updated: string | null;
    status: string;
    status_updated_at: string | null;
    manually_set: boolean;
  }> => {
    const response = await api.get(`/pdf/${pdfId}/progress`);
    return response.data;
  },

  getAllReadingProgress: async (): Promise<{
    progress: Record<string, ReadingProgress>;
  }> => {
    const response = await api.get('/pdf/progress/all');
    return response.data;
  },

  updateBookStatus: async (
    pdfId: number,
    status: string,
    manually_set: boolean = true
  ): Promise<StatusUpdateResponse> => {
    const response = await api.put(`/pdf/${pdfId}/status`, {
      status,
      manually_set,
    });
    return response.data;
  },

  deleteBook: async (pdfId: number): Promise<BookDeletionResponse> => {
    const response = await api.delete(`/pdf/${pdfId}`);
    return response.data;
  },

  getStatusCounts: async (): Promise<{
    all: number;
    new: number;
    reading: number;
    finished: number;
  }> => {
    const response = await api.get('/pdf/status/counts');
    return response.data;
  },

  getThumbnailUrl: (pdfId: number): string => {
    return `${API_BASE_URL}/pdf/${pdfId}/thumbnail`;
  },

  getFileUrl: (pdfId: number): string => {
    return `${API_BASE_URL}/pdf/${pdfId}/file`;
  },

  refreshPDFCache: async (): Promise<{
    success: boolean;
    cache_built_at: string;
    pdf_count: number;
    message: string;
  }> => {
    const response = await api.post('/pdf/refresh-cache');
    return response.data;
  },

  getReadingSessions: async (
    pdfId: number
  ): Promise<ReadingSessionsResponse> => {
    const response = await api.get(`/reading-statistics/sessions/pdf/${pdfId}`);
    return response.data;
  },

  updateReadingSession: async (
    sessionId: string,
    pdfId: number,
    pagesRead: number,
    averageTimePerPage: number
  ): Promise<SessionUpdateResponse> => {
    const response = await api.put('/reading-statistics/session/update', {
      session_id: sessionId,
      pdf_id: pdfId,
      pages_read: pagesRead,
      average_time_per_page: averageTimePerPage,
    });
    return response.data;
  },
};

export const notesService = {
  saveChatNote: async (
    pdfId: number,
    pageNumber: number,
    title: string,
    chatContent: string
  ): Promise<ChatNoteSaveResponse> => {
    const response = await api.post('/notes/chat', {
      pdf_id: pdfId,
      page_number: pageNumber,
      title: title,
      chat_content: chatContent,
    });
    return response.data;
  },

  getChatNotesForPdf: async (
    pdfId: number,
    pageNumber?: number
  ): Promise<ChatNote[]> => {
    const params = pageNumber ? `?page_number=${pageNumber}` : '';
    const response = await api.get(`/notes/chat/pdf/${pdfId}${params}`);
    return response.data;
  },

  getChatNoteById: async (noteId: number): Promise<ChatNote> => {
    const response = await api.get(`/notes/chat/id/${noteId}`);
    return response.data;
  },

  deleteChatNote: async (noteId: number): Promise<ChatNoteDeleteResponse> => {
    const response = await api.delete(`/notes/chat/${noteId}`);
    return response.data;
  },
};

export const aiService = {
  checkHealth: async () => {
    const response = await api.get('/ai/health');
    return response.data;
  },

  analyzePage: async (pdfId: number, pageNum: number, context?: string) => {
    const response = await api.post('/ai/analyze', {
      pdf_id: pdfId,
      page_num: pageNum,
      context: context || '',
    });
    return response.data;
  },

  analyzeEpubSection: async (
    epubId: number,
    navId: string,
    context?: string
  ) => {
    const response = await api.post('/ai/analyze-epub-section', {
      epub_id: epubId,
      nav_id: navId,
      context: context || '',
    });
    return response.data;
  },

  streamAnalyzePage: async function* (
    pdfId: number,
    pageNum: number,
    context?: string
  ): AsyncGenerator<
    {
      // Structured streaming fields (same as chat)
      type?: 'thinking' | 'response' | 'metadata';
      content?: string | null;
      metadata?: {
        thinking_started?: boolean;
        thinking_complete?: boolean;
      };
      // Control fields
      done?: boolean;
      text_extracted?: boolean;
      error?: string;
    },
    void,
    unknown
  > {
    try {
      yield* streamSSE('/ai/analyze/stream', {
        pdf_id: pdfId,
        page_num: pageNum,
        context: context || '',
      });
    } catch (error) {
      throw new Error(
        `Analysis failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  streamAnalyzeEpubSection: async function* (
    epubId: number,
    navId: string,
    scrollPosition: number,
    context?: string
  ): AsyncGenerator<
    {
      // Structured streaming fields (same as chat)
      type?: 'thinking' | 'response' | 'metadata';
      content?: string | null;
      metadata?: {
        thinking_started?: boolean;
        thinking_complete?: boolean;
      };
      // Control fields
      done?: boolean;
      text_extracted?: boolean;
      error?: string;
    },
    void,
    unknown
  > {
    try {
      yield* streamSSE('/ai/analyze-epub-section/stream', {
        epub_id: epubId,
        nav_id: navId,
        scroll_position: scrollPosition,
        context: context || '',
      });
    } catch (error) {
      throw new Error(
        `Analysis failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },
};

export const chatService = {
  stopChat: async (requestId: string): Promise<void> => {
    try {
      const response = await api.post(`/ai/chat/stop/${requestId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to stop chat:', error);
      throw error;
    }
  },

  stopEpubChat: async (requestId: string): Promise<void> => {
    try {
      const response = await api.post(`/ai/chat/epub/stop/${requestId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to stop EPUB chat:', error);
      throw error;
    }
  },

  streamChat: async function* (
    message: string,
    pdfId: number,
    pageNum: number,
    chatHistory?: Array<{ role: string; content: string }>,
    abortSignal?: AbortSignal,
    isNewChat?: boolean
  ): AsyncGenerator<
    {
      // Structured streaming fields
      type?: 'thinking' | 'response' | 'metadata';
      content?: string;
      metadata?: {
        thinking_started?: boolean;
        thinking_complete?: boolean;
      };
      // Legacy/control fields
      request_id?: string;
      done?: boolean;
      cancelled?: boolean;
      error?: string;
    },
    void,
    unknown
  > {
    try {
      yield* streamSSE(
        '/ai/chat',
        {
          message,
          pdf_id: pdfId,
          page_num: pageNum,
          chat_history: chatHistory,
          is_new_chat: isNewChat || false,
        },
        abortSignal
      );
    } catch (error) {
      throw new Error(
        `Chat failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  streamChatEpub: async function* (
    message: string,
    epubId: number,
    navId: string,
    scrollPosition: number,
    chatHistory?: Array<{ role: string; content: string }>,
    abortSignal?: AbortSignal,
    isNewChat?: boolean
  ): AsyncGenerator<
    {
      // Structured streaming fields
      type?: 'thinking' | 'response' | 'metadata';
      content?: string;
      metadata?: {
        thinking_started?: boolean;
        thinking_complete?: boolean;
      };
      // Legacy/control fields
      request_id?: string;
      done?: boolean;
      cancelled?: boolean;
      error?: string;
    },
    void,
    unknown
  > {
    try {
      yield* streamSSE(
        '/ai/chat/epub',
        {
          message,
          epub_id: epubId,
          nav_id: navId,
          scroll_position: scrollPosition,
          chat_history: chatHistory,
          is_new_chat: isNewChat || false,
        },
        abortSignal
      );
    } catch (error) {
      throw new Error(
        `EPUB chat failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },
};

/** True when the error is an axios error with the given HTTP status. */
const isStatus = (error: unknown, status: number): boolean =>
  axios.isAxiosError(error) && error.response?.status === status;

// Real Highlight Service - Connects to backend API
export const highlightService = {
  // Helper function to convert backend response to frontend format
  _convertBackendHighlight: (backendHighlight: BackendHighlight): Highlight => {
    let coordinates: HighlightCoordinates[] = [];

    // Parse coordinates from JSON string
    try {
      coordinates =
        typeof backendHighlight.coordinates === 'string'
          ? JSON.parse(backendHighlight.coordinates)
          : backendHighlight.coordinates;
    } catch (error) {
      console.error('Error parsing highlight coordinates:', error);
      coordinates = [];
    }

    return {
      id: backendHighlight.id.toString(), // Convert number to string for frontend
      pdf_id: backendHighlight.pdf_id,
      pdfFilename: backendHighlight.pdf_filename,
      pageNumber: backendHighlight.page_number,
      selectedText: backendHighlight.selected_text,
      startOffset: backendHighlight.start_offset,
      endOffset: backendHighlight.end_offset,
      // The PDF wire format stores hex values; normalize to canonical names
      color: toHighlightColor(backendHighlight.color),
      coordinates,
      createdAt: new Date(backendHighlight.created_at),
      updatedAt: new Date(backendHighlight.updated_at),
    };
  },

  createHighlight: async (
    highlightData: HighlightRequest
  ): Promise<Highlight> => {
    try {
      const response = await api.post('/highlights/', {
        pdf_id: highlightData.pdf_id,
        page_number: highlightData.pageNumber,
        selected_text: highlightData.selectedText,
        start_offset: highlightData.startOffset,
        end_offset: highlightData.endOffset,
        color: highlightColorHex(highlightData.color),
        coordinates: highlightData.coordinates,
      });
      const highlight = highlightService._convertBackendHighlight(
        response.data
      );
      devLog('✅ [HIGHLIGHT CREATED]', highlight);
      return highlight;
    } catch (error) {
      throw new Error(
        `Failed to create highlight: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  getHighlightsForPdf: async (
    pdfId: number,
    pageNumber?: number
  ): Promise<Highlight[]> => {
    const url =
      pageNumber !== undefined
        ? `/highlights/pdf/${pdfId}/page/${pageNumber}`
        : `/highlights/pdf/${pdfId}`;

    try {
      const response = await api.get(url);
      return response.data.map(highlightService._convertBackendHighlight);
    } catch (error) {
      throw new Error(
        `Failed to retrieve highlights: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  getHighlightById: async (highlightId: string): Promise<Highlight | null> => {
    try {
      const response = await api.get(`/highlights/id/${highlightId}`);
      return highlightService._convertBackendHighlight(response.data);
    } catch (error) {
      if (isStatus(error, 404)) {
        devLog('Highlight not found:', highlightId);
        return null;
      }
      throw new Error(
        `Failed to retrieve highlight: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  deleteHighlight: async (highlightId: string): Promise<boolean> => {
    try {
      await api.delete(`/highlights/${highlightId}`);
      devLog('Deleted highlight:', highlightId);
      return true;
    } catch (error) {
      if (isStatus(error, 404)) {
        devLog('Highlight not found for deletion:', highlightId);
        return false;
      }
      throw new Error(
        `Failed to delete highlight: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  updateHighlightColor: async (
    highlightId: string,
    color: HighlightColor
  ): Promise<boolean> => {
    try {
      await api.put(`/highlights/${highlightId}/color`, {
        color: highlightColorHex(color),
      });
      devLog('Updated highlight color:', highlightId, color);
      return true;
    } catch (error) {
      if (isStatus(error, 404)) {
        devLog('Highlight not found for color update:', highlightId);
        return false;
      }
      throw new Error(
        `Failed to update highlight color: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  // Get highlight statistics for all PDFs
  getHighlightStats: async (): Promise<Record<string, HighlightStats>> => {
    try {
      const response = await api.get('/highlights/stats/count');
      return response.data;
    } catch (error) {
      throw new Error(
        `Failed to retrieve highlight statistics: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },
};

// EPUB-specific notes service (completely separate from PDF notesService)
export const epubNotesService = {
  saveChatNote: async (
    epubId: number,
    navId: string,
    chapterId: string,
    chapterTitle: string,
    title: string,
    chatContent: string,
    contextSections?: string[],
    scrollPosition?: number
  ): Promise<EPUBChatNoteSaveResponse> => {
    const response = await api.post('/epub-notes/chat', {
      epub_id: epubId,
      nav_id: navId,
      chapter_id: chapterId,
      chapter_title: chapterTitle,
      title: title,
      chat_content: chatContent,
      context_sections: contextSections,
      scroll_position: scrollPosition || 0,
    });
    return response.data;
  },

  getChatNotesForEpub: async (
    epubId: number,
    navId?: string,
    chapterId?: string
  ): Promise<EPUBChatNote[]> => {
    const params = new URLSearchParams();
    if (navId) params.append('nav_id', navId);
    if (chapterId) params.append('chapter_id', chapterId);

    const response = await api.get(
      `/epub-notes/chat/${epubId}${params.toString() ? '?' + params.toString() : ''}`
    );
    return response.data;
  },

  getChatNotesByChapter: async (
    epubId: number
  ): Promise<Record<string, EPUBChatNote[]>> => {
    const response = await api.get(`/epub-notes/chat/${epubId}/by-chapter`);
    return response.data;
  },

  getChatNoteById: async (noteId: number): Promise<EPUBChatNote> => {
    const response = await api.get(`/epub-notes/chat/id/${noteId}`);
    return response.data;
  },

  deleteChatNote: async (
    noteId: number
  ): Promise<EPUBChatNoteDeleteResponse> => {
    const response = await api.delete(`/epub-notes/chat/${noteId}`);
    return response.data;
  },

  getNotesStatistics: async (): Promise<Record<string, NotesStats>> => {
    const response = await api.get('/epub-notes/stats');
    return response.data;
  },
};
