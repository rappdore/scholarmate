import { useCallback } from 'react';
import { epubService } from '../services/epubService';
import type { EPUBHighlight } from '../utils/epubHighlights';
import type { HighlightColor } from '../types/highlights';
import { createHighlightsStore } from './createHighlightsStore';

export interface EPUBHighlightRequest {
  nav_id: string;
  chapter_id?: string;
  start_xpath: string;
  start_offset: number;
  end_xpath: string;
  end_offset: number;
  highlight_text: string;
  color: HighlightColor;
}

const store = createHighlightsStore<
  EPUBHighlight,
  EPUBHighlightRequest,
  number
>({
  label: 'EPUB highlight',
  load: epubId => epubService.getAllHighlights(epubId),
  create: (epubId, data) => epubService.createEPUBHighlight(epubId, data),
  remove: async highlightId => {
    await epubService.deleteEPUBHighlight(String(highlightId));
    return true;
  },
  updateColor: async (highlightId, color) => {
    await epubService.updateEPUBHighlightColor(highlightId, color);
    return true;
  },
  hasId: (highlight, highlightId) => highlight.id === highlightId,
  withColor: (highlight, color) => ({ ...highlight, color }),
});

export const EPUBHighlightsProvider = store.Provider;

export function useEPUBHighlightsContext() {
  const { currentDocumentId, setCurrentDocumentId, highlights, ...rest } =
    store.useStore();

  // Get highlights for a specific section (navId)
  const getHighlightsForSection = useCallback(
    (navId: string): EPUBHighlight[] =>
      highlights.filter(h => h.nav_id === navId),
    [highlights]
  );

  // Get highlights for a specific chapter
  const getHighlightsForChapter = useCallback(
    (chapterId: string): EPUBHighlight[] =>
      highlights.filter(h => h.chapter_id === chapterId),
    [highlights]
  );

  return {
    ...rest,
    highlights,
    currentEpubId: currentDocumentId,
    setCurrentEpubId: setCurrentDocumentId,
    getHighlightsForSection,
    getHighlightsForChapter,
  };
}
