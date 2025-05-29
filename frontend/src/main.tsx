import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './index.css';
import App from './App.tsx';
import { HighlightsProvider } from './contexts/HighlightsContext.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <HighlightsProvider>
        <App />
      </HighlightsProvider>
    </BrowserRouter>
  </StrictMode>
);
