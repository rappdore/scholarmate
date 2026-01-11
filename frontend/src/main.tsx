import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { HighlightsProvider } from './contexts/HighlightsContext';
import { EPUBHighlightsProvider } from './contexts/EPUBHighlightsContext';
import { SettingsProvider } from './contexts/SettingsContext';
import './index.css';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <SettingsProvider>
        <HighlightsProvider>
          <EPUBHighlightsProvider>
            <App />
          </EPUBHighlightsProvider>
        </HighlightsProvider>
      </SettingsProvider>
    </BrowserRouter>
  </StrictMode>
);
