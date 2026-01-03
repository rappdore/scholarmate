/**
 * TTS WebSocket service for managing text-to-speech communication.
 */

import { audioPlayer } from '../utils/audioPlayer';

// TTS configuration - change this to adjust default playback speed
export const DEFAULT_TTS_SPEED = 1.5;

type TTSState = 'idle' | 'connecting' | 'playing' | 'stopping';

interface SentenceInfo {
  text: string;
  startOffset: number;
  endOffset: number;
}

interface TTSEventHandlers {
  onStateChange?: (state: TTSState) => void;
  onSentenceStart?: (
    index: number,
    text: string,
    startOffset: number,
    endOffset: number
  ) => void;
  onSentenceEnd?: (index: number) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
}

class TTSService {
  private ws: WebSocket | null = null;
  private state: TTSState = 'idle';
  private handlers: TTSEventHandlers = {};
  private currentSentences: SentenceInfo[] = [];
  private cleanupPromise: Promise<void> | null = null;

  private getWsUrl(): string {
    // Use environment variable if available, otherwise derive from current location
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const backendPort = import.meta.env.VITE_BACKEND_PORT || '8000';
    return `${wsProtocol}//${window.location.hostname}:${backendPort}/ws/tts`;
  }

  setHandlers(handlers: TTSEventHandlers) {
    this.handlers = handlers;

    // Trigger sentence start when audio actually starts playing (not when received)
    audioPlayer.setOnSentenceStart(index => {
      const sentenceInfo = this.currentSentences[index];
      if (sentenceInfo) {
        this.handlers.onSentenceStart?.(
          index,
          sentenceInfo.text,
          sentenceInfo.startOffset,
          sentenceInfo.endOffset
        );
      }
    });

    audioPlayer.setOnSentenceComplete(index => {
      this.handlers.onSentenceEnd?.(index);
    });
  }

  private setState(newState: TTSState) {
    this.state = newState;
    this.handlers.onStateChange?.(newState);
  }

  getState(): TTSState {
    return this.state;
  }

  getSentences(): SentenceInfo[] {
    return this.currentSentences;
  }

  async start(
    text: string,
    voice: string = 'af_heart',
    speed: number = DEFAULT_TTS_SPEED
  ): Promise<void> {
    if (this.state !== 'idle') {
      await this.stop();
    }

    this.setState('connecting');
    this.currentSentences = [];

    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.getWsUrl());

      this.ws.onopen = () => {
        this.setState('playing');
        this.ws!.send(
          JSON.stringify({
            type: 'start',
            text,
            voice,
            speed,
          })
        );
        resolve();
      };

      this.ws.onmessage = event => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch (e) {
          console.error('Failed to parse TTS message:', e);
          return;
        }

        switch (data.type) {
          case 'sentence_start':
            // Store sentence info (text + offsets) for when audio actually starts playing
            this.currentSentences[data.index] = {
              text: data.text,
              startOffset: data.startOffset,
              endOffset: data.endOffset,
            };
            // Note: onSentenceStart is NOT called here - it's called by audioPlayer
            // when the audio for this sentence actually begins playing
            break;

          case 'audio':
            audioPlayer.queueAudio(data.data, data.index);
            break;

          case 'sentence_end':
            // Server signals sentence audio fully sent; actual playback completion
            // is handled by audioPlayer.onSentenceComplete callback
            break;

          case 'done':
            this.waitForAudioComplete()
              .then(() => {
                this.cleanup();
                this.handlers.onDone?.();
              })
              .catch(err => {
                console.error('TTS: Error during completion handling:', err);
                this.cleanup();
              });
            break;

          case 'stopped':
            this.cleanup();
            break;

          case 'error':
            this.handlers.onError?.(data.message);
            this.cleanup();
            break;
        }
      };

      this.ws.onerror = () => {
        reject(new Error('WebSocket connection failed'));
        this.cleanup();
      };

      this.ws.onclose = () => {
        if (this.state === 'playing') {
          this.cleanup();
        }
      };
    });
  }

  private async waitForAudioComplete(): Promise<void> {
    const maxWaitMs = 60000; // 60 second timeout
    const startTime = Date.now();

    while (audioPlayer.getIsPlaying()) {
      if (Date.now() - startTime > maxWaitMs) {
        console.warn('TTS: Audio playback timeout, forcing cleanup');
        audioPlayer.stop();
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }

  async stop(): Promise<void> {
    if (this.state === 'idle') return;

    // If already stopping, wait for that to complete
    if (this.cleanupPromise) {
      await this.cleanupPromise;
      return;
    }

    this.setState('stopping');
    audioPlayer.stop();

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'stop' }));
    }

    this.cleanupPromise = this.cleanup();
    await this.cleanupPromise;
  }

  private async cleanup(): Promise<void> {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.currentSentences = [];
    this.setState('idle');
    this.cleanupPromise = null;
  }
}

export const ttsService = new TTSService();
