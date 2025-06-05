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

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

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
    try {
      const response = await fetch('http://localhost:8000/ai/analyze/stream', {
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
  streamChat: async function* (
    message: string,
    filename: string,
    pageNum: number,
    chatHistory?: Array<{ role: string; content: string }>
  ): AsyncGenerator<string, void, unknown> {
    try {
      const response = await fetch('http://localhost:8000/ai/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          filename,
          page_num: pageNum,
          chat_history: chatHistory,
        }),
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
                if (data.done) {
                  return;
                }
                if (data.content) {
                  yield data.content;
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
    try {
      const response = await fetch('http://localhost:8000/highlights/', {
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

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const backendHighlight = await response.json();
      const highlight =
        highlightService._convertBackendHighlight(backendHighlight);

      console.log('Created highlight:', highlight);
      return highlight;
    } catch (error) {
      console.error('Error creating highlight:', error);
      throw new Error(
        `Failed to create highlight: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  getHighlightsForPdf: async (
    filename: string,
    pageNumber?: number
  ): Promise<Highlight[]> => {
    try {
      const url =
        pageNumber !== undefined
          ? `http://localhost:8000/highlights/${encodeURIComponent(filename)}/page/${pageNumber}`
          : `http://localhost:8000/highlights/${encodeURIComponent(filename)}`;

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const backendHighlights = await response.json();
      const highlights = backendHighlights.map(
        highlightService._convertBackendHighlight
      );

      console.log(
        `Retrieved ${highlights.length} highlights for ${filename}${pageNumber !== undefined ? ` page ${pageNumber}` : ''}`
      );
      return highlights;
    } catch (error) {
      console.error('Error retrieving highlights:', error);
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

export default api;
