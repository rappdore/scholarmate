import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PDFViewer from '../components/PDFViewer';
import EPUBViewer from '../components/EPUBViewer';
import TabbedRightPanel from '../components/TabbedRightPanel';
import SimpleResizablePanels from '../components/SimpleResizablePanels';
import { pdfService } from '../services/api';
import { epubService } from '../services/epubService';
import type { DocumentType } from '../types/document';

export default function Reader() {
  const { filename } = useParams<{ filename: string }>();
  const navigate = useNavigate();
  const [currentPage, setCurrentPage] = useState(1);
  const [currentNavId, setCurrentNavId] = useState<string | undefined>(
    undefined
  );
  const [currentChapterId, setCurrentChapterId] = useState<string | undefined>(
    undefined
  );
  const [currentChapterTitle, setCurrentChapterTitle] = useState<
    string | undefined
  >(undefined);
  const [totalPages, setTotalPages] = useState<number | null>(null);
  const [isProgressLoaded, setIsProgressLoaded] = useState(false);
  const [documentType, setDocumentType] = useState<DocumentType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detect document type on component mount
  useEffect(() => {
    if (!filename) return;

    const detectDocumentType = async () => {
      try {
        setLoading(true);
        setError(null);

        // Try to get PDF info first
        try {
          await pdfService.getPDFInfo(filename);
          setDocumentType('pdf');
        } catch (pdfError) {
          // If PDF fails, try EPUB
          try {
            await epubService.getEPUBInfo(filename);
            setDocumentType('epub');
          } catch (epubError) {
            throw new Error('Document not found or unsupported format');
          }
        }
      } catch (err) {
        console.error('Error detecting document type:', err);
        setError('Document not found or unsupported format');
      } finally {
        setLoading(false);
      }
    };

    detectDocumentType();
  }, [filename]);

  // Load reading progress on component mount (for PDFs only for now)
  useEffect(() => {
    if (!filename || documentType !== 'pdf') return;

    const loadReadingProgress = async () => {
      try {
        const progress = await pdfService.getReadingProgress(filename);
        if (progress.last_page && progress.last_page > 1) {
          setCurrentPage(progress.last_page);
        }
        if (progress.total_pages) {
          setTotalPages(progress.total_pages);
        }
      } catch (error) {
        console.error('Error loading reading progress:', error);
      } finally {
        setIsProgressLoaded(true);
      }
    };

    loadReadingProgress();
  }, [filename, documentType]);

  // Save reading progress when page changes (for PDFs only for now)
  useEffect(() => {
    if (!filename || !isProgressLoaded || !totalPages || documentType !== 'pdf')
      return;

    const saveProgress = async () => {
      try {
        await pdfService.saveReadingProgress(filename, currentPage, totalPages);
      } catch (error) {
        console.error('Error saving reading progress:', error);
      }
    };

    // Debounce saving to avoid too many requests
    const timeoutId = setTimeout(saveProgress, 1000);
    return () => clearTimeout(timeoutId);
  }, [filename, currentPage, totalPages, isProgressLoaded, documentType]);

  // Keyboard navigation for PDF pages
  useEffect(() => {
    if (documentType !== 'pdf') return;

    const handleKeyDown = (event: KeyboardEvent) => {
      // Only handle arrow keys if no input/textarea is focused
      const activeElement = document.activeElement;
      const isInputFocused =
        activeElement?.tagName === 'INPUT' ||
        activeElement?.tagName === 'TEXTAREA' ||
        activeElement?.getAttribute('contenteditable') === 'true';

      if (isInputFocused) return;

      switch (event.key) {
        case 'ArrowLeft':
          event.preventDefault();
          if (currentPage > 1) {
            setCurrentPage(prev => prev - 1);
          }
          break;
        case 'ArrowRight':
          event.preventDefault();
          if (totalPages && currentPage < totalPages) {
            setCurrentPage(prev => prev + 1);
          }
          break;
      }
    };

    // Add event listener
    document.addEventListener('keydown', handleKeyDown);

    // Cleanup
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [currentPage, totalPages, documentType]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleNavIdChange = (navId: string) => {
    setCurrentNavId(navId);
  };

  const handleChapterInfoChange = (chapterId: string, chapterTitle: string) => {
    setCurrentChapterId(chapterId);
    setCurrentChapterTitle(chapterTitle);
  };

  const handleTotalPagesChange = (total: number) => {
    if (!totalPages) {
      setTotalPages(total);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-t-4 border-purple-400 mx-auto"></div>
          <p className="mt-6 text-slate-300 text-lg font-medium">
            Loading document...
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-gray-900">
        <div className="text-center bg-slate-800/50 backdrop-blur-sm rounded-2xl p-8 border border-slate-700/50">
          <div className="text-red-400 text-4xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-slate-200 mb-3">
            Error Loading Document
          </h2>
          <p className="text-slate-400 mb-4">{error}</p>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            Return to Library
          </button>
        </div>
      </div>
    );
  }

  // Render appropriate viewer based on document type
  const renderViewer = () => {
    switch (documentType) {
      case 'pdf':
        return (
          <PDFViewer
            filename={filename}
            currentPage={currentPage}
            onPageChange={handlePageChange}
            onTotalPagesChange={handleTotalPagesChange}
          />
        );
      case 'epub':
        return (
          <EPUBViewer
            filename={filename}
            onNavIdChange={handleNavIdChange}
            onChapterInfoChange={handleChapterInfoChange}
          />
        );
      default:
        return (
          <div className="flex items-center justify-center h-full bg-gray-900 text-gray-300">
            <div className="text-center">
              <div className="text-red-400 text-4xl mb-4">❓</div>
              <h2 className="text-2xl font-bold mb-4">Unknown Document Type</h2>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-gray-900">
      <SimpleResizablePanels
        leftPanel={renderViewer()}
        rightPanel={
          <TabbedRightPanel
            filename={filename}
            documentType={documentType}
            currentPage={currentPage}
            currentNavId={currentNavId}
            currentChapterId={currentChapterId}
            currentChapterTitle={currentChapterTitle}
            onPageJump={handlePageChange}
          />
        }
      />
    </div>
  );
}
