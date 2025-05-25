import { useState, useCallback, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

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
          </div>
        </div>
      </div>

      {/* PDF Content */}
      <div className="flex-1 overflow-auto bg-gray-800">
        {error ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <p className="text-red-400 mb-2">Error loading PDF</p>
              <p className="text-sm text-gray-400">{error}</p>
            </div>
          </div>
        ) : (
          <div className="flex justify-center p-4">
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
          </div>
        )}
      </div>
    </div>
  );
}
