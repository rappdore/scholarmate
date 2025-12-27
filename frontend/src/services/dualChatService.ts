/**
 * Dual Chat Service - Handles communication with backend for dual LLM chat
 */

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
  ): AsyncGenerator<
    {
      llm1?: { content?: string; done?: boolean; error?: string };
      llm2?: { content?: string; done?: boolean; error?: string };
      request_id?: string;
    },
    void,
    unknown
  > {
    try {
      const response = await fetch('http://localhost:8000/ai/dual-chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          pdf_id: pdfId,
          page_num: pageNum,
          llm1_history: llm1History,
          llm2_history: llm2History,
          primary_llm_id: primaryLLMId,
          secondary_llm_id: secondaryLLMId,
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

                // Yield the entire data object
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
      const response = await fetch(
        `http://localhost:8000/ai/dual-chat/stop/${requestId}`,
        {
          method: 'POST',
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to stop dual chat: ${response.status}`);
      }
    } catch (error) {
      console.error('Error stopping dual chat:', error);
      throw error;
    }
  },
};
