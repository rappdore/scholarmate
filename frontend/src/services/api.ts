import axios from 'axios';
import type { PDF, PDFInfo } from '../types/pdf';
import type {
  Highlight,
  HighlightCoordinates,
  HighlightRequest,
  HighlightResponse,
  UpdateColorRequest,
  HighlightColor,
} from '../types/highlights';

const API_BASE_URL = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Extensive logging interceptor
api.interceptors.request.use(
  config => {
    console.log('🚀 [API REQUEST]', {
      method: config.method?.toUpperCase(),
      url: config.url,
      fullURL: `${config.baseURL}${config.url}`,
      headers: config.headers,
      data: config.data,
      timestamp: new Date().toISOString(),
    });
    return config;
  },
  error => {
    console.error('❌ [API REQUEST ERROR]', {
      message: error.message,
      error: error,
      timestamp: new Date().toISOString(),
    });
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  response => {
    console.log('✅ [API RESPONSE]', {
      status: response.status,
      statusText: response.statusText,
      url: response.config.url,
      fullURL: `${response.config.baseURL}${response.config.url}`,
      data: response.data,
      headers: response.headers,
      timestamp: new Date().toISOString(),
    });
    return response;
  },
  error => {
    console.error('❌ [API RESPONSE ERROR]', {
      message: error.message,
      url: error.config?.url,
      fullURL: error.config
        ? `${error.config.baseURL}${error.config.url}`
        : 'unknown',
      status: error.response?.status,
      statusText: error.response?.statusText,
      responseData: error.response?.data,
      code: error.code,
      isNetworkError: error.message === 'Network Error',
      isTimeout: error.code === 'ECONNABORTED',
      timestamp: new Date().toISOString(),
    });
    return Promise.reject(error);
  }
);

export const pdfService = {
  listPDFs: async (status?: string): Promise<PDF[]> => {
    const url = status ? `/pdf/list?status=${status}` : '/pdf/list';
    const response = await api.get(url);
    return response.data;
  },

  getPDFInfo: async (filename: string): Promise<PDFInfo> => {
    const response = await api.get(`/pdf/${filename}/info`);
    return response.data;
  },

  getPageText: async (filename: string, pageNum: number): Promise<string> => {
    const response = await api.get(`/pdf/${filename}/text/${pageNum}`);
    return response.data;
  },

  saveReadingProgress: async (
    filename: string,
    lastPage: number,
    totalPages: number
  ): Promise<any> => {
    const response = await api.put(`/pdf/${filename}/progress`, {
      last_page: lastPage,
      total_pages: totalPages,
    });
    return response.data;
  },

  getReadingProgress: async (
    filename: string
  ): Promise<{
    pdf_filename: string;
    last_page: number;
    total_pages: number | null;
    last_updated: string | null;
    status: string;
    status_updated_at: string | null;
    manually_set: boolean;
  }> => {
    const response = await api.get(`/pdf/${filename}/progress`);
    return response.data;
  },

  getAllReadingProgress: async (): Promise<{
    progress: Record<string, any>;
  }> => {
    const response = await api.get('/pdf/progress/all');
    return response.data;
  },

  // New status management methods
  updateBookStatus: async (
    filename: string,
    status: string,
    manually_set: boolean = true
  ): Promise<any> => {
    const response = await api.put(`/pdf/${filename}/status`, {
      status,
      manually_set,
    });
    return response.data;
  },

  deleteBook: async (filename: string): Promise<any> => {
    const response = await api.delete(`/pdf/${filename}`);
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

  getThumbnailUrl: (filename: string): string => {
    return `http://localhost:8000/pdf/${encodeURIComponent(filename)}/thumbnail`;
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
};

export const notesService = {
  saveChatNote: async (
    pdfFilename: string,
    pageNumber: number,
    title: string,
    chatContent: string
  ): Promise<any> => {
    const response = await api.post('/notes/chat', {
      pdf_filename: pdfFilename,
      page_number: pageNumber,
      title: title,
      chat_content: chatContent,
    });
    return response.data;
  },

  getChatNotesForPdf: async (
    pdfFilename: string,
    pageNumber?: number
  ): Promise<any[]> => {
    const params = pageNumber ? `?page_number=${pageNumber}` : '';
    const response = await api.get(`/notes/chat/${pdfFilename}${params}`);
    return response.data;
  },

  getChatNoteById: async (noteId: number): Promise<any> => {
    const response = await api.get(`/notes/chat/id/${noteId}`);
    return response.data;
  },

  deleteChatNote: async (noteId: number): Promise<any> => {
    const response = await api.delete(`/notes/chat/${noteId}`);
    return response.data;
  },
};

export const aiService = {
  checkHealth: async () => {
    const response = await api.get('/ai/health');
    return response.data;
  },

  analyzePage: async (filename: string, pageNum: number, context?: string) => {
    const response = await api.post('/ai/analyze', {
      filename,
      page_num: pageNum,
      context: context || '',
    });
    return response.data;
  },

  analyzeEpubSection: async (
    filename: string,
    navId: string,
    context?: string
  ) => {
    const response = await api.post('/ai/analyze-epub-section', {
      filename,
      nav_id: navId,
      context: context || '',
    });
    return response.data;
  },

  streamAnalyzePage: async function* (
    filename: string,
    pageNum: number,
    context?: string
  ): AsyncGenerator<
    {
      content?: string;
      done?: boolean;
      text_extracted?: boolean;
      error?: string;
    },
    void,
    unknown
  > {
    const url = `${API_BASE_URL}/ai/analyze/stream`;
    console.log('🚀 [FETCH REQUEST - STREAM ANALYZE]', {
      url,
      method: 'POST',
      filename,
      pageNum,
      context,
      timestamp: new Date().toISOString(),
    });

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename,
          page_num: pageNum,
          context: context || '',
        }),
      });

      console.log('✅ [FETCH RESPONSE - STREAM ANALYZE]', {
        url,
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        headers: Object.fromEntries(response.headers.entries()),
        timestamp: new Date().toISOString(),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ [FETCH ERROR - STREAM ANALYZE]', {
          url,
          status: response.status,
          statusText: response.statusText,
          errorText,
          timestamp: new Date().toISOString(),
        });
        throw new Error(
          `HTTP error! status: ${response.status}, body: ${errorText}`
        );
      }

      const reader = response.body?.getReader();
      if (!reader) {
        const error = 'Failed to get response reader';
        console.error('❌ [STREAM ANALYZE ERROR]', {
          error,
          timestamp: new Date().toISOString(),
        });
        throw new Error(error);
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let chunkCount = 0;

      try {
        while (true) {
          const { done, value } = await reader.read();
          chunkCount++;

          if (done) {
            console.log('✅ [STREAM ANALYZE COMPLETE]', {
              totalChunks: chunkCount,
              timestamp: new Date().toISOString(),
            });
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                console.log('📦 [STREAM CHUNK - ANALYZE]', {
                  chunkNum: chunkCount,
                  data,
                });
                yield data;
                if (data.done) {
                  return;
                }
              } catch (e) {
                console.error('❌ [SSE PARSE ERROR]', {
                  line,
                  error: e,
                  timestamp: new Date().toISOString(),
                });
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      console.error('❌ [STREAM ANALYZE FAILED]', {
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
        timestamp: new Date().toISOString(),
      });
      throw new Error(
        `Analysis failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  streamAnalyzeEpubSection: async function* (
    filename: string,
    navId: string,
    context?: string
  ): AsyncGenerator<
    {
      content?: string;
      done?: boolean;
      text_extracted?: boolean;
      error?: string;
    },
    void,
    unknown
  > {
    try {
      const response = await fetch(
        'http://localhost:8000/ai/analyze-epub-section/stream',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            filename,
            nav_id: navId,
            context: context || '',
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Failed to get response reader');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                yield data;
                if (data.done) {
                  return;
                }
              } catch (e) {
                console.error('Error parsing SSE data:', e);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      throw new Error(
        `Analysis failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  getPageContext: async (
    filename: string,
    pageNum: number,
    contextPages: number = 1
  ) => {
    const response = await api.get(
      `/ai/${filename}/context/${pageNum}?context_pages=${contextPages}`
    );
    return response.data;
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
    filename: string,
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
    const url = `${API_BASE_URL}/ai/chat`;
    console.log('🚀 [FETCH REQUEST - STREAM CHAT]', {
      url,
      method: 'POST',
      message,
      filename,
      pageNum,
      isNewChat,
      hasAbortSignal: !!abortSignal,
      historyLength: chatHistory?.length || 0,
      timestamp: new Date().toISOString(),
    });

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          filename,
          page_num: pageNum,
          chat_history: chatHistory,
          is_new_chat: isNewChat || false,
        }),
        signal: abortSignal,
      });

      console.log('✅ [FETCH RESPONSE - STREAM CHAT]', {
        url,
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        headers: Object.fromEntries(response.headers.entries()),
        timestamp: new Date().toISOString(),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ [FETCH ERROR - STREAM CHAT]', {
          url,
          status: response.status,
          statusText: response.statusText,
          errorText,
          timestamp: new Date().toISOString(),
        });
        throw new Error(
          `HTTP error! status: ${response.status}, body: ${errorText}`
        );
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Failed to get response reader');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.error) {
                  throw new Error(data.error);
                }

                // Yield the entire data object so the consumer can handle request_id, done, cancelled, etc.
                yield data;

                if (data.done || data.cancelled) {
                  return;
                }
              } catch (e) {
                console.error('Error parsing SSE data:', e);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      throw new Error(
        `Chat failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  streamChatEpub: async function* (
    message: string,
    filename: string,
    navId: string,
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
      const response = await fetch('http://localhost:8000/ai/chat/epub', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          filename,
          nav_id: navId,
          chat_history: chatHistory,
          is_new_chat: isNewChat || false,
        }),
        signal: abortSignal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Failed to get response reader');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.error) {
                  throw new Error(data.error);
                }

                // Yield the entire data object so the consumer can handle request_id, done, cancelled, etc.
                yield data;

                if (data.done || data.cancelled) {
                  return;
                }
              } catch (e) {
                console.error('Error parsing SSE data:', e);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      throw new Error(
        `EPUB chat failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },
};

// Real Highlight Service - Connects to backend API
export const highlightService = {
  // Helper function to convert backend response to frontend format
  _convertBackendHighlight: (backendHighlight: any): Highlight => {
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
      pdfFilename: backendHighlight.pdf_filename,
      pageNumber: backendHighlight.page_number,
      selectedText: backendHighlight.selected_text,
      startOffset: backendHighlight.start_offset,
      endOffset: backendHighlight.end_offset,
      color: backendHighlight.color as HighlightColor,
      coordinates,
      createdAt: new Date(backendHighlight.created_at),
      updatedAt: new Date(backendHighlight.updated_at),
    };
  },

  createHighlight: async (
    highlightData: HighlightRequest
  ): Promise<Highlight> => {
    const url = `${API_BASE_URL}/highlights/`;
    console.log('🚀 [FETCH REQUEST - CREATE HIGHLIGHT]', {
      url,
      method: 'POST',
      highlightData,
      timestamp: new Date().toISOString(),
    });

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          pdf_filename: highlightData.pdfFilename,
          page_number: highlightData.pageNumber,
          selected_text: highlightData.selectedText,
          start_offset: highlightData.startOffset,
          end_offset: highlightData.endOffset,
          color: highlightData.color,
          coordinates: highlightData.coordinates,
        }),
      });

      console.log('✅ [FETCH RESPONSE - CREATE HIGHLIGHT]', {
        url,
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        timestamp: new Date().toISOString(),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ [CREATE HIGHLIGHT ERROR]', {
          url,
          status: response.status,
          errorText,
          timestamp: new Date().toISOString(),
        });
        throw new Error(
          `HTTP error! status: ${response.status}, body: ${errorText}`
        );
      }

      const backendHighlight = await response.json();
      const highlight =
        highlightService._convertBackendHighlight(backendHighlight);

      console.log('✅ [HIGHLIGHT CREATED]', highlight);
      return highlight;
    } catch (error) {
      console.error('❌ [CREATE HIGHLIGHT FAILED]', {
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
        timestamp: new Date().toISOString(),
      });
      throw new Error(
        `Failed to create highlight: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  getHighlightsForPdf: async (
    filename: string,
    pageNumber?: number
  ): Promise<Highlight[]> => {
    const url =
      pageNumber !== undefined
        ? `${API_BASE_URL}/highlights/${encodeURIComponent(filename)}/page/${pageNumber}`
        : `${API_BASE_URL}/highlights/${encodeURIComponent(filename)}`;

    console.log('🚀 [FETCH REQUEST - GET HIGHLIGHTS]', {
      url,
      filename,
      pageNumber,
      timestamp: new Date().toISOString(),
    });

    try {
      const response = await fetch(url);

      console.log('✅ [FETCH RESPONSE - GET HIGHLIGHTS]', {
        url,
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        timestamp: new Date().toISOString(),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ [GET HIGHLIGHTS ERROR]', {
          url,
          status: response.status,
          errorText,
          timestamp: new Date().toISOString(),
        });
        throw new Error(
          `HTTP error! status: ${response.status}, body: ${errorText}`
        );
      }

      const backendHighlights = await response.json();
      const highlights = backendHighlights.map(
        highlightService._convertBackendHighlight
      );

      console.log('✅ [HIGHLIGHTS RETRIEVED]', {
        count: highlights.length,
        filename,
        pageNumber,
        timestamp: new Date().toISOString(),
      });
      return highlights;
    } catch (error) {
      console.error('❌ [GET HIGHLIGHTS FAILED]', {
        filename,
        pageNumber,
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
        timestamp: new Date().toISOString(),
      });
      throw new Error(
        `Failed to retrieve highlights: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  getHighlightById: async (highlightId: string): Promise<Highlight | null> => {
    try {
      const response = await fetch(
        `http://localhost:8000/highlights/id/${highlightId}`
      );

      if (response.status === 404) {
        console.log('Highlight not found:', highlightId);
        return null;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const backendHighlight = await response.json();
      const highlight =
        highlightService._convertBackendHighlight(backendHighlight);

      console.log('Retrieved highlight by ID:', highlight);
      return highlight;
    } catch (error) {
      console.error('Error retrieving highlight by ID:', error);
      throw new Error(
        `Failed to retrieve highlight: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  deleteHighlight: async (highlightId: string): Promise<boolean> => {
    try {
      const response = await fetch(
        `http://localhost:8000/highlights/${highlightId}`,
        {
          method: 'DELETE',
        }
      );

      if (response.status === 404) {
        console.log('Highlight not found for deletion:', highlightId);
        return false;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      console.log('Deleted highlight:', highlightId);
      return true;
    } catch (error) {
      console.error('Error deleting highlight:', error);
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
      const response = await fetch(
        `http://localhost:8000/highlights/${highlightId}/color`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            color: color,
          }),
        }
      );

      if (response.status === 404) {
        console.log('Highlight not found for color update:', highlightId);
        return false;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      console.log('Updated highlight color:', highlightId, color);
      return true;
    } catch (error) {
      console.error('Error updating highlight color:', error);
      throw new Error(
        `Failed to update highlight color: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  // Get highlight statistics for all PDFs
  getHighlightStats: async (): Promise<Record<string, any>> => {
    try {
      const response = await fetch(
        'http://localhost:8000/highlights/stats/count'
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const stats = await response.json();
      console.log('Retrieved highlight statistics:', stats);
      return stats;
    } catch (error) {
      console.error('Error retrieving highlight statistics:', error);
      throw new Error(
        `Failed to retrieve highlight statistics: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },
};

// EPUB-specific notes service (completely separate from PDF notesService)
export const epubNotesService = {
  saveChatNote: async (
    epubFilename: string,
    navId: string,
    chapterId: string,
    chapterTitle: string,
    title: string,
    chatContent: string,
    contextSections?: string[],
    scrollPosition?: number
  ): Promise<any> => {
    const response = await api.post('/epub-notes/chat', {
      epub_filename: epubFilename,
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
    epubFilename: string,
    navId?: string,
    chapterId?: string
  ): Promise<any[]> => {
    const params = new URLSearchParams();
    if (navId) params.append('nav_id', navId);
    if (chapterId) params.append('chapter_id', chapterId);

    const response = await api.get(
      `/epub-notes/chat/${epubFilename}${params.toString() ? '?' + params.toString() : ''}`
    );
    return response.data;
  },

  getChatNotesByChapter: async (
    epubFilename: string
  ): Promise<Record<string, any[]>> => {
    const response = await api.get(
      `/epub-notes/chat/${epubFilename}/by-chapter`
    );
    return response.data;
  },

  getChatNoteById: async (noteId: number): Promise<any> => {
    const response = await api.get(`/epub-notes/chat/id/${noteId}`);
    return response.data;
  },

  deleteChatNote: async (noteId: number): Promise<any> => {
    const response = await api.delete(`/epub-notes/chat/${noteId}`);
    return response.data;
  },

  getNotesStatistics: async (): Promise<Record<string, any>> => {
    const response = await api.get('/epub-notes/stats');
    return response.data;
  },
};

export default api;
