import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from 'react';
import { highlightService } from '../services/api';
import type { Highlight, HighlightRequest } from '../types/highlights';

interface HighlightsContextType {
  highlights: Highlight[];
  isLoading: boolean;
  error: string | null;
  currentPdfId: number | null;
  createHighlight: (
    highlightData: HighlightRequest
  ) => Promise<Highlight | null>;
  deleteHighlight: (highlightId: string) => Promise<boolean>;
  updateHighlightColor: (
    highlightId: string,
    color: string
  ) => Promise<boolean>;
  refreshHighlights: () => Promise<void>;
  setCurrentPdfId: (pdfId: number | null) => void;
  getHighlightsForPage: (pageNumber: number) => Highlight[];
}

const HighlightsContext = createContext<HighlightsContextType | undefined>(
  undefined
);

export const useHighlightsContext = () => {
  const context = useContext(HighlightsContext);
  if (context === undefined) {
    throw new Error(
      'useHighlightsContext must be used within a HighlightsProvider'
    );
  }
  return context;
};

interface HighlightsProviderProps {
  children: React.ReactNode;
}

export const HighlightsProvider: React.FC<HighlightsProviderProps> = ({
  children,
}) => {
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPdfId, setCurrentPdfId] = useState<number | null>(null);

  // Load highlights for the current PDF.
  // `isCancelled` lets the loading effect drop stale responses (e.g. a slow
  // response for a previous PDF arriving after the user switched documents).
  const loadHighlights = useCallback(
    async (isCancelled?: () => boolean) => {
      // Use === null: 0 is a valid PDF id
      if (currentPdfId === null) {
        setHighlights([]);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const loadedHighlights = await highlightService.getHighlightsForPdf(
          currentPdfId
          // Don't filter by pageNumber to get all highlights
        );
        if (isCancelled?.()) return;
        setHighlights(loadedHighlights);
      } catch (err) {
        console.error('Error loading highlights:', err);
        if (isCancelled?.()) return;
        setError(
          err instanceof Error ? err.message : 'Failed to load highlights'
        );
      } finally {
        if (!isCancelled?.()) {
          setIsLoading(false);
        }
      }
    },
    [currentPdfId]
  );

  // Create a new highlight
  const createHighlight = useCallback(
    async (highlightData: HighlightRequest): Promise<Highlight | null> => {
      setError(null);

      try {
        const newHighlight =
          await highlightService.createHighlight(highlightData);

        // Add to local state immediately for instant feedback
        setHighlights(prev => [...prev, newHighlight]);

        return newHighlight;
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to create highlight'
        );
        console.error('Error creating highlight:', err);
        return null;
      }
    },
    []
  );

  // Delete a highlight
  const deleteHighlight = useCallback(
    async (highlightId: string): Promise<boolean> => {
      setError(null);

      try {
        const success = await highlightService.deleteHighlight(highlightId);

        if (success) {
          // Remove from local state immediately
          setHighlights(prev => prev.filter(h => h.id !== highlightId));
        }

        return success;
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to delete highlight'
        );
        console.error('Error deleting highlight:', err);
        return false;
      }
    },
    []
  );

  // Update highlight color
  const updateHighlightColor = useCallback(
    async (highlightId: string, color: string): Promise<boolean> => {
      setError(null);

      try {
        const success = await highlightService.updateHighlightColor(
          highlightId,
          color as any
        );

        if (success) {
          // Update local state immediately
          setHighlights(prev =>
            prev.map(h =>
              h.id === highlightId
                ? { ...h, color: color as any, updatedAt: new Date() }
                : h
            )
          );
        }

        return success;
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to update highlight color'
        );
        console.error('Error updating highlight color:', err);
        return false;
      }
    },
    []
  );

  // Get highlights for a specific page
  const getHighlightsForPage = useCallback(
    (pageNumber: number): Highlight[] => {
      return highlights.filter(h => h.pageNumber === pageNumber);
    },
    [highlights]
  );

  // Load highlights when the current PDF changes; cancel in-flight requests
  // so a stale response cannot overwrite a newer one.
  useEffect(() => {
    let cancelled = false;
    loadHighlights(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadHighlights]);

  const value: HighlightsContextType = {
    highlights,
    isLoading,
    error,
    currentPdfId,
    createHighlight,
    deleteHighlight,
    updateHighlightColor,
    refreshHighlights: loadHighlights,
    setCurrentPdfId,
    getHighlightsForPage,
  };

  return (
    <HighlightsContext.Provider value={value}>
      {children}
    </HighlightsContext.Provider>
  );
};
