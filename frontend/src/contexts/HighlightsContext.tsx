import { useCallback } from 'react';
import { highlightService } from '../services/api';
import type { Highlight, HighlightRequest } from '../types/highlights';
import { createHighlightsStore } from './createHighlightsStore';

const store = createHighlightsStore<Highlight, HighlightRequest, string>({
  label: 'highlight',
  load: pdfId => highlightService.getHighlightsForPdf(pdfId),
  create: (_pdfId, data) => highlightService.createHighlight(data),
  remove: highlightId => highlightService.deleteHighlight(highlightId),
  updateColor: (highlightId, color) =>
    highlightService.updateHighlightColor(highlightId, color),
  hasId: (highlight, highlightId) => highlight.id === highlightId,
  withColor: (highlight, color) => ({
    ...highlight,
    color,
    updatedAt: new Date(),
  }),
});

export const HighlightsProvider = store.Provider;

export function useHighlightsContext() {
  const { currentDocumentId, setCurrentDocumentId, highlights, ...rest } =
    store.useStore();

  // Get highlights for a specific page
  const getHighlightsForPage = useCallback(
    (pageNumber: number): Highlight[] =>
      highlights.filter(h => h.pageNumber === pageNumber),
    [highlights]
  );

  return {
    ...rest,
    highlights,
    currentPdfId: currentDocumentId,
    setCurrentPdfId: setCurrentDocumentId,
    getHighlightsForPage,
  };
}
