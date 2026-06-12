import '@testing-library/jest-dom';

// vitest 4 + jsdom 27 expose `sessionStorage` but resolve the `localStorage`
// getter to undefined. Provide a spec-shaped Map-backed implementation so
// components that persist to localStorage are testable.
if (typeof window !== 'undefined' && !window.localStorage) {
  const store = new Map<string, string>();
  const localStorageShim: Storage = {
    get length() {
      return store.size;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null;
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
    removeItem(key: string) {
      store.delete(key);
    },
    clear() {
      store.clear();
    },
  };
  Object.defineProperty(window, 'localStorage', {
    value: localStorageShim,
    configurable: true,
  });
}
