/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend base URL override (build-time); see src/services/config.ts. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
