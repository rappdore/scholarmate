import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAsyncData } from '../../src/hooks/useAsyncData';

describe('useAsyncData', () => {
  it('resolves data for the given key', async () => {
    const fetcher = vi.fn().mockResolvedValue('payload');
    const { result } = renderHook(() =>
      useAsyncData(7, fetcher, 'Failed to load')
    );

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe('payload');
    expect(result.current.error).toBeNull();
    expect(fetcher).toHaveBeenCalledWith(7);
  });

  it('skips fetching when the key is undefined', async () => {
    const fetcher = vi.fn();
    const { result } = renderHook(() =>
      useAsyncData(undefined, fetcher, 'Failed to load')
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.data).toBeNull();
  });

  it('reports the error text on failure', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() =>
      useAsyncData(1, fetcher, 'Failed to load statistics')
    );

    await waitFor(() =>
      expect(result.current.error).toBe('Failed to load statistics')
    );
    expect(result.current.loading).toBe(false);
  });

  it('drops a stale response when the key changes mid-flight', async () => {
    let resolveFirst: (v: string) => void;
    const first = new Promise<string>(r => (resolveFirst = r));
    const fetcher = vi
      .fn()
      .mockImplementationOnce(() => first)
      .mockResolvedValueOnce('newer');

    const { result, rerender } = renderHook(
      ({ key }: { key: number }) => useAsyncData(key, fetcher, 'fail'),
      { initialProps: { key: 1 } }
    );

    rerender({ key: 2 });
    await waitFor(() => expect(result.current.data).toBe('newer'));

    resolveFirst!('stale');
    await first;
    expect(result.current.data).toBe('newer');
  });

  it('does not refetch when only the fetcher identity changes', async () => {
    const fetcher = vi.fn().mockResolvedValue('a');
    const { result, rerender } = renderHook(
      // A new closure each render, like callers writing inline fetchers
      ({ key }: { key: number }) =>
        useAsyncData(key, id => fetcher(id), 'fail'),
      { initialProps: { key: 1 } }
    );

    await waitFor(() => expect(result.current.data).toBe('a'));
    rerender({ key: 1 });
    rerender({ key: 1 });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
