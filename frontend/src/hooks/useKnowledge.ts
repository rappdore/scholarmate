import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { knowledgeService } from '../services/knowledgeApi';
import type {
  Concept,
  ExtractionResponse,
  ExtractionProgress,
  ExtractionStatusInfo,
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
  isLoading: boolean;
  isExtracting: boolean;
  error: string | null;
  extractionProgress: ExtractionProgress[];
  isSectionExtracted: boolean;
  // Real-time extraction status
  extractionStatus: ExtractionStatusInfo | null;
  loadConcepts: () => Promise<void>;
  extractConcepts: () => Promise<ExtractionResponse | null>;
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
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await knowledgeService.getConcepts(bookId, bookType, {
        nav_id: navId,
        page_num: pageNum,
      });
      setConcepts(data);
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
          await loadConcepts();
          await refreshExtractionProgress();

          // Keep status visible for a moment, then clear
          setTimeout(() => {
            setExtractionStatus(null);
          }, 2000);
        }
      } else {
        // No status found - extraction might have finished before we started polling
        // or was never started. Stop polling.
        if (pollingRef.current) {
          stopPolling();
          setIsExtracting(false);
        }
      }
    };

    // Poll immediately and then at intervals
    poll();
    pollIntervalRef.current = setInterval(poll, PROGRESS_POLL_INTERVAL);
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
    };
  }, [stopPolling]);

  // Check for ongoing extraction on mount/section change
  useEffect(() => {
    if (!bookId || !bookType || !sectionId) {
      return;
    }

    const checkForOngoingExtraction = async () => {
      const status = await pollExtractionStatus();
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
    isLoading,
    isExtracting,
    error,
    extractionProgress,
    isSectionExtracted,
    extractionStatus,
    loadConcepts,
    extractConcepts,
    cancelExtraction,
    refreshExtractionProgress,
    clearError,
  };
}
