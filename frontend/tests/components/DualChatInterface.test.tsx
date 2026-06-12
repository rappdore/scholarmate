/**
 * Regression tests for the DualChat Stop button (audit F-15): the stop
 * plumbing (request id tracking, AbortController, stopDualChat endpoint)
 * existed but no UI invoked it.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DualChatInterface from '../../src/components/DualChatInterface';
import { dualChatService } from '../../src/services/dualChatService';
import { getActiveLLMConfiguration } from '../../src/api/llmConfig';
import type { LLMConfiguration } from '../../src/types/llm';

vi.mock('../../src/services/dualChatService', () => ({
  dualChatService: {
    streamDualChat: vi.fn(),
    stopDualChat: vi.fn(),
  },
}));

vi.mock('../../src/api/llmConfig', () => ({
  getActiveLLMConfiguration: vi.fn(),
}));

vi.mock('../../src/services/api', () => ({
  notesService: { saveChatNote: vi.fn() },
}));

function makeLLM(id: number, name: string): LLMConfiguration {
  return {
    id,
    name,
    base_url: 'http://localhost:1234',
    model_name: name,
    is_active: true,
    always_starts_with_thinking: false,
    created_at: '',
    updated_at: '',
    api_key_preview: '',
  };
}

const PRIMARY = makeLLM(1, 'llm-one');

vi.mock('../../src/components/LLMSelectionModal', () => ({
  default: ({
    isOpen,
    onSelect,
  }: {
    isOpen: boolean;
    onSelect: (llm: LLMConfiguration) => void;
  }) =>
    isOpen ? (
      <button onClick={() => onSelect(makeLLM(2, 'llm-two'))}>
        pick-secondary
      </button>
    ) : null,
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getActiveLLMConfiguration).mockResolvedValue(PRIMARY);
});

/** Render, select the secondary LLM, and start a never-finishing stream. */
async function startStreaming() {
  const user = userEvent.setup();
  const captured: { signal?: AbortSignal } = {};

  vi.mocked(dualChatService.streamDualChat).mockImplementation(
    async function* (_msg, _pdf, _page, _h1, _h2, _id1, _id2, abortSignal) {
      captured.signal = abortSignal;
      yield { request_id: 'req-123' };
      // Stream never completes on its own; only Stop ends it
      await new Promise(() => {});
    }
  );

  render(<DualChatInterface pdfId={1} filename="doc.pdf" currentPage={2} />);

  await user.click(await screen.findByText('Select Second LLM'));
  await user.click(await screen.findByText('pick-secondary'));

  const textarea = await screen.findByPlaceholderText(/Ask about this PDF/);
  await user.type(textarea, 'compare these');
  await user.click(screen.getByRole('button', { name: 'Send' }));

  return { user, captured };
}

describe('DualChat Stop button (F-15)', () => {
  it('shows Stop while streaming and stops via the backend + abort', async () => {
    const { user, captured } = await startStreaming();

    // While streaming, the send button must become an enabled Stop button
    const stopButton = await screen.findByRole('button', { name: 'Stop' });
    expect(stopButton).toBeEnabled();

    await user.click(stopButton);

    await waitFor(() =>
      expect(dualChatService.stopDualChat).toHaveBeenCalledWith('req-123')
    );
    expect(captured.signal?.aborted).toBe(true);

    // Button reverts to Send once stopped
    await screen.findByRole('button', { name: 'Send' });
  });

  it('stops via Cmd/Ctrl+Enter while streaming', async () => {
    const { user } = await startStreaming();
    await screen.findByRole('button', { name: 'Stop' });

    await user.keyboard('{Meta>}{Enter}{/Meta}');

    await waitFor(() =>
      expect(dualChatService.stopDualChat).toHaveBeenCalledWith('req-123')
    );
  });
});
