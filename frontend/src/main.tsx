import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
// HashRouter so routes resolve under the packaged Electron app, where the
// page is served via loadFile (file://) and a BrowserRouter pathname would
// never match any route.
import { HashRouter } from 'react-router-dom';
import { HighlightsProvider } from './contexts/HighlightsContext';
import { EPUBHighlightsProvider } from './contexts/EPUBHighlightsContext';
import { SettingsProvider } from './contexts/SettingsContext';
import './index.css';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <SettingsProvider>
        <HighlightsProvider>
          <EPUBHighlightsProvider>
            <App />
          </EPUBHighlightsProvider>
        </HighlightsProvider>
      </SettingsProvider>
    </HashRouter>
  </StrictMode>
);
