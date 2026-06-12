/**
 * Centralized backend endpoint configuration — the single source of truth
 * for every HTTP and WebSocket URL the frontend builds.
 *
 * The backend is always addressed by absolute URL so the app behaves
 * identically under the Vite dev server, a static build, and the packaged
 * Electron app (file:// origin, where relative `/api/...` paths and
 * `window.location.hostname` both break). Set VITE_API_URL to point at a
 * backend running elsewhere.
 */

const DEFAULT_API_URL = 'http://127.0.0.1:8000';

/** Resolve the HTTP base URL from an optional override (no trailing slash). */
export function resolveApiBaseUrl(override: string | undefined): string {
  const base = override?.trim() ? override.trim() : DEFAULT_API_URL;
  return base.replace(/\/+$/, '');
}

/** Derive the WebSocket base URL from an HTTP base URL. */
export function toWsBaseUrl(httpBaseUrl: string): string {
  return httpBaseUrl.replace(/^http/, 'ws');
}

export const API_BASE_URL: string = resolveApiBaseUrl(
  import.meta.env.VITE_API_URL
);

export const WS_BASE_URL: string = toWsBaseUrl(API_BASE_URL);
