/**
 * Dual Chat Service - Handles communication with backend for dual LLM chat
 */
import { api, streamSSE } from './http';

/** Structured chunk for one LLM within a dual-chat SSE event (mirrors the
 * backend StreamParser events: thinking/response/metadata). */
export interface DualChatLLMChunk {
  type?: 'thinking' | 'response' | 'metadata';
  content?: string | null;
  metadata?: { thinking_complete?: boolean };
  error?: string;
  done?: boolean;
  cancelled?: boolean;
}

/** One SSE event from POST /ai/dual-chat. */
export interface DualChatStreamEvent {
  llm1?: DualChatLLMChunk;
  llm2?: DualChatLLMChunk;
  request_id?: string;
  done?: boolean;
  error?: string;
}

export const dualChatService = {
  /**
   * Stream responses from both LLMs simultaneously (PDF only)
   *
   * @param message - User message to send to both LLMs
   * @param pdfId - PDF document ID
   * @param pageNum - Current page number
   * @param llm1History - Chat history for LLM 1
   * @param llm2History - Chat history for LLM 2
   * @param primaryLLMId - ID of primary LLM configuration
   * @param secondaryLLMId - ID of secondary LLM configuration
   * @param abortSignal - Optional AbortSignal to cancel the request
   * @param isNewChat - Whether this is a new chat session
   */
  streamDualChat: async function* (
    message: string,
    pdfId: number,
    pageNum: number,
    llm1History: Array<{ role: string; content: string }>,
    llm2History: Array<{ role: string; content: string }>,
    primaryLLMId: number,
    secondaryLLMId: number,
    abortSignal?: AbortSignal,
    isNewChat?: boolean
  ): AsyncGenerator<DualChatStreamEvent, void, unknown> {
    try {
      yield* streamSSE(
        '/ai/dual-chat',
        {
          message,
          pdf_id: pdfId,
          page_num: pageNum,
          llm1_history: llm1History,
          llm2_history: llm2History,
          primary_llm_id: primaryLLMId,
          secondary_llm_id: secondaryLLMId,
          is_new_chat: isNewChat || false,
        },
        abortSignal
      );
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        // Request was aborted
        return;
      }
      throw new Error(
        `Dual chat failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  },

  /**
   * Stop both LLM streams for a dual chat session
   *
   * @param requestId - Request ID to stop
   */
  stopDualChat: async (requestId: string): Promise<void> => {
    try {
      await api.post(`/ai/dual-chat/stop/${requestId}`);
    } catch (error) {
      console.error('Error stopping dual chat:', error);
      throw error;
    }
  },
};
