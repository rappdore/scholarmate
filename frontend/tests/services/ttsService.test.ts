import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../src/utils/audioPlayer', () => ({
  audioPlayer: {
    stop: vi.fn(),
    getIsPlaying: vi.fn(() => false),
    setOnSentenceStart: vi.fn(),
    setOnSentenceComplete: vi.fn(),
    queueAudio: vi.fn(),
  },
}));

import { ttsService } from '../../src/services/ttsService';

class FakeWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.OPEN;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }
}

/** Start a TTS session and simulate the socket opening. */
async function startSession(): Promise<FakeWebSocket> {
  const startPromise = ttsService.start('hello world');
  const ws = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  ws.onopen?.();
  await startPromise;
  return ws;
}

describe('ttsService stop/cleanup lifecycle', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  it('stop() is a no-op when idle', async () => {
    expect(ttsService.getState()).toBe('idle');
    await ttsService.stop();
    expect(ttsService.getState()).toBe('idle');
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('stop() sends a stop message, closes the socket, and returns to idle', async () => {
    const ws = await startSession();
    expect(ttsService.getState()).toBe('playing');

    await ttsService.stop();

    expect(ttsService.getState()).toBe('idle');
    expect(ws.readyState).toBe(FakeWebSocket.CLOSED);
    expect(ws.sent).toContainEqual(JSON.stringify({ type: 'stop' }));
  });

  it('stop() still works on subsequent sessions (cleanupPromise is cleared)', async () => {
    // Regression (F-6): cleanup() used to null cleanupPromise synchronously
    // BEFORE stop() overwrote it with the resolved promise, so every later
    // stop() hit the early-return and never cleaned up.
    await startSession();
    await ttsService.stop();
    expect(ttsService.getState()).toBe('idle');

    const ws2 = await startSession();
    expect(ttsService.getState()).toBe('playing');

    await ttsService.stop();

    expect(ttsService.getState()).toBe('idle');
    expect(ws2.readyState).toBe(FakeWebSocket.CLOSED);
  });

  it('concurrent stop() calls both resolve and leave the service idle', async () => {
    await startSession();

    await Promise.all([ttsService.stop(), ttsService.stop()]);

    expect(ttsService.getState()).toBe('idle');

    // And the service can still start/stop afterwards
    const ws = await startSession();
    await ttsService.stop();
    expect(ttsService.getState()).toBe('idle');
    expect(ws.readyState).toBe(FakeWebSocket.CLOSED);
  });
});
