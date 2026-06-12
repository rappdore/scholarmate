import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from 'react';
import type { HighlightColor } from '../types/highlights';

/**
 * The format-specific operations a highlights store needs. PDF and EPUB
 * highlights share their entire lifecycle (load on document change, optimistic
 * create/delete/recolor) and differ only in record shape, id type, and the
 * service calls — exactly what this interface captures.
 */
export interface HighlightsApi<H, Req, Id> {
  /** Used in error messages, e.g. 'highlight' or 'EPUB highlight'. */
  label: string;
  load: (documentId: number) => Promise<H[]>;
  create: (documentId: number, data: Req) => Promise<H>;
  remove: (id: Id) => Promise<boolean>;
  updateColor: (id: Id, color: HighlightColor) => Promise<boolean>;
  hasId: (highlight: H, id: Id) => boolean;
  withColor: (highlight: H, color: HighlightColor) => H;
}

export interface HighlightsStore<H, Req, Id> {
  highlights: H[];
  isLoading: boolean;
  error: string | null;
  currentDocumentId: number | null;
  createHighlight: (data: Req) => Promise<H | null>;
  deleteHighlight: (id: Id) => Promise<boolean>;
  updateHighlightColor: (id: Id, color: HighlightColor) => Promise<boolean>;
  refreshHighlights: () => Promise<void>;
  setCurrentDocumentId: (id: number | null) => void;
}

export function createHighlightsStore<H, Req, Id>(
  api: HighlightsApi<H, Req, Id>
) {
  const Context = createContext<HighlightsStore<H, Req, Id> | undefined>(
    undefined
  );

  function useStore(): HighlightsStore<H, Req, Id> {
    const context = useContext(Context);
    if (context === undefined) {
      throw new Error(
        `${api.label} store must be used within its corresponding provider`
      );
    }
    return context;
  }

  function errorMessage(err: unknown, action: string): string {
    return err instanceof Error
      ? err.message
      : `Failed to ${action} ${api.label}`;
  }

  const Provider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [highlights, setHighlights] = useState<H[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentDocumentId, setCurrentDocumentId] = useState<number | null>(
      null
    );

    // Load highlights for the current document.
    // `isCancelled` lets the loading effect drop stale responses (e.g. a slow
    // response for a previous document arriving after the user switched).
    const loadHighlights = useCallback(
      async (isCancelled?: () => boolean) => {
        // Use === null: 0 is a valid document id
        if (currentDocumentId === null) {
          setHighlights([]);
          return;
        }

        setIsLoading(true);
        setError(null);

        try {
          const loaded = await api.load(currentDocumentId);
          if (isCancelled?.()) return;
          setHighlights(loaded);
        } catch (err) {
          console.error(`Error loading ${api.label}s:`, err);
          if (isCancelled?.()) return;
          setError(errorMessage(err, 'load'));
        } finally {
          if (!isCancelled?.()) {
            setIsLoading(false);
          }
        }
      },
      [currentDocumentId]
    );

    const createHighlight = useCallback(
      async (data: Req): Promise<H | null> => {
        // Use === null: 0 is a valid document id
        if (currentDocumentId === null) {
          setError('No document selected');
          return null;
        }

        setError(null);

        try {
          const newHighlight = await api.create(currentDocumentId, data);

          // Add to local state immediately for instant feedback
          setHighlights(prev => [...prev, newHighlight]);

          return newHighlight;
        } catch (err) {
          setError(errorMessage(err, 'create'));
          console.error(`Error creating ${api.label}:`, err);
          return null;
        }
      },
      [currentDocumentId]
    );

    const deleteHighlight = useCallback(
      async (highlightId: Id): Promise<boolean> => {
        setError(null);

        try {
          const success = await api.remove(highlightId);

          if (success) {
            // Remove from local state immediately
            setHighlights(prev => prev.filter(h => !api.hasId(h, highlightId)));
          }

          return success;
        } catch (err) {
          setError(errorMessage(err, 'delete'));
          console.error(`Error deleting ${api.label}:`, err);
          return false;
        }
      },
      []
    );

    const updateHighlightColor = useCallback(
      async (highlightId: Id, color: HighlightColor): Promise<boolean> => {
        setError(null);

        try {
          const success = await api.updateColor(highlightId, color);

          if (success) {
            // Update local state immediately
            setHighlights(prev =>
              prev.map(h =>
                api.hasId(h, highlightId) ? api.withColor(h, color) : h
              )
            );
          }

          return success;
        } catch (err) {
          setError(errorMessage(err, 'update color of'));
          console.error(`Error updating ${api.label} color:`, err);
          return false;
        }
      },
      []
    );

    // Load highlights when the current document changes; cancel in-flight
    // requests so a stale response cannot overwrite a newer one.
    useEffect(() => {
      let cancelled = false;
      loadHighlights(() => cancelled);
      return () => {
        cancelled = true;
      };
    }, [loadHighlights]);

    const value: HighlightsStore<H, Req, Id> = {
      highlights,
      isLoading,
      error,
      currentDocumentId,
      createHighlight,
      deleteHighlight,
      updateHighlightColor,
      refreshHighlights: loadHighlights,
      setCurrentDocumentId,
    };

    return <Context.Provider value={value}>{children}</Context.Provider>;
  };

  return { Provider, useStore };
}
