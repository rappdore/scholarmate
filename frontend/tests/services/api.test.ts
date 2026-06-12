import { describe, it, expect, vi, afterEach } from 'vitest';
import { chatService } from '../../src/services/api';
import { parseSSELine } from '../../src/services/http';
import { dualChatService } from '../../src/services/dualChatService';

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
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse(chunks)));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('parseSSELine', () => {
  it('parses a valid data line', () => {
    expect(parseSSELine('data: {"type":"response","content":"hi"}')).toEqual({
      type: 'response',
      content: 'hi',
    });
  });

  it('returns null for non-data lines', () => {
    expect(parseSSELine('')).toBeNull();
    expect(parseSSELine(': keep-alive')).toBeNull();
    expect(parseSSELine('event: message')).toBeNull();
  });

  it('returns null for malformed JSON without throwing', () => {
    expect(parseSSELine('data: {not json}')).toBeNull();
  });
});

describe('chatService.streamChat', () => {
  it('yields parsed chunks and stops on done', async () => {
    stubFetch([
      'data: {"type":"response","content":"Hel"}\n',
      'data: {"type":"response","content":"lo"}\ndata: {"done":true}\n',
    ]);

    const received = [];
    for await (const chunk of chatService.streamChat('hi', 1, 1)) {
      received.push(chunk);
    }

    expect(received).toEqual([
      { type: 'response', content: 'Hel' },
      { type: 'response', content: 'lo' },
      { done: true },
    ]);
  });

  it('propagates backend SSE errors to the consumer', async () => {
    stubFetch([
      'data: {"type":"response","content":"Hi"}\n',
      'data: {"error":"model exploded"}\n',
    ]);

    const generator = chatService.streamChat('hi', 1, 1);
    const first = await generator.next();
    expect(first.value).toEqual({ type: 'response', content: 'Hi' });

    // Regression (F-4): the error used to be swallowed by the JSON.parse
    // try/catch and never reached the consumer.
    await expect(generator.next()).rejects.toThrow('model exploded');
  });

  it('skips malformed SSE lines and continues streaming', async () => {
    stubFetch([
      'data: {not json}\n',
      'data: {"content":"ok"}\ndata: {"done":true}\n',
    ]);

    const received = [];
    for await (const chunk of chatService.streamChat('hi', 1, 1)) {
      received.push(chunk);
    }

    expect(received).toEqual([{ content: 'ok' }, { done: true }]);
  });
});

describe('chatService.streamChatEpub', () => {
  it('propagates backend SSE errors to the consumer', async () => {
    stubFetch(['data: {"error":"epub boom"}\n']);

    const generator = chatService.streamChatEpub('hi', 1, 'section_1', 0);
    await expect(generator.next()).rejects.toThrow('epub boom');
  });
});

describe('dualChatService.streamDualChat', () => {
  it('propagates backend SSE errors to the consumer', async () => {
    stubFetch([
      'data: {"llm1":{"type":"response","content":"a"}}\n',
      'data: {"error":"dual boom"}\n',
    ]);

    const generator = dualChatService.streamDualChat('hi', 1, 1, [], [], 1, 2);
    const first = await generator.next();
    expect(first.value).toEqual({
      llm1: { type: 'response', content: 'a' },
    });

    await expect(generator.next()).rejects.toThrow('dual boom');
  });

  it('yields events until done', async () => {
    stubFetch([
      'data: {"llm1":{"content":"x"},"llm2":{"content":"y"}}\ndata: {"done":true}\n',
    ]);

    const received = [];
    for await (const event of dualChatService.streamDualChat(
      'hi',
      1,
      1,
      [],
      [],
      1,
      2
    )) {
      received.push(event);
    }

    expect(received).toEqual([
      { llm1: { content: 'x' }, llm2: { content: 'y' } },
      { done: true },
    ]);
  });
});
