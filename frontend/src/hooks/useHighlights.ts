import { useState, useEffect, useCallback } from 'react';
import { highlightService } from '../services/api';
import type { Highlight, HighlightRequest } from '../types/highlights';

interface UseHighlightsOptions {
  filename?: string;
  pageNumber?: number;
}

export function useHighlights({
  filename,
  pageNumber,
}: UseHighlightsOptions = {}) {
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load highlights for the current PDF/page
  const loadHighlights = useCallback(async () => {
    if (!filename) return;

    setIsLoading(true);
    setError(null);

    try {
      const loadedHighlights = await highlightService.getHighlightsForPdf(
        filename,
        pageNumber
      );
      setHighlights(loadedHighlights);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load highlights'
      );
      console.error('Error loading highlights:', err);
    } finally {
      setIsLoading(false);
    }
  }, [filename, pageNumber]);

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

  // Load highlights when filename or pageNumber changes
  useEffect(() => {
    loadHighlights();
  }, [loadHighlights]);

  return {
    highlights,
    isLoading,
    error,
    createHighlight,
    deleteHighlight,
    updateHighlightColor,
    refreshHighlights: loadHighlights,
  };
}
