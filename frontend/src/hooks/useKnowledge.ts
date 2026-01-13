import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { knowledgeService } from '../services/knowledgeApi';
import type {
  Concept,
  ExtractionResponse,
  ExtractionProgress,
  ExtractionStatusInfo,
  RelationshipExtractionResponse,
} from '../types/knowledge';

interface UseKnowledgeOptions {
  bookId?: number;
  bookType?: 'epub' | 'pdf';
  navId?: string;
  pageNum?: number;
  autoLoad?: boolean;
}

interface UseKnowledgeReturn {
  concepts: Concept[];
  relationshipCount: number;
  isLoading: boolean;
  isExtracting: boolean;
  error: string | null;
  extractionProgress: ExtractionProgress[];
  isSectionExtracted: boolean;
  // Real-time extraction status
  extractionStatus: ExtractionStatusInfo | null;
  loadConcepts: () => Promise<void>;
  extractConcepts: () => Promise<ExtractionResponse | null>;
  extractRelationships: () => Promise<RelationshipExtractionResponse | null>;
  cancelExtraction: () => Promise<boolean>;
  refreshExtractionProgress: () => Promise<void>;
  clearError: () => void;
}

// Poll interval in ms (3 seconds to reduce server load)
const PROGRESS_POLL_INTERVAL = 3000;

export function useKnowledge({
  bookId,
  bookType,
  navId,
  pageNum,
  autoLoad = true,
}: UseKnowledgeOptions): UseKnowledgeReturn {
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [relationshipCount, setRelationshipCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extractionProgress, setExtractionProgress] = useState<
    ExtractionProgress[]
  >([]);
  const [extractionStatus, setExtractionStatus] =
    useState<ExtractionStatusInfo | null>(null);

  // Ref to track if we should continue polling
  const pollingRef = useRef<boolean>(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Track when polling started to handle race condition with backend registration
  const pollingStartTimeRef = useRef<number>(0);
  // Track setTimeout IDs for cleanup on unmount
  const statusClearTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  // Grace period before giving up on finding extraction status (ms)
  // This accounts for time between API call start and backend registering the extraction
  const POLLING_GRACE_PERIOD_MS = 10000; // 10 seconds

  // Compute section ID for status queries
  const sectionId = useMemo(() => {
    if (bookType === 'epub' && navId) {
      return navId;
    }
    if (bookType === 'pdf' && pageNum !== undefined) {
      return `page_${pageNum}`;
    }
    return undefined;
  }, [bookType, navId, pageNum]);

  const isSectionExtracted = useMemo(() => {
    if (!bookId || !bookType) return false;
    if (bookType === 'epub' && navId) {
      return extractionProgress.some(p => p.nav_id === navId);
    }
    if (bookType === 'pdf' && pageNum !== undefined) {
      return extractionProgress.some(p => p.page_num === pageNum);
    }
    return false;
  }, [bookId, bookType, navId, pageNum, extractionProgress]);

  const loadConcepts = useCallback(async () => {
    if (!bookId || !bookType) {
      setConcepts([]);
      setRelationshipCount(0);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await knowledgeService.getConcepts(bookId, bookType, {
        nav_id: navId,
        page_num: pageNum,
      });
      setConcepts(data.concepts);
      setRelationshipCount(data.relationship_count);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load concepts';
      setError(message);
      console.error('Error loading concepts:', err);
    } finally {
      setIsLoading(false);
    }
  }, [bookId, bookType, navId, pageNum]);

  const refreshExtractionProgress = useCallback(async () => {
    if (!bookId || !bookType) {
      setExtractionProgress([]);
      return;
    }

    try {
      const progress = await knowledgeService.getExtractionProgress(
        bookId,
        bookType
      );
      setExtractionProgress(progress);
    } catch (err) {
      console.error('Error loading extraction progress:', err);
    }
  }, [bookId, bookType]);

  // Poll for extraction status - returns the status or null
  const pollExtractionStatus =
    useCallback(async (): Promise<ExtractionStatusInfo | null> => {
      if (!bookId || !bookType || !sectionId) {
        return null;
      }

      try {
        const response = await knowledgeService.getExtractionStatus({
          book_id: bookId,
          book_type: bookType,
          section_id: sectionId,
        });

        if (response.found && response.extraction) {
          return response.extraction;
        }
        return null;
      } catch (err) {
        console.error('Error polling extraction status:', err);
        return null;
      }
    }, [bookId, bookType, sectionId]);

  // Stop polling
  const stopPolling = useCallback(() => {
    pollingRef.current = false;
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  // Start polling for progress
  const startPolling = useCallback(() => {
    // Don't start if already polling
    if (pollingRef.current) {
      return;
    }

    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollingRef.current = true;
    pollingStartTimeRef.current = Date.now();

    const poll = async () => {
      if (!pollingRef.current) return;

      const status = await pollExtractionStatus();
      setExtractionStatus(status);

      // Check if extraction finished
      if (status) {
        if (
          status.status === 'completed' ||
          status.status === 'cancelled' ||
          status.status === 'failed'
        ) {
          // Stop polling and refresh data
          stopPolling();
          setIsExtracting(false);

          // Refresh concepts and progress after completion
          await Promise.all([loadConcepts(), refreshExtractionProgress()]);

          // Keep status visible for a moment, then clear
          // Track the timeout so it can be cleared on unmount
          statusClearTimeoutRef.current = setTimeout(() => {
            setExtractionStatus(null);
          }, 2000);
        }
      } else {
        // No status found - but don't give up immediately!
        // There's a race condition: the backend might not have registered
        // the extraction yet (it does setup before calling register_extraction).
        // Only stop polling after the grace period has elapsed.
        const elapsedMs = Date.now() - pollingStartTimeRef.current;
        if (elapsedMs > POLLING_GRACE_PERIOD_MS) {
          // Grace period exceeded - extraction either finished very quickly
          // or was never started. Stop polling.
          if (pollingRef.current) {
            stopPolling();
            setIsExtracting(false);
          }
        }
        // Otherwise, keep polling - the backend will register the extraction soon
      }
    };

    // Poll immediately and schedule next poll after completion
    // Using recursive setTimeout instead of setInterval to prevent overlapping
    // requests when API response takes longer than the poll interval
    const schedulePoll = async () => {
      if (!pollingRef.current) return;
      await poll();
      if (pollingRef.current) {
        pollIntervalRef.current = setTimeout(
          schedulePoll,
          PROGRESS_POLL_INTERVAL
        );
      }
    };
    schedulePoll();
  }, [
    pollExtractionStatus,
    loadConcepts,
    refreshExtractionProgress,
    stopPolling,
  ]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling();
      // Clear any pending status clear timeout to prevent state update after unmount
      if (statusClearTimeoutRef.current) {
        clearTimeout(statusClearTimeoutRef.current);
        statusClearTimeoutRef.current = null;
      }
    };
  }, [stopPolling]);

  // Check for ongoing extraction on mount/section change
  useEffect(() => {
    if (!bookId || !bookType || !sectionId) {
      return;
    }

    let cancelled = false;

    const checkForOngoingExtraction = async () => {
      const status = await pollExtractionStatus();
      if (cancelled) return;
      if (
        status &&
        (status.status === 'running' || status.status === 'cancelling')
      ) {
        // There's an ongoing extraction - show it and start polling
        setExtractionStatus(status);
        setIsExtracting(true);
        startPolling();
      }
    };

    checkForOngoingExtraction();

    return () => {
      cancelled = true;
    };
  }, [bookId, bookType, sectionId, pollExtractionStatus, startPolling]);

  const extractConcepts =
    useCallback(async (): Promise<ExtractionResponse | null> => {
      if (!bookId || !bookType) {
        setError('No book selected');
        return null;
      }

      if (bookType === 'epub' && !navId) {
        setError('No section selected for EPUB');
        return null;
      }
      if (bookType === 'pdf' && pageNum === undefined) {
        setError('No page selected for PDF');
        return null;
      }

      setIsExtracting(true);
      setError(null);
      setExtractionStatus(null);

      // Start polling for progress
      startPolling();

      try {
        // Note: This API call blocks until extraction completes (or errors)
        const result = await knowledgeService.extractSection({
          book_id: bookId,
          book_type: bookType,
          nav_id: navId,
          page_num: pageNum,
        });

        // Extraction finished - stop polling and update state
        stopPolling();
        setIsExtracting(false);
        setExtractionStatus(null);

        // Refresh data
        await loadConcepts();
        await refreshExtractionProgress();

        return result;
      } catch (err) {
        // Error occurred - stop polling and update state
        stopPolling();
        setIsExtracting(false);
        setExtractionStatus(null);

        const message =
          err instanceof Error ? err.message : 'Extraction failed';
        setError(message);
        console.error('Error extracting concepts:', err);
        return null;
      }
    }, [
      bookId,
      bookType,
      navId,
      pageNum,
      loadConcepts,
      refreshExtractionProgress,
      startPolling,
      stopPolling,
    ]);

  const extractRelationships =
    useCallback(async (): Promise<RelationshipExtractionResponse | null> => {
      if (!bookId || !bookType) {
        setError('No book selected');
        return null;
      }

      if (bookType === 'epub' && !navId) {
        setError('No section selected for EPUB');
        return null;
      }
      if (bookType === 'pdf' && pageNum === undefined) {
        setError('No page selected for PDF');
        return null;
      }

      setIsExtracting(true);
      setError(null);
      setExtractionStatus(null);

      // Start polling for progress
      startPolling();

      try {
        const result = await knowledgeService.extractRelationships({
          book_id: bookId,
          book_type: bookType,
          nav_id: navId,
          page_num: pageNum,
          force: false, // Resume from where we left off if there's prior progress
        });

        // Extraction finished - stop polling and update state
        stopPolling();
        setIsExtracting(false);
        setExtractionStatus(null);

        // Refresh data (relationships affect the graph)
        await loadConcepts();

        return result;
      } catch (err) {
        // Error occurred - stop polling and update state
        stopPolling();
        setIsExtracting(false);
        setExtractionStatus(null);

        const message =
          err instanceof Error ? err.message : 'Relationship extraction failed';
        setError(message);
        console.error('Error extracting relationships:', err);
        return null;
      }
    }, [
      bookId,
      bookType,
      navId,
      pageNum,
      loadConcepts,
      startPolling,
      stopPolling,
    ]);

  const cancelExtraction = useCallback(async (): Promise<boolean> => {
    if (!bookId || !bookType || !sectionId) {
      setError('No extraction to cancel');
      return false;
    }

    try {
      const result = await knowledgeService.cancelExtraction(
        bookId,
        bookType,
        sectionId
      );

      if (result.success) {
        // Cancellation requested - polling will pick up the status change
        console.log('Cancellation requested:', result.message);
        return true;
      } else {
        setError(result.message);
        return false;
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to cancel extraction';
      setError(message);
      console.error('Error cancelling extraction:', err);
      return false;
    }
  }, [bookId, bookType, sectionId]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  useEffect(() => {
    if (autoLoad && bookId && bookType) {
      loadConcepts();
      refreshExtractionProgress();
    }
  }, [
    autoLoad,
    bookId,
    bookType,
    navId,
    pageNum,
    loadConcepts,
    refreshExtractionProgress,
  ]);

  return {
    concepts,
    relationshipCount,
    isLoading,
    isExtracting,
    error,
    extractionProgress,
    isSectionExtracted,
    extractionStatus,
    loadConcepts,
    extractConcepts,
    extractRelationships,
    cancelExtraction,
    refreshExtractionProgress,
    clearError,
  };
}
