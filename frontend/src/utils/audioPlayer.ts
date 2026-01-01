/**
 * Web Audio API wrapper for playing PCM audio chunks.
 * Handles queuing, sequential playback, and cleanup.
 */

type SentenceCallback = (sentenceIndex: number) => void;

class AudioPlayer {
  private audioContext: AudioContext | null = null;
  private queue: { buffer: AudioBuffer; sentenceIndex: number }[] = [];
  private isPlaying = false;
  private currentSource: AudioBufferSourceNode | null = null;
  private currentSentenceIndex: number = -1;
  private onSentenceStart: SentenceCallback | null = null;
  private onSentenceComplete: SentenceCallback | null = null;

  private readonly SAMPLE_RATE = 24000;

  private getContext(): AudioContext {
    if (!this.audioContext) {
      this.audioContext = new AudioContext({ sampleRate: this.SAMPLE_RATE });
    }
    return this.audioContext;
  }

  /**
   * Set callback for when a sentence starts playing (first audio chunk)
   */
  setOnSentenceStart(callback: SentenceCallback | null) {
    this.onSentenceStart = callback;
  }

  /**
   * Set callback for when a sentence finishes playing (last audio chunk)
   */
  setOnSentenceComplete(callback: SentenceCallback | null) {
    this.onSentenceComplete = callback;
  }

  private decodeBase64PCM(base64Data: string): AudioBuffer | null {
    try {
      const ctx = this.getContext();

      const binaryString = atob(base64Data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      const float32 = new Float32Array(bytes.buffer);

      const audioBuffer = ctx.createBuffer(1, float32.length, this.SAMPLE_RATE);
      audioBuffer.copyToChannel(float32, 0);

      return audioBuffer;
    } catch (e) {
      console.error('Failed to decode audio data:', e);
      return null;
    }
  }

  queueAudio(base64Data: string, sentenceIndex: number) {
    const buffer = this.decodeBase64PCM(base64Data);
    if (!buffer) {
      return; // Skip invalid audio data
    }
    this.queue.push({ buffer, sentenceIndex });

    if (!this.isPlaying) {
      this.playNext();
    }
  }

  private async playNext() {
    if (this.queue.length === 0) {
      this.isPlaying = false;
      // Final sentence completed when queue empties
      if (this.currentSentenceIndex >= 0) {
        this.onSentenceComplete?.(this.currentSentenceIndex);
        this.currentSentenceIndex = -1;
      }
      return;
    }

    this.isPlaying = true;
    const { buffer, sentenceIndex } = this.queue.shift()!;
    const ctx = this.getContext();

    if (ctx.state === 'suspended') {
      await ctx.resume();
    }

    // Check if this is a new sentence starting
    if (sentenceIndex !== this.currentSentenceIndex) {
      // Previous sentence completed (if there was one)
      if (this.currentSentenceIndex >= 0) {
        this.onSentenceComplete?.(this.currentSentenceIndex);
      }
      // New sentence starting
      this.currentSentenceIndex = sentenceIndex;
      this.onSentenceStart?.(sentenceIndex);
    }

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    source.onended = () => {
      this.currentSource = null;
      this.playNext();
    };

    this.currentSource = source;
    source.start();
  }

  stop() {
    this.queue = [];

    if (this.currentSource) {
      try {
        this.currentSource.stop();
      } catch {
        // Ignore if already stopped
      }
      this.currentSource = null;
    }

    this.isPlaying = false;
    this.currentSentenceIndex = -1;
  }

  getIsPlaying(): boolean {
    return this.isPlaying;
  }

  /**
   * Get the currently playing sentence index (-1 if none)
   */
  getCurrentSentenceIndex(): number {
    return this.currentSentenceIndex;
  }

  dispose() {
    this.stop();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}

export const audioPlayer = new AudioPlayer();
