import axios from 'axios';
import type { PDF, PDFInfo } from '../types/pdf';
import type {
  Highlight,
  HighlightRequest,
  HighlightResponse,
  UpdateColorRequest,
  HighlightColor,
} from '../types/highlights';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

export const pdfService = {
  listPDFs: async (): Promise<PDF[]> => {
    const response = await api.get('/pdf/list');
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

// Stubbed Highlight Service - Returns mock data for UI development
export const highlightService = {
  // In-memory storage for development
  _highlights: new Map<string, Highlight[]>(),
  _nextId: 1,

  createHighlight: async (
    highlightData: HighlightRequest
  ): Promise<Highlight> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 200));

    const highlight: Highlight = {
      id: `temp-${highlightService._nextId++}`,
      pdfFilename: highlightData.pdfFilename,
      pageNumber: highlightData.pageNumber,
      selectedText: highlightData.selectedText,
      startOffset: highlightData.startOffset,
      endOffset: highlightData.endOffset,
      color: highlightData.color,
      coordinates: highlightData.coordinates,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    const key = `${highlightData.pdfFilename}-${highlightData.pageNumber}`;
    const existing = highlightService._highlights.get(key) || [];
    existing.push(highlight);
    highlightService._highlights.set(key, existing);

    console.log('Created highlight (stubbed):', highlight);
    return highlight;
  },

  getHighlightsForPdf: async (
    filename: string,
    pageNumber?: number
  ): Promise<Highlight[]> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 100));

    if (pageNumber !== undefined) {
      const key = `${filename}-${pageNumber}`;
      const highlights = highlightService._highlights.get(key) || [];
      console.log(
        `Retrieved ${highlights.length} highlights for ${filename} page ${pageNumber} (stubbed)`
      );
      return highlights;
    } else {
      // Return all highlights for the PDF
      const allHighlights: Highlight[] = [];
      for (const [key, highlights] of highlightService._highlights.entries()) {
        if (key.startsWith(filename + '-')) {
          allHighlights.push(...highlights);
        }
      }
      console.log(
        `Retrieved ${allHighlights.length} total highlights for ${filename} (stubbed)`
      );
      return allHighlights;
    }
  },

  getHighlightById: async (highlightId: string): Promise<Highlight | null> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 100));

    for (const highlights of highlightService._highlights.values()) {
      const found = highlights.find((h: Highlight) => h.id === highlightId);
      if (found) {
        console.log('Retrieved highlight by ID (stubbed):', found);
        return found;
      }
    }
    console.log('Highlight not found (stubbed):', highlightId);
    return null;
  },

  deleteHighlight: async (highlightId: string): Promise<boolean> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 150));

    for (const [key, highlights] of highlightService._highlights.entries()) {
      const index = highlights.findIndex(
        (h: Highlight) => h.id === highlightId
      );
      if (index !== -1) {
        highlights.splice(index, 1);
        highlightService._highlights.set(key, highlights);
        console.log('Deleted highlight (stubbed):', highlightId);
        return true;
      }
    }
    console.log('Highlight not found for deletion (stubbed):', highlightId);
    return false;
  },

  updateHighlightColor: async (
    highlightId: string,
    color: HighlightColor
  ): Promise<boolean> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 150));

    for (const highlights of highlightService._highlights.values()) {
      const highlight = highlights.find((h: Highlight) => h.id === highlightId);
      if (highlight) {
        highlight.color = color;
        highlight.updatedAt = new Date();
        console.log('Updated highlight color (stubbed):', highlightId, color);
        return true;
      }
    }
    console.log('Highlight not found for color update (stubbed):', highlightId);
    return false;
  },

  // Utility method to clear all highlights (for development)
  clearAllHighlights: () => {
    highlightService._highlights.clear();
    console.log('Cleared all highlights (stubbed)');
  },

  // Utility method to get all highlights (for debugging)
  getAllHighlights: () => {
    const all: Highlight[] = [];
    for (const highlights of highlightService._highlights.values()) {
      all.push(...highlights);
    }
    return all;
  },
};

export default api;
