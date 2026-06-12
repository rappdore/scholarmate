import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import {
  createHighlightsStore,
  type HighlightsApi,
} from '../../src/contexts/createHighlightsStore';
import type { HighlightColor } from '../../src/types/highlights';

interface FakeHighlight {
  id: number;
  text: string;
  color: HighlightColor;
}

type FakeRequest = { text: string; color: HighlightColor };

function makeApi(
  overrides: Partial<HighlightsApi<FakeHighlight, FakeRequest, number>> = {}
): HighlightsApi<FakeHighlight, FakeRequest, number> {
  return {
    label: 'fake highlight',
    load: vi.fn().mockResolvedValue([]),
    create: vi
      .fn()
      .mockImplementation(async (_docId: number, data: FakeRequest) => ({
        id: 99,
        text: data.text,
        color: data.color,
      })),
    remove: vi.fn().mockResolvedValue(true),
    updateColor: vi.fn().mockResolvedValue(true),
    hasId: (h, id) => h.id === id,
    withColor: (h, color) => ({ ...h, color }),
    ...overrides,
  };
}

function setup(api: HighlightsApi<FakeHighlight, FakeRequest, number>) {
  const store = createHighlightsStore(api);
  let captured: ReturnType<typeof store.useStore>;

  function Probe() {
    captured = store.useStore();
    return (
      <div>
        <span data-testid="count">{captured.highlights.length}</span>
        <span data-testid="error">{captured.error ?? ''}</span>
        <span data-testid="texts">
          {captured.highlights.map(h => h.text).join(',')}
        </span>
        <span data-testid="colors">
          {captured.highlights.map(h => h.color).join(',')}
        </span>
      </div>
    );
  }

  render(
    <store.Provider>
      <Probe />
    </store.Provider>
  );

  return {
    get store() {
      return captured!;
    },
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('createHighlightsStore', () => {
  it('loads highlights when a document id is set, including id 0', async () => {
    const api = makeApi({
      load: vi
        .fn()
        .mockResolvedValue([{ id: 1, text: 'hello', color: 'yellow' }]),
    });
    const ctx = setup(api);

    act(() => ctx.store.setCurrentDocumentId(0));

    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('1')
    );
    expect(api.load).toHaveBeenCalledWith(0);
  });

  it('clears highlights when the document id is cleared', async () => {
    const api = makeApi({
      load: vi.fn().mockResolvedValue([{ id: 1, text: 'a', color: 'yellow' }]),
    });
    const ctx = setup(api);

    act(() => ctx.store.setCurrentDocumentId(5));
    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('1')
    );

    act(() => ctx.store.setCurrentDocumentId(null));
    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('0')
    );
  });

  it('drops a stale response when the document changes mid-flight', async () => {
    let resolveFirst: (h: FakeHighlight[]) => void;
    const first = new Promise<FakeHighlight[]>(r => (resolveFirst = r));
    const load = vi
      .fn()
      .mockImplementationOnce(() => first)
      .mockResolvedValueOnce([{ id: 2, text: 'newer', color: 'blue' }]);
    const ctx = setup(makeApi({ load }));

    act(() => ctx.store.setCurrentDocumentId(1));
    act(() => ctx.store.setCurrentDocumentId(2));

    await waitFor(() =>
      expect(screen.getByTestId('texts').textContent).toBe('newer')
    );

    // Old request resolving late must not overwrite the newer data
    await act(async () => {
      resolveFirst!([{ id: 1, text: 'stale', color: 'yellow' }]);
      await first;
    });
    expect(screen.getByTestId('texts').textContent).toBe('newer');
  });

  it('adds created highlights optimistically', async () => {
    const ctx = setup(makeApi());
    act(() => ctx.store.setCurrentDocumentId(3));
    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('0')
    );

    await act(async () => {
      const created = await ctx.store.createHighlight({
        text: 'fresh',
        color: 'green',
      });
      expect(created).toEqual({ id: 99, text: 'fresh', color: 'green' });
    });
    expect(screen.getByTestId('texts').textContent).toBe('fresh');
  });

  it('refuses to create when no document is selected', async () => {
    const api = makeApi();
    const ctx = setup(api);

    await act(async () => {
      const created = await ctx.store.createHighlight({
        text: 'x',
        color: 'yellow',
      });
      expect(created).toBeNull();
    });
    expect(api.create).not.toHaveBeenCalled();
    expect(screen.getByTestId('error').textContent).toBe(
      'No document selected'
    );
  });

  it('removes deleted highlights from state only on success', async () => {
    const api = makeApi({
      load: vi.fn().mockResolvedValue([
        { id: 1, text: 'a', color: 'yellow' },
        { id: 2, text: 'b', color: 'blue' },
      ]),
      remove: vi.fn().mockResolvedValueOnce(true).mockResolvedValueOnce(false),
    });
    const ctx = setup(api);
    act(() => ctx.store.setCurrentDocumentId(1));
    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('2')
    );

    await act(async () => {
      expect(await ctx.store.deleteHighlight(1)).toBe(true);
    });
    expect(screen.getByTestId('texts').textContent).toBe('b');

    await act(async () => {
      expect(await ctx.store.deleteHighlight(2)).toBe(false);
    });
    expect(screen.getByTestId('texts').textContent).toBe('b');
  });

  it('recolors via withColor on success', async () => {
    const api = makeApi({
      load: vi.fn().mockResolvedValue([{ id: 1, text: 'a', color: 'yellow' }]),
    });
    const ctx = setup(api);
    act(() => ctx.store.setCurrentDocumentId(1));
    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('1')
    );

    await act(async () => {
      expect(await ctx.store.updateHighlightColor(1, 'purple')).toBe(true);
    });
    expect(screen.getByTestId('colors').textContent).toBe('purple');
    expect(api.updateColor).toHaveBeenCalledWith(1, 'purple');
  });

  it('surfaces load failures as errors', async () => {
    const api = makeApi({
      load: vi.fn().mockRejectedValue(new Error('backend down')),
    });
    const ctx = setup(api);
    act(() => ctx.store.setCurrentDocumentId(1));

    await waitFor(() =>
      expect(screen.getByTestId('error').textContent).toBe('backend down')
    );
  });
});
