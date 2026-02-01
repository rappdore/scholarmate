// Preload script runs in renderer context but has access to Node.js
// Used to safely expose APIs to the renderer process

import { contextBridge } from 'electron';

// Expose protected methods that allow the renderer process to use
// specific electron features without exposing the entire API
contextBridge.exposeInMainWorld('electronAPI', {
  // Add any IPC methods here if needed in the future
  // For now, the app communicates directly with the backend via HTTP
  platform: process.platform,
  isElectron: true,
});

// Type declaration for the exposed API
declare global {
  interface Window {
    electronAPI: {
      platform: NodeJS.Platform;
      isElectron: boolean;
    };
  }
}
