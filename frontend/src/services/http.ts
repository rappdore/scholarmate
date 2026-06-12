/**
 * Shared HTTP client and SSE streaming helper.
 *
 * Every backend call goes through either the `api` axios instance (plain
 * request/response) or `streamSSE` (server-sent-event POST streams), so URL
 * resolution and logging live in exactly one place.
 */
import axios from 'axios';
import { API_BASE_URL } from './config';

// Verbose request/response logging is only enabled in development builds to
// avoid dumping full payloads to the console in production.
export const devLog = (...args: unknown[]): void => {
  if (import.meta.env.DEV) {
    console.log(...args);
  }
};

export const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use(
  config => {
    devLog('🚀 [API REQUEST]', {
      method: config.method?.toUpperCase(),
      url: config.url,
      fullURL: `${config.baseURL}${config.url}`,
      headers: config.headers,
      data: config.data,
      timestamp: new Date().toISOString(),
    });
    return config;
  },
  error => {
    console.error('❌ [API REQUEST ERROR]', {
      message: error.message,
      error: error,
      timestamp: new Date().toISOString(),
    });
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  response => {
    devLog('✅ [API RESPONSE]', {
      status: response.status,
      statusText: response.statusText,
      url: response.config.url,
      fullURL: `${response.config.baseURL}${response.config.url}`,
      data: response.data,
      headers: response.headers,
      timestamp: new Date().toISOString(),
    });
    return response;
  },
  error => {
    console.error('❌ [API RESPONSE ERROR]', {
      message: error.message,
      url: error.config?.url,
      fullURL: error.config
        ? `${error.config.baseURL}${error.config.url}`
        : 'unknown',
      status: error.response?.status,
      statusText: error.response?.statusText,
      responseData: error.response?.data,
      code: error.code,
      isNetworkError: error.message === 'Network Error',
      isTimeout: error.code === 'ECONNABORTED',
      timestamp: new Date().toISOString(),
    });
    return Promise.reject(error);
  }
);

/**
 * Parse a single SSE line of the form `data: {...}`.
 * Returns the parsed payload, or null when the line is not a data line or
 * contains malformed JSON (malformed lines are logged and skipped so a single
 * bad chunk doesn't kill the stream).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function parseSSELine(line: string): Record<string, any> | null {
  if (!line.startsWith('data: ')) {
    return null;
  }
  try {
    return JSON.parse(line.slice(6));
  } catch (e) {
    console.error('Error parsing SSE data:', e, line);
    return null;
  }
}

/**
 * POST `body` to `path` and yield each parsed SSE data event.
 *
 * Behavior shared by every stream consumer:
 * - non-2xx responses throw with the response body included
 * - backend `{error}` events throw so the failure reaches the consumer
 *   (malformed lines are skipped inside parseSSELine)
 * - the final `{done}` / `{cancelled}` event is yielded, then the stream ends
 */
export async function* streamSSE(
  path: string,
  body: unknown,
  signal?: AbortSignal
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): AsyncGenerator<Record<string, any>, void, unknown> {
  const url = `${API_BASE_URL}${path}`;
  devLog('🚀 [SSE REQUEST]', {
    url,
    method: 'POST',
    body,
    timestamp: new Date().toISOString(),
  });

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('❌ [SSE ERROR]', {
      url,
      status: response.status,
      statusText: response.statusText,
      errorText,
      timestamp: new Date().toISOString(),
    });
    throw new Error(
      `HTTP error! status: ${response.status}, body: ${errorText}`
    );
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('Failed to get response reader');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const data = parseSSELine(line);
        if (data === null) {
          continue;
        }

        if (data.error) {
          throw new Error(data.error);
        }

        yield data;

        if (data.done || data.cancelled) {
          return;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
