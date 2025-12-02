import { useState, useCallback, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import type {
  TextSelection,
  HighlightCoordinates,
  HighlightColor,
  Highlight,
} from '../types/highlights';
import HighlightOverlay from './HighlightOverlay';
import { useHighlightsContext } from '../contexts/HighlightsContext';

// Set up the worker for react-pdf v9
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFViewerProps {
  filename?: string;
  currentPage: number;
  onPageChange: (page: number) => void;
  onTotalPagesChange?: (totalPages: number) => void;
}

// Helper function to get saved zoom or default
const getSavedZoom = (): number => {
  try {
    const savedZoom = localStorage.getItem('pdf-viewer-zoom');
    if (savedZoom) {
      const zoomValue = parseFloat(savedZoom);
      if (zoomValue >= 0.5 && zoomValue <= 3.0) {
        return zoomValue;
      }
    }
  } catch (error) {
    console.warn('Error reading zoom from localStorage:', error);
  }
  return 1.0; // Default 100% zoom
};

// Helper function to get saved view mode or default
const getSavedViewMode = (): 'single' | 'double' => {
  try {
    const savedViewMode = localStorage.getItem('pdf-viewer-view-mode');
    if (savedViewMode === 'double' || savedViewMode === 'single') {
      return savedViewMode;
    }
  } catch (error) {
    console.warn('Error reading view mode from localStorage:', error);
  }
  return 'single'; // Default single page view
};

export default function PDFViewer({
  filename,
  currentPage,
  onPageChange,
  onTotalPagesChange,
}: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scale, setScale] = useState<number>(getSavedZoom()); // Initialize directly from localStorage
  const [viewMode, setViewMode] = useState<'single' | 'double'>(
    getSavedViewMode()
  ); // Add view mode state

  // Page turn timing state
  const [pageTurnTime, setPageTurnTime] = useState<number | null>(null); // Time in seconds
  const [lastPageTurnTime, setLastPageTurnTime] = useState<number | null>(null); // Previous turn time for comparison
  const [isFaster, setIsFaster] = useState<boolean | null>(null); // true = green, false = red, null = first turn
  const lastPageRef = useRef<number | null>(null); // null means not initialized yet
  const pageStartTimeRef = useRef<number>(Date.now());

  // Average page time state
  const [averagePageTime, setAveragePageTime] = useState<number>(0);
  const [numTimeSamples, setNumTimeSamples] = useState<number>(0);

  // Session page counter state
  const [sessionPagesRead, setSessionPagesRead] = useState<number>(0);

  // Session ID state - generated once per reading session
  const [sessionId, setSessionId] = useState<string>('');

  // Generate session ID on mount or when filename changes
  useEffect(() => {
    // Generate a new session ID when a PDF is opened
    const generateSessionId = () => {
      return crypto.randomUUID();
    };

    if (filename && !sessionId) {
      // Generate new session ID if we don't have one
      setSessionId(generateSessionId());
    } else if (!filename) {
      // Clear session ID when no file is selected (returned to library)
      setSessionId('');
    }
  }, [filename]); // Only depend on filename

  // Text selection state
  const [contextMenu, setContextMenu] = useState<{
    visible: boolean;
    x: number;
    y: number;
    selection: TextSelection | null;
  }>({
    visible: false,
    x: 0,
    y: 0,
    selection: null,
  });

  // Selected highlight state for keyboard shortcuts
  const [selectedHighlight, setSelectedHighlight] = useState<Highlight | null>(
    null
  );

  const pdfContainerRef = useRef<HTMLDivElement>(null);

  // Highlight management - Use shared context
  const {
    highlights,
    createHighlight,
    deleteHighlight,
    setCurrentFilename,
    getHighlightsForPage,
  } = useHighlightsContext();

  // Set current filename when it changes
  useEffect(() => {
    setCurrentFilename(filename || null);
  }, [filename, setCurrentFilename]);

  // Save zoom level to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem('pdf-viewer-zoom', scale.toString());
    } catch (error) {
      console.warn('Error saving zoom to localStorage:', error);
    }
  }, [scale]);

  // Save view mode to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem('pdf-viewer-view-mode', viewMode);
    } catch (error) {
      console.warn('Error saving view mode to localStorage:', error);
    }
  }, [viewMode]);

  // Track page turn timing and session page count
  useEffect(() => {
    const previousPage = lastPageRef.current;

    // Skip tracking if this is the first render (previousPage is null)
    if (previousPage === null) {
      lastPageRef.current = currentPage;
      return;
    }

    if (currentPage > previousPage) {
      // Forward navigation - record time and increment counter
      const elapsedSeconds = (Date.now() - pageStartTimeRef.current) / 1000;
      setPageTurnTime(elapsedSeconds);

      // Update average
      // (n * current average + current page)/( n + 1)
      const newAverage =
        (numTimeSamples * averagePageTime + elapsedSeconds) /
        (numTimeSamples + 1);
      setAveragePageTime(newAverage);
      setNumTimeSamples(prev => prev + 1);

      // Compare with last turn time
      if (lastPageTurnTime === null) {
        // First page turn - show green
        setIsFaster(true);
      } else {
        setIsFaster(elapsedSeconds < lastPageTurnTime);
      }

      setLastPageTurnTime(elapsedSeconds);
      pageStartTimeRef.current = Date.now();

      // Increment session page counter
      const newPagesRead = sessionPagesRead + 1;
      setSessionPagesRead(newPagesRead);

      // Send reading session data to backend
      if (sessionId && filename) {
        fetch('/api/reading-statistics/session/update', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            pdf_filename: filename,
            pages_read: newPagesRead,
            average_time_per_page: newAverage,
          }),
        }).catch(error => {
          console.error('Failed to update reading statistics:', error);
          // Don't block the UI on statistics update failures
        });
      }
    } else if (currentPage < previousPage) {
      // Backward navigation - reset timer and blank out display
      setPageTurnTime(null);
      setIsFaster(null);
      pageStartTimeRef.current = Date.now();

      // Decrement session page counter
      setSessionPagesRead(prev => prev - 1);
    }

    lastPageRef.current = currentPage;
  }, [currentPage, lastPageTurnTime, averagePageTime, numTimeSamples]);

  // Reset timer and session counter when document changes
  useEffect(() => {
    setPageTurnTime(null);
    setLastPageTurnTime(null);
    setIsFaster(null);
    setSessionPagesRead(0);
    setAveragePageTime(0);
    setNumTimeSamples(0);
    pageStartTimeRef.current = Date.now();
    lastPageRef.current = null; // Reset to null so first page change is ignored
  }, [filename]); // Only reset when filename changes

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Delete key - delete selected highlight
      if (event.key === 'Delete' && selectedHighlight) {
        event.preventDefault();
        handleHighlightDelete(selectedHighlight.id);
        setSelectedHighlight(null);
      }

      // Escape key - clear selection and context menu
      if (event.key === 'Escape') {
        setSelectedHighlight(null);
        setContextMenu(prev => ({ ...prev, visible: false }));
        window.getSelection()?.removeAllRanges();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedHighlight]);

  const onDocumentLoadSuccess = useCallback(
    ({ numPages }: { numPages: number }) => {
      setNumPages(numPages);
      setLoading(false);
      setError(null);
      onTotalPagesChange?.(numPages);
    },
    [onTotalPagesChange]
  );

  const onDocumentLoadError = useCallback((error: Error) => {
    setError(`Failed to load PDF: ${error.message}`);
    setLoading(false);
  }, []);

  const goToPrevPage = () => {
    if (viewMode === 'double') {
      // In double page mode, go back by 2 pages, but ensure we don't go below 1
      const newPage = Math.max(1, currentPage - 2);
      onPageChange(newPage);
    } else {
      // Single page mode
      if (currentPage > 1) {
        onPageChange(currentPage - 1);
      }
    }
  };

  const goToNextPage = () => {
    if (viewMode === 'double') {
      // In double page mode, go forward by 2 pages, but ensure we don't exceed numPages
      const newPage = Math.min(numPages, currentPage + 2);
      onPageChange(newPage);
    } else {
      // Single page mode
      if (currentPage < numPages) {
        onPageChange(currentPage + 1);
      }
    }
  };

  const zoomIn = () => {
    setScale(prev => Math.min(prev + 0.2, 3.0)); // Max zoom 3x
  };

  const zoomOut = () => {
    setScale(prev => Math.max(prev - 0.2, 0.5)); // Min zoom 0.5x
  };

  const resetZoom = () => {
    setScale(1.0);
  };

  // Format time in minutes:seconds
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Toggle view mode
  const toggleViewMode = () => {
    setViewMode(prev => (prev === 'single' ? 'double' : 'single'));
  };

  // Helper function to get pages to display
  const getPagesToDisplay = (): number[] => {
    if (viewMode === 'single') {
      return [currentPage];
    } else {
      // Double page mode
      const pages = [currentPage];
      if (currentPage + 1 <= numPages) {
        pages.push(currentPage + 1);
      }
      return pages;
    }
  };

  // Text selection and coordinate mapping functions
  const getTextSelection = useCallback((): TextSelection | null => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.rangeCount) {
      return null;
    }

    const range = selection.getRangeAt(0);
    const selectedText = selection.toString().trim();

    if (!selectedText) {
      return null;
    }

    // In double page mode, we need to determine which page the selection is on
    let selectedPageNumber = currentPage;
    let textLayer: HTMLElement | null = null;

    if (viewMode === 'double') {
      // Find which page the selection belongs to
      const startContainer = range.startContainer;
      const pageElement = (
        startContainer.nodeType === Node.TEXT_NODE
          ? startContainer.parentElement
          : (startContainer as HTMLElement)
      )?.closest('.react-pdf__Page');

      if (pageElement) {
        // Check if this is the first or second page in double view
        const allPages =
          pdfContainerRef.current?.querySelectorAll('.react-pdf__Page');
        if (allPages) {
          const pageIndex = Array.from(allPages).indexOf(pageElement);
          selectedPageNumber = currentPage + (pageIndex % 2);
        }

        const foundTextLayer = pageElement.querySelector(
          '.react-pdf__Page__textContent'
        );
        textLayer = foundTextLayer as HTMLElement | null;
      }
    } else {
      // Single page mode - use the current page
      const foundTextLayer = pdfContainerRef.current?.querySelector(
        '.react-pdf__Page__textContent'
      );
      textLayer = foundTextLayer as HTMLElement | null;
    }

    if (!textLayer) {
      console.warn('Text layer not found');
      return null;
    }

    try {
      // Calculate coordinates relative to the PDF page
      const coordinates = calculateSelectionCoordinates(
        range,
        textLayer as HTMLElement
      );

      // Calculate text offsets (simplified for now)
      const { startOffset, endOffset } = calculateTextOffsets(
        range,
        textLayer as HTMLElement
      );

      return {
        text: selectedText,
        startOffset,
        endOffset,
        coordinates,
        pageNumber: selectedPageNumber,
      };
    } catch (error) {
      console.error('Error processing text selection:', error);
      return null;
    }
  }, [currentPage, viewMode]);

  const calculateSelectionCoordinates = (
    range: Range,
    textLayer: HTMLElement
  ): HighlightCoordinates[] => {
    const rects = range.getClientRects();
    const coordinates: HighlightCoordinates[] = [];

    // Get page dimensions for normalization
    const pageElement = textLayer.closest('.react-pdf__Page');
    const pageRect = pageElement?.getBoundingClientRect();

    if (!pageRect) {
      throw new Error('Could not find page element');
    }

    // In double page mode, we need to ensure coordinates are relative to the individual page
    // The pageRect already gives us the correct page boundaries regardless of view mode

    for (let i = 0; i < rects.length; i++) {
      const rect = rects[i];

      // Convert to coordinates relative to the specific page (not viewport)
      const x = rect.left - pageRect.left;
      const y = rect.top - pageRect.top;

      coordinates.push({
        x,
        y,
        width: rect.width,
        height: rect.height,
        pageWidth: pageRect.width,
        pageHeight: pageRect.height,
        zoom: viewMode === 'double' ? scale * 0.8 : scale, // Store the actual scale used for rendering
      });
    }

    return coordinates;
  };

  const calculateTextOffsets = (
    range: Range,
    textLayer: HTMLElement
  ): { startOffset: number; endOffset: number } => {
    // Simplified offset calculation - in a real implementation, this would be more sophisticated
    // For now, we'll use the range's start and end offsets within the container
    const textContent = textLayer.textContent || '';
    const selectedText = range.toString();

    // Find the position of the selected text in the full page text
    const startOffset = textContent.indexOf(selectedText);
    const endOffset = startOffset + selectedText.length;

    return {
      startOffset: Math.max(0, startOffset),
      endOffset: Math.max(0, endOffset),
    };
  };

  // Handle text selection events
  const handleMouseUp = useCallback(
    (event: MouseEvent) => {
      // Small delay to ensure selection is complete
      setTimeout(() => {
        const selection = getTextSelection();
        if (selection && selection.text.length > 0) {
          // Show context menu at mouse position
          setContextMenu({
            visible: true,
            x: event.clientX,
            y: event.clientY,
            selection,
          });
        } else {
          // Hide context menu if no selection
          setContextMenu(prev => ({ ...prev, visible: false }));
        }
      }, 10);
    },
    [getTextSelection]
  );

  // Handle clicks outside to hide context menu
  const handleDocumentClick = useCallback((event: MouseEvent) => {
    const target = event.target as HTMLElement;

    // Don't hide if clicking on the context menu itself
    if (target.closest('.highlight-context-menu')) {
      return;
    }

    // Hide context menu
    setContextMenu(prev => ({ ...prev, visible: false }));
  }, []);

  // Set up event listeners
  useEffect(() => {
    const container = pdfContainerRef.current;
    if (!container) return;

    container.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('click', handleDocumentClick);

    return () => {
      container.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('click', handleDocumentClick);
    };
  }, [handleMouseUp, handleDocumentClick]);

  // Handle highlight creation
  const handleCreateHighlight = async (color: HighlightColor) => {
    if (contextMenu.selection && filename) {
      // Create highlight using our hook
      const highlightData = {
        pdfFilename: filename,
        pageNumber: contextMenu.selection.pageNumber,
        selectedText: contextMenu.selection.text,
        startOffset: contextMenu.selection.startOffset,
        endOffset: contextMenu.selection.endOffset,
        color: color,
        coordinates: contextMenu.selection.coordinates,
      };

      const newHighlight = await createHighlight(highlightData);

      if (newHighlight) {
        console.log('Highlight created:', newHighlight);
        // Note: Removed onTextSelection callback to prevent duplicate highlight creation
        // The highlight is now handled entirely by the useHighlights hook
      }
    }

    setContextMenu(prev => ({ ...prev, visible: false }));

    // Clear the text selection
    window.getSelection()?.removeAllRanges();
  };

  // Handle highlight deletion
  const handleHighlightDelete = async (highlightId: string) => {
    const success = await deleteHighlight(highlightId);
    if (success) {
      console.log('Highlight deleted:', highlightId);
      // Clear selection if the deleted highlight was selected
      if (selectedHighlight?.id === highlightId) {
        setSelectedHighlight(null);
      }
    }
  };

  // Handle highlight click (for selection)
  const handleHighlightClick = (highlight: Highlight) => {
    setSelectedHighlight(highlight);
    console.log('Highlight selected:', highlight.id);
  };

  if (!filename) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <p className="text-gray-400">No PDF selected</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header with navigation */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-3 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-100 truncate">
          {filename}
        </h1>
        <div className="flex items-center gap-4">
          {/* Session ID display (for debugging) */}
          {sessionId && (
            <div className="flex items-center">
              <span className="text-xs font-mono text-gray-500">
                Session: {sessionId.substring(0, 8)}...
              </span>
            </div>
          )}

          {/* Session pages read counter */}
          <div className="flex items-center">
            <span
              className={`text-sm font-mono ${
                sessionPagesRead >= 0 ? 'text-green-400' : 'text-red-400'
              }`}
            >
              Pages: {sessionPagesRead}
            </span>
          </div>

          {/* Average page time display */}
          {averagePageTime > 0 && (
            <div className="flex items-center">
              <span className="text-sm font-mono text-blue-400">
                Avg: {formatTime(averagePageTime)}
              </span>
            </div>
          )}

          {/* Page turn time display */}
          {pageTurnTime !== null && (
            <div className="flex items-center">
              <span
                className={`text-sm font-mono ${
                  isFaster ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {formatTime(pageTurnTime)}
              </span>
            </div>
          )}

          {/* View mode toggle */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggleViewMode}
              className={`px-3 py-1 rounded transition-colors ${
                viewMode === 'single'
                  ? 'bg-blue-600 text-white hover:bg-blue-500'
                  : 'bg-gray-600 text-gray-200 hover:bg-gray-500'
              }`}
              title="Single page view"
            >
              Single
            </button>
            <button
              onClick={toggleViewMode}
              className={`px-3 py-1 rounded transition-colors ${
                viewMode === 'double'
                  ? 'bg-blue-600 text-white hover:bg-blue-500'
                  : 'bg-gray-600 text-gray-200 hover:bg-gray-500'
              }`}
              title="Double page view"
            >
              Double
            </button>
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={zoomOut}
              disabled={scale <= 0.5}
              className="px-3 py-1 bg-gray-600 text-gray-200 rounded disabled:bg-gray-500 disabled:text-gray-400 disabled:cursor-not-allowed hover:bg-gray-500 transition-colors"
            >
              Zoom Out
            </button>
            <span className="text-sm text-gray-300 min-w-16 text-center">
              {Math.round(scale * 100)}%
            </span>
            <button
              onClick={zoomIn}
              disabled={scale >= 3.0}
              className="px-3 py-1 bg-gray-600 text-gray-200 rounded disabled:bg-gray-500 disabled:text-gray-400 disabled:cursor-not-allowed hover:bg-gray-500 transition-colors"
            >
              Zoom In
            </button>
            <button
              onClick={resetZoom}
              className="px-3 py-1 bg-gray-700 text-gray-200 rounded hover:bg-gray-600 transition-colors"
            >
              Reset
            </button>
          </div>

          {/* Page navigation */}
          <div className="flex items-center gap-2">
            <button
              onClick={goToPrevPage}
              disabled={currentPage <= 1}
              className="px-3 py-1 bg-blue-600 text-white rounded disabled:bg-gray-500 disabled:text-gray-400 disabled:cursor-not-allowed hover:bg-blue-500 transition-colors"
            >
              Previous
            </button>
            <span className="text-sm text-gray-300">
              {loading
                ? '...'
                : viewMode === 'double' && currentPage + 1 <= numPages
                  ? `${currentPage}-${currentPage + 1} of ${numPages}`
                  : `${currentPage} of ${numPages}`}
            </span>
            <button
              onClick={goToNextPage}
              disabled={
                viewMode === 'double'
                  ? currentPage + 1 >= numPages
                  : currentPage >= numPages
              }
              className="px-3 py-1 bg-blue-600 text-white rounded disabled:bg-gray-500 disabled:text-gray-400 disabled:cursor-not-allowed hover:bg-blue-500 transition-colors"
            >
              Next
            </button>

            {/* Debug: Show highlight count and selection status */}
            {highlights.length > 0 && (
              <span className="text-xs text-green-400 ml-2">
                {viewMode === 'double'
                  ? getHighlightsForPage(currentPage).length +
                    getHighlightsForPage(currentPage + 1).length
                  : getHighlightsForPage(currentPage).length}{' '}
                highlights
              </span>
            )}
            {selectedHighlight && (
              <span className="text-xs text-blue-400 ml-2 px-2 py-1 bg-blue-900 rounded">
                Selected: "{selectedHighlight.selectedText.substring(0, 20)}..."
                (Press Delete to remove)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* PDF Content */}
      <div className="flex-1 overflow-auto bg-gray-800" ref={pdfContainerRef}>
        {error ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <p className="text-red-400 mb-2">Error loading PDF</p>
              <p className="text-sm text-gray-400">{error}</p>
            </div>
          </div>
        ) : (
          <div className="flex justify-center p-4 relative">
            <Document
              file={`/api/pdf/${filename}/file`}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading={
                <div className="flex items-center justify-center h-96">
                  <div className="text-gray-400">Loading PDF...</div>
                </div>
              }
            >
              <div
                className={`${viewMode === 'double' ? 'flex gap-4 items-start' : ''}`}
              >
                {getPagesToDisplay().map(pageNum => (
                  <div key={pageNum} className="relative">
                    <Page
                      pageNumber={pageNum}
                      renderTextLayer={true}
                      renderAnnotationLayer={true}
                      className="shadow-lg"
                      scale={viewMode === 'double' ? scale * 0.8 : scale} // Slightly smaller scale for double page view
                    />

                    {/* Highlight Overlay for each page */}
                    <HighlightOverlay
                      highlights={getHighlightsForPage(pageNum)}
                      pageNumber={pageNum}
                      scale={viewMode === 'double' ? scale * 0.8 : scale}
                      selectedHighlightId={selectedHighlight?.id}
                      onHighlightClick={handleHighlightClick}
                      onHighlightDelete={handleHighlightDelete}
                    />
                  </div>
                ))}
              </div>
            </Document>

            {/* Context Menu for Text Selection */}
            {contextMenu.visible && contextMenu.selection && (
              <div
                className="highlight-context-menu fixed z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl p-3"
                style={{
                  left: `${contextMenu.x}px`,
                  top: `${contextMenu.y}px`,
                  transform: 'translate(-50%, -100%)',
                }}
              >
                <div className="mb-2">
                  <p className="text-xs text-gray-400 mb-2">Create Highlight</p>
                  <p className="text-sm text-gray-200 max-w-xs truncate">
                    "{contextMenu.selection.text}"
                  </p>
                </div>

                <div className="flex gap-2 flex-wrap">
                  {Object.entries({
                    Yellow: '#ffff00',
                    Green: '#00ff00',
                    Blue: '#0080ff',
                    Pink: '#ff69b4',
                    Orange: '#ffa500',
                    Purple: '#9370db',
                    Red: '#ff4444',
                    Cyan: '#00ffff',
                  }).map(([name, color]) => (
                    <button
                      key={name}
                      onClick={() =>
                        handleCreateHighlight(color as HighlightColor)
                      }
                      className="w-6 h-6 rounded border-2 border-gray-600 hover:border-gray-400 transition-colors"
                      style={{ backgroundColor: color }}
                      title={`Highlight in ${name}`}
                    />
                  ))}
                </div>

                <button
                  onClick={() =>
                    setContextMenu(prev => ({ ...prev, visible: false }))
                  }
                  className="mt-2 w-full text-xs text-gray-400 hover:text-gray-200 transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
