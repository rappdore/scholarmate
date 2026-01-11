import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from 'react';
import { epubService } from '../services/epubService';
import type { EPUBHighlight, HighlightColor } from '../utils/epubHighlights';

interface EPUBHighlightRequest {
  nav_id: string;
  chapter_id?: string;
  start_xpath: string;
  start_offset: number;
  end_xpath: string;
  end_offset: number;
  highlight_text: string;
  color: HighlightColor;
}

interface EPUBHighlightsContextType {
  highlights: EPUBHighlight[];
  isLoading: boolean;
  error: string | null;
  currentEpubId: number | null;
  createHighlight: (
    highlightData: EPUBHighlightRequest
  ) => Promise<EPUBHighlight | null>;
  deleteHighlight: (highlightId: number) => Promise<boolean>;
  updateHighlightColor: (
    highlightId: number,
    color: HighlightColor
  ) => Promise<boolean>;
  refreshHighlights: () => Promise<void>;
  setCurrentEpubId: (epubId: number | null) => void;
  getHighlightsForSection: (navId: string) => EPUBHighlight[];
  getHighlightsForChapter: (chapterId: string) => EPUBHighlight[];
}

const EPUBHighlightsContext = createContext<
  EPUBHighlightsContextType | undefined
>(undefined);

export const useEPUBHighlightsContext = () => {
  const context = useContext(EPUBHighlightsContext);
  if (context === undefined) {
    throw new Error(
      'useEPUBHighlightsContext must be used within an EPUBHighlightsProvider'
    );
  }
  return context;
};

interface EPUBHighlightsProviderProps {
  children: React.ReactNode;
}

export const EPUBHighlightsProvider: React.FC<EPUBHighlightsProviderProps> = ({
  children,
}) => {
  const [highlights, setHighlights] = useState<EPUBHighlight[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentEpubId, setCurrentEpubId] = useState<number | null>(null);

  // Load highlights for the current EPUB
  const loadHighlights = useCallback(async () => {
    if (!currentEpubId) {
      setHighlights([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const loadedHighlights =
        await epubService.getAllHighlights(currentEpubId);
      setHighlights(loadedHighlights);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load EPUB highlights'
      );
      console.error('Error loading EPUB highlights:', err);
    } finally {
      setIsLoading(false);
    }
  }, [currentEpubId]);

  // Create a new highlight
  const createHighlight = useCallback(
    async (
      highlightData: EPUBHighlightRequest
    ): Promise<EPUBHighlight | null> => {
      if (!currentEpubId) {
        setError('No EPUB selected');
        return null;
      }

      setError(null);

      try {
        const newHighlight = await epubService.createEPUBHighlight(
          currentEpubId,
          highlightData
        );

        // Add to local state immediately for instant feedback
        setHighlights(prev => [...prev, newHighlight]);

        return newHighlight;
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to create EPUB highlight'
        );
        console.error('Error creating EPUB highlight:', err);
        return null;
      }
    },
    [currentEpubId]
  );

  // Delete a highlight
  const deleteHighlight = useCallback(
    async (highlightId: number): Promise<boolean> => {
      setError(null);

      try {
        await epubService.deleteEPUBHighlight(String(highlightId));

        // Remove from local state immediately
        setHighlights(prev => prev.filter(h => h.id !== highlightId));

        return true;
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to delete EPUB highlight'
        );
        console.error('Error deleting EPUB highlight:', err);
        return false;
      }
    },
    []
  );

  // Update highlight color
  const updateHighlightColor = useCallback(
    async (highlightId: number, color: HighlightColor): Promise<boolean> => {
      setError(null);

      try {
        await epubService.updateEPUBHighlightColor(highlightId, color);

        // Update local state immediately
        setHighlights(prev =>
          prev.map(h => (h.id === highlightId ? { ...h, color } : h))
        );

        return true;
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to update EPUB highlight color'
        );
        console.error('Error updating EPUB highlight color:', err);
        return false;
      }
    },
    []
  );

  // Get highlights for a specific section (navId)
  const getHighlightsForSection = useCallback(
    (navId: string): EPUBHighlight[] => {
      return highlights.filter(h => h.nav_id === navId);
    },
    [highlights]
  );

  // Get highlights for a specific chapter
  const getHighlightsForChapter = useCallback(
    (chapterId: string): EPUBHighlight[] => {
      return highlights.filter(h => h.chapter_id === chapterId);
    },
    [highlights]
  );

  // Load highlights when epubId changes
  useEffect(() => {
    loadHighlights();
  }, [loadHighlights]);

  const value: EPUBHighlightsContextType = {
    highlights,
    isLoading,
    error,
    currentEpubId,
    createHighlight,
    deleteHighlight,
    updateHighlightColor,
    refreshHighlights: loadHighlights,
    setCurrentEpubId,
    getHighlightsForSection,
    getHighlightsForChapter,
  };

  return (
    <EPUBHighlightsContext.Provider value={value}>
      {children}
    </EPUBHighlightsContext.Provider>
  );
};
