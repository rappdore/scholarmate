import { describe, it, expect } from 'vitest';
import {
  resolveApiBaseUrl,
  toWsBaseUrl,
  API_BASE_URL,
  WS_BASE_URL,
} from '../../src/services/config';

describe('resolveApiBaseUrl', () => {
  it('falls back to the local backend when no override is set', () => {
    expect(resolveApiBaseUrl(undefined)).toBe('http://127.0.0.1:8000');
  });

  it('uses the VITE_API_URL override when provided', () => {
    expect(resolveApiBaseUrl('http://192.168.1.5:9000')).toBe(
      'http://192.168.1.5:9000'
    );
  });

  it('strips trailing slashes so path concatenation is safe', () => {
    expect(resolveApiBaseUrl('http://localhost:8000/')).toBe(
      'http://localhost:8000'
    );
    expect(resolveApiBaseUrl('http://localhost:8000//')).toBe(
      'http://localhost:8000'
    );
  });

  it('treats blank overrides as unset', () => {
    expect(resolveApiBaseUrl('')).toBe('http://127.0.0.1:8000');
    expect(resolveApiBaseUrl('   ')).toBe('http://127.0.0.1:8000');
  });
});

describe('toWsBaseUrl', () => {
  it('converts http to ws', () => {
    expect(toWsBaseUrl('http://127.0.0.1:8000')).toBe('ws://127.0.0.1:8000');
  });

  it('converts https to wss', () => {
    expect(toWsBaseUrl('https://example.com')).toBe('wss://example.com');
  });
});

describe('exported constants', () => {
  it('WS_BASE_URL is derived from API_BASE_URL', () => {
    expect(WS_BASE_URL).toBe(toWsBaseUrl(API_BASE_URL));
  });

  it('API_BASE_URL is absolute (works under file:// in Electron)', () => {
    expect(API_BASE_URL).toMatch(/^https?:\/\//);
  });
});
