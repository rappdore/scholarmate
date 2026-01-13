import axios from 'axios';
import { API_BASE_URL } from './config';
import type {
  Concept,
  ConceptCreate,
  ConceptsResponse,
  ConceptUpdate,
  Relationship,
  RelationshipCreate,
  RelationshipUpdate,
  GraphData,
  ExtractionRequest,
  ExtractionResponse,
  BookExtractionRequest,
  BookExtractionResponse,
  ExtractionProgress,
  KnowledgeStats,
  ExtractionStatusResponse,
  CancelExtractionResponse,
  SimilarConceptResult,
  RelationshipExtractionRequest,
  RelationshipExtractionResponse,
} from '../types/knowledge';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const knowledgeService = {
  extractSection: async (
    request: ExtractionRequest
  ): Promise<ExtractionResponse> => {
    const response = await api.post('/api/knowledge/extract', request);
    return response.data;
  },

  extractBook: async (
    request: BookExtractionRequest
  ): Promise<BookExtractionResponse> => {
    const response = await api.post('/api/knowledge/extract-book', request);
    return response.data;
  },

  extractRelationships: async (
    request: RelationshipExtractionRequest
  ): Promise<RelationshipExtractionResponse> => {
    const response = await api.post(
      '/api/knowledge/extract-relationships',
      request
    );
    return response.data;
  },

  getExtractionProgress: async (
    bookId: number,
    bookType: 'epub' | 'pdf'
  ): Promise<ExtractionProgress[]> => {
    const response = await api.get(
      `/api/knowledge/extraction-progress/${bookId}`,
      {
        params: { book_type: bookType },
      }
    );
    return response.data;
  },

  getConcepts: async (
    bookId: number,
    bookType: 'epub' | 'pdf',
    options?: {
      nav_id?: string;
      page_num?: number;
      importance_min?: number;
    }
  ): Promise<ConceptsResponse> => {
    const response = await api.get(`/api/knowledge/concepts/${bookId}`, {
      params: {
        book_type: bookType,
        ...options,
      },
    });
    return response.data;
  },

  getConceptById: async (conceptId: number): Promise<Concept> => {
    const response = await api.get(`/api/knowledge/concept/${conceptId}`);
    return response.data;
  },

  createConcept: async (concept: ConceptCreate): Promise<Concept> => {
    const response = await api.post('/api/knowledge/concept', concept);
    return response.data;
  },

  updateConcept: async (
    conceptId: number,
    updates: ConceptUpdate
  ): Promise<Concept> => {
    const response = await api.patch(
      `/api/knowledge/concept/${conceptId}`,
      updates
    );
    return response.data;
  },

  deleteConcept: async (
    conceptId: number
  ): Promise<{ success: boolean; deleted_id: number }> => {
    const response = await api.delete(`/api/knowledge/concept/${conceptId}`);
    return response.data;
  },

  mergeConcepts: async (
    sourceId: number,
    targetId: number
  ): Promise<{ success: boolean; merged_into: number }> => {
    const response = await api.post(
      `/api/knowledge/concept/${sourceId}/merge/${targetId}`
    );
    return response.data;
  },

  findSimilarConcepts: async (
    conceptId: number,
    options?: { n_results?: number; cross_book?: boolean }
  ): Promise<SimilarConceptResult[]> => {
    const response = await api.get(`/api/knowledge/similar/${conceptId}`, {
      params: options,
    });
    return response.data;
  },

  searchConcepts: async (
    query: string,
    options?: {
      book_id?: number;
      book_type?: 'epub' | 'pdf';
      limit?: number;
    }
  ): Promise<Concept[]> => {
    const response = await api.get('/api/knowledge/search', {
      params: { q: query, ...options },
    });
    return response.data;
  },

  createRelationship: async (
    relationship: RelationshipCreate
  ): Promise<Relationship> => {
    const response = await api.post(
      '/api/knowledge/relationship',
      relationship
    );
    return response.data;
  },

  getRelationshipById: async (
    relationshipId: number
  ): Promise<Relationship> => {
    const response = await api.get(
      `/api/knowledge/relationship/${relationshipId}`
    );
    return response.data;
  },

  updateRelationship: async (
    relationshipId: number,
    updates: RelationshipUpdate
  ): Promise<Relationship> => {
    const response = await api.patch(
      `/api/knowledge/relationship/${relationshipId}`,
      updates
    );
    return response.data;
  },

  deleteRelationship: async (
    relationshipId: number
  ): Promise<{ success: boolean; deleted_id: number }> => {
    const response = await api.delete(
      `/api/knowledge/relationship/${relationshipId}`
    );
    return response.data;
  },

  getConceptRelationships: async (
    conceptId: number
  ): Promise<Relationship[]> => {
    const response = await api.get(`/api/knowledge/relationships/${conceptId}`);
    return response.data;
  },

  getGraph: async (
    bookId: number,
    bookType: 'epub' | 'pdf'
  ): Promise<GraphData> => {
    const response = await api.get(`/api/knowledge/graph/${bookId}`, {
      params: { book_type: bookType },
    });
    return response.data;
  },

  getStats: async (): Promise<KnowledgeStats> => {
    const response = await api.get('/api/knowledge/stats');
    return response.data;
  },

  recalculateImportance: async (
    bookId: number,
    bookType: 'epub' | 'pdf'
  ): Promise<{
    success: boolean;
    book_id: number;
    concepts_updated: number;
    new_importance_values: Record<number, number>;
  }> => {
    const response = await api.post(
      `/api/knowledge/recalculate-importance/${bookId}`,
      null,
      { params: { book_type: bookType } }
    );
    return response.data;
  },

  deleteBookKnowledge: async (
    bookId: number,
    bookType: 'epub' | 'pdf'
  ): Promise<{
    success: boolean;
    book_id: number;
    embeddings_deleted: number;
  }> => {
    const response = await api.delete(`/api/knowledge/book/${bookId}`, {
      params: { book_type: bookType },
    });
    return response.data;
  },

  // ========================================
  // EXTRACTION STATUS & CANCELLATION
  // ========================================

  /**
   * Get the status of running extractions.
   * If sectionId is provided with bookId and bookType, returns status of that specific extraction.
   * Otherwise returns all running extractions (optionally filtered).
   */
  getExtractionStatus: async (options?: {
    book_id?: number;
    book_type?: 'epub' | 'pdf';
    section_id?: string;
  }): Promise<ExtractionStatusResponse> => {
    const response = await api.get('/api/knowledge/extraction-status', {
      params: options,
    });
    return response.data;
  },

  /**
   * Cancel a running extraction.
   * If sectionId is provided, cancels just that section.
   * If sectionId is not provided, cancels all running extractions for the book.
   */
  cancelExtraction: async (
    bookId: number,
    bookType: 'epub' | 'pdf',
    sectionId?: string
  ): Promise<CancelExtractionResponse> => {
    const response = await api.post('/api/knowledge/cancel-extraction', null, {
      params: {
        book_id: bookId,
        book_type: bookType,
        section_id: sectionId,
      },
    });
    return response.data;
  },
};
