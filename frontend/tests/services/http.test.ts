import { describe, it, expect, vi, afterEach } from 'vitest';
import { streamSSE } from '../../src/services/http';
import { API_BASE_URL } from '../../src/services/config';

/**
 * Build a minimal fetch-like response whose body streams the given strings
 * as UTF-8 chunks, mimicking an SSE response.
 */
function sseResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  const encoded = chunks.map(chunk => encoder.encode(chunk));
  let index = 0;

  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    headers: new Headers(),
    body: {
      getReader() {
        return {
          read: async () =>
            index < encoded.length
              ? { done: false as const, value: encoded[index++] }
              : { done: true as const, value: undefined },
          releaseLock() {},
        };
      },
    },
  };
}

function stubFetch(chunks: string[]) {
  const fetchMock = vi.fn().mockResolvedValue(sseResponse(chunks));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('streamSSE', () => {
  it('POSTs the body to the absolute backend URL', async () => {
    const fetchMock = stubFetch(['data: {"done":true}\n']);

    for await (const _ of streamSSE('/ai/chat', { message: 'hi' })) {
      void _;
    }

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/ai/chat`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ message: 'hi' }),
      })
    );
  });

  it('yields parsed events and ends after the done event', async () => {
    stubFetch([
      'data: {"content":"a"}\n',
      'data: {"content":"b"}\ndata: {"done":true}\ndata: {"content":"after"}\n',
    ]);

    const received = [];
    for await (const event of streamSSE('/x', {})) {
      received.push(event);
    }

    expect(received).toEqual([
      { content: 'a' },
      { content: 'b' },
      { done: true },
    ]);
  });

  it('ends after a cancelled event', async () => {
    stubFetch(['data: {"cancelled":true}\ndata: {"content":"after"}\n']);

    const received = [];
    for await (const event of streamSSE('/x', {})) {
      received.push(event);
    }

    expect(received).toEqual([{ cancelled: true }]);
  });

  it('throws on backend error events', async () => {
    stubFetch(['data: {"error":"model exploded"}\n']);

    const generator = streamSSE('/x', {});
    await expect(generator.next()).rejects.toThrow('model exploded');
  });

  it('throws on non-2xx responses with the body included', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => 'kaboom',
      })
    );

    const generator = streamSSE('/x', {});
    await expect(generator.next()).rejects.toThrow(
      'HTTP error! status: 500, body: kaboom'
    );
  });

  it('skips malformed lines and reassembles events split across chunks', async () => {
    stubFetch([
      'data: {not json}\ndata: {"con',
      'tent":"ok"}\ndata: {"done":true}\n',
    ]);

    const received = [];
    for await (const event of streamSSE('/x', {})) {
      received.push(event);
    }

    expect(received).toEqual([{ content: 'ok' }, { done: true }]);
  });

  it('forwards the abort signal to fetch', async () => {
    const fetchMock = stubFetch(['data: {"done":true}\n']);
    const controller = new AbortController();

    for await (const _ of streamSSE('/x', {}, controller.signal)) {
      void _;
    }

    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ signal: controller.signal })
    );
  });
});
