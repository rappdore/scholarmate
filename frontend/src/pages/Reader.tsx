import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PDFViewer from '../components/PDFViewer';
import TabbedRightPanel from '../components/TabbedRightPanel';
import SimpleResizablePanels from '../components/SimpleResizablePanels';
import { pdfService } from '../services/api';

export default function Reader() {
  const { filename } = useParams<{ filename: string }>();
  const navigate = useNavigate();
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState<number | null>(null);
  const [isProgressLoaded, setIsProgressLoaded] = useState(false);

  // Load reading progress on component mount
  useEffect(() => {
    if (!filename) return;

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
  }, [filename]);

  // Save reading progress when page changes
  useEffect(() => {
    if (!filename || !isProgressLoaded || !totalPages) return;

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
  }, [filename, currentPage, totalPages, isProgressLoaded]);

  // Keyboard navigation for PDF pages
  useEffect(() => {
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
  }, [currentPage, totalPages]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleTotalPagesChange = (total: number) => {
    if (!totalPages) {
      setTotalPages(total);
    }
  };

  // Note: handleTextSelection function removed as highlight creation is now handled
  // entirely within PDFViewer component using the useHighlights hook

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-gray-900">
      <SimpleResizablePanels
        leftPanel={
          <PDFViewer
            filename={filename}
            currentPage={currentPage}
            onPageChange={handlePageChange}
            onTotalPagesChange={handleTotalPagesChange}
          />
        }
        rightPanel={
          <TabbedRightPanel
            filename={filename}
            currentPage={currentPage}
            onPageJump={handlePageChange}
          />
        }
      />
    </div>
  );
}
