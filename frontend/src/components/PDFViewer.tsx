import { useState, useCallback, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import type {
  TextSelection,
  HighlightCoordinates,
  HighlightColor,
} from '../types/highlights';
import HighlightOverlay from './HighlightOverlay';
import { useHighlights } from '../hooks/useHighlights';

// Set up the worker for react-pdf v9
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFViewerProps {
  filename?: string;
  currentPage: number;
  onPageChange: (page: number) => void;
  onTotalPagesChange?: (totalPages: number) => void;
  onTextSelection?: (selection: TextSelection, color: HighlightColor) => void;
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

export default function PDFViewer({
  filename,
  currentPage,
  onPageChange,
  onTotalPagesChange,
  onTextSelection,
}: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scale, setScale] = useState<number>(getSavedZoom()); // Initialize directly from localStorage

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

  const pdfContainerRef = useRef<HTMLDivElement>(null);

  // Highlight management
  const { highlights, createHighlight, deleteHighlight } = useHighlights({
    filename,
    pageNumber: currentPage,
  });

  // Save zoom level to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem('pdf-viewer-zoom', scale.toString());
    } catch (error) {
      console.warn('Error saving zoom to localStorage:', error);
    }
  }, [scale]);

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
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const goToNextPage = () => {
    if (currentPage < numPages) {
      onPageChange(currentPage + 1);
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

    // Get the text layer element
    const textLayer = pdfContainerRef.current?.querySelector(
      '.react-pdf__Page__textContent'
    );
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
        pageNumber: currentPage,
      };
    } catch (error) {
      console.error('Error processing text selection:', error);
      return null;
    }
  }, [currentPage]);

  const calculateSelectionCoordinates = (
    range: Range,
    textLayer: HTMLElement
  ): HighlightCoordinates[] => {
    const rects = range.getClientRects();
    const textLayerRect = textLayer.getBoundingClientRect();
    const coordinates: HighlightCoordinates[] = [];

    // Get page dimensions for normalization
    const pageElement = textLayer.closest('.react-pdf__Page');
    const pageRect = pageElement?.getBoundingClientRect();

    if (!pageRect) {
      throw new Error('Could not find page element');
    }

    for (let i = 0; i < rects.length; i++) {
      const rect = rects[i];

      // Convert to coordinates relative to the page
      const x = rect.left - pageRect.left;
      const y = rect.top - pageRect.top;

      coordinates.push({
        x,
        y,
        width: rect.width,
        height: rect.height,
        pageWidth: pageRect.width,
        pageHeight: pageRect.height,
        zoom: scale,
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
        // Also call the parent callback if provided
        onTextSelection?.(contextMenu.selection, color);
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
    }
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
              {loading ? '...' : `${currentPage} of ${numPages}`}
            </span>
            <button
              onClick={goToNextPage}
              disabled={currentPage >= numPages}
              className="px-3 py-1 bg-blue-600 text-white rounded disabled:bg-gray-500 disabled:text-gray-400 disabled:cursor-not-allowed hover:bg-blue-500 transition-colors"
            >
              Next
            </button>

            {/* Debug: Show highlight count */}
            {highlights.length > 0 && (
              <span className="text-xs text-green-400 ml-2">
                {highlights.filter(h => h.pageNumber === currentPage).length}{' '}
                highlights
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
            <div className="relative">
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
                <Page
                  pageNumber={currentPage}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  className="shadow-lg"
                  scale={scale}
                />
              </Document>

              {/* Highlight Overlay */}
              <HighlightOverlay
                highlights={highlights}
                pageNumber={currentPage}
                scale={scale}
                onHighlightDelete={handleHighlightDelete}
              />
            </div>

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
