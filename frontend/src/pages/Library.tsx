import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { pdfService } from '../services/api';
import { mockPdfService, initializeMockData } from '../services/mockApi';
import type { PDF, BookStatus } from '../types/pdf';
import {
  computeBookStatus,
  getBookStatus,
  matchesStatusFilter,
  calculateStatusCounts,
  shouldPromptFinished,
} from '../utils/bookStatus';
import LibraryTabs from '../components/LibraryTabs';
import BookActionMenu from '../components/BookActionMenu';

export default function Library() {
  const [pdfs, setPdfs] = useState<PDF[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | BookStatus>('reading');
  const [hoveredBook, setHoveredBook] = useState<string | null>(null);
  const [statusCounts, setStatusCounts] = useState({
    all: 0,
    new: 0,
    reading: 0,
    finished: 0,
  });
  const navigate = useNavigate();

  useEffect(() => {
    // Initialize mock data for development
    initializeMockData();
    loadPDFs();
  }, []);

  useEffect(() => {
    // Update status counts whenever PDFs change
    const counts = calculateStatusCounts(pdfs);
    setStatusCounts(counts);
  }, [pdfs]);

  const loadPDFs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await pdfService.listPDFs();

      // Enhance PDFs with computed status information
      const enhancedPdfs = data.map(pdf => {
        const computed_status = computeBookStatus(pdf);
        const mockStatus = mockPdfService.getBookStatus(pdf.filename);

        return {
          ...pdf,
          computed_status,
          manual_status: mockStatus?.status,
          // Update reading_progress with status fields if they exist
          reading_progress: pdf.reading_progress
            ? {
                ...pdf.reading_progress,
                status: mockStatus?.status || computed_status,
                status_updated_at:
                  mockStatus?.updated_at || new Date().toISOString(),
                manually_set: mockStatus?.manually_set || false,
              }
            : null,
        };
      });

      setPdfs(enhancedPdfs);

      // Check for books that should prompt for finished status
      enhancedPdfs.forEach(pdf => {
        if (shouldPromptFinished(pdf)) {
          console.log(`Book "${pdf.title}" is ready to be marked as finished!`);
          // TODO: Show notification or prompt in a future enhancement
        }
      });
    } catch (err) {
      console.error('Error loading PDFs:', err);
      setError('Failed to load PDFs. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (pdf: PDF, newStatus: BookStatus) => {
    try {
      // Update status via mock API
      await mockPdfService.updateBookStatus(pdf.filename, newStatus, true);

      // Update local state
      setPdfs(prevPdfs =>
        prevPdfs.map(p =>
          p.filename === pdf.filename
            ? {
                ...p,
                manual_status: newStatus,
                reading_progress: p.reading_progress
                  ? {
                      ...p.reading_progress,
                      status: newStatus,
                      status_updated_at: new Date().toISOString(),
                      manually_set: true,
                    }
                  : null,
              }
            : p
        )
      );

      console.log(`Updated "${pdf.title}" status to "${newStatus}"`);
    } catch (err) {
      console.error('Error updating book status:', err);
    }
  };

  const handleDeleteBook = async (pdf: PDF) => {
    try {
      // Delete via mock API
      await mockPdfService.deleteBook(pdf.filename);

      // Remove from local state
      setPdfs(prevPdfs => prevPdfs.filter(p => p.filename !== pdf.filename));

      console.log(`Deleted "${pdf.title}"`);
      // TODO: In Phase 3, this will also delete the actual file and database records
    } catch (err) {
      console.error('Error deleting book:', err);
    }
  };

  const filteredPdfs = pdfs.filter(pdf => matchesStatusFilter(pdf, activeTab));

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const handlePDFClick = (filename: string) => {
    navigate(`/read/${encodeURIComponent(filename)}`);
  };

  const getStatusBadge = (pdf: PDF) => {
    const status = getBookStatus(pdf);
    const statusConfig = {
      new: {
        label: 'New',
        color: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
        icon: '📚',
      },
      reading: {
        label: 'Reading',
        color: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
        icon: '📖',
      },
      finished: {
        label: 'Finished',
        color: 'bg-green-500/20 text-green-300 border-green-500/30',
        icon: '✅',
      },
    };

    const config = statusConfig[status];
    return (
      <div
        className={`text-xs px-2 py-1 rounded-full border flex items-center gap-1 ${config.color}`}
      >
        <span>{config.icon}</span>
        <span>{config.label}</span>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-t-4 border-purple-400 mx-auto"></div>
          <p className="mt-6 text-slate-300 text-lg font-medium">
            Loading your library...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-center bg-slate-800/50 backdrop-blur-sm rounded-2xl p-8 border border-slate-700/50">
          <div className="text-red-400 text-4xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-slate-200 mb-3">
            Error Loading PDFs
          </h2>
          <p className="text-slate-400 mb-6 max-w-md">{error}</p>
          <button
            onClick={loadPDFs}
            className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all duration-200 font-medium shadow-lg hover:shadow-purple-500/25"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8 text-center">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400 bg-clip-text text-transparent mb-4">
            PDF Library
          </h1>
          <p className="text-slate-300 text-lg font-medium">
            Organize and track your reading progress with intelligent status
            management
          </p>
          <div className="w-24 h-1 bg-gradient-to-r from-purple-500 to-blue-500 mx-auto mt-4 rounded-full"></div>
        </div>

        {pdfs.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-slate-600 text-8xl mb-6">📚</div>
            <h2 className="text-2xl font-bold text-slate-300 mb-4">
              Your Library is Empty
            </h2>
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-8 border border-slate-700/50 max-w-2xl mx-auto">
              <p className="text-slate-300 text-lg mb-4">
                No PDFs found in your library
              </p>
              <div className="text-left space-y-3">
                <p className="text-slate-400">
                  <span className="font-semibold text-purple-400">
                    📁 To add PDFs:
                  </span>
                </p>
                <ol className="text-slate-400 space-y-2 ml-4">
                  <li className="flex items-start gap-2">
                    <span className="text-purple-400 font-bold">1.</span>
                    <span>
                      Navigate to the{' '}
                      <code className="bg-slate-700 px-2 py-1 rounded text-sm font-mono">
                        backend/pdfs
                      </code>{' '}
                      directory
                    </span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-purple-400 font-bold">2.</span>
                    <span>Copy your PDF files into that folder</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-purple-400 font-bold">3.</span>
                    <span>Refresh this page to see your PDFs</span>
                  </li>
                </ol>
              </div>
              <button
                onClick={loadPDFs}
                className="mt-6 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all duration-200 font-medium shadow-lg hover:shadow-purple-500/25"
              >
                🔄 Refresh Library
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Library Tabs */}
            <LibraryTabs
              activeTab={activeTab}
              counts={statusCounts}
              onTabChange={setActiveTab}
            />

            {/* Books Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
              {filteredPdfs.map(pdf => (
                <div
                  key={pdf.filename}
                  className="relative group bg-slate-800/60 backdrop-blur-sm rounded-2xl shadow-xl hover:shadow-2xl hover:shadow-purple-500/20 transition-all duration-300 cursor-pointer border border-slate-700/50 hover:border-purple-500/50 overflow-hidden transform hover:scale-105 flex flex-col"
                  onMouseEnter={() => setHoveredBook(pdf.filename)}
                  onMouseLeave={() => setHoveredBook(null)}
                >
                  {/* Book Action Menu */}
                  <BookActionMenu
                    pdf={pdf}
                    onStatusChange={status => handleStatusChange(pdf, status)}
                    onDelete={() => handleDeleteBook(pdf)}
                    isVisible={hoveredBook === pdf.filename}
                  />

                  <div
                    className="p-6 flex-1"
                    onClick={() => handlePDFClick(pdf.filename)}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="w-16 h-20 bg-slate-700/50 rounded-lg overflow-hidden group-hover:scale-110 transition-transform duration-200 border border-slate-600/50">
                        <img
                          src={pdfService.getThumbnailUrl(pdf.filename)}
                          alt={`${pdf.title} thumbnail`}
                          className="w-full h-full object-cover"
                          onError={e => {
                            const target = e.target as HTMLImageElement;
                            target.style.display = 'none';
                            target.parentElement!.innerHTML =
                              '<div class="w-full h-full flex items-center justify-center text-purple-400 text-2xl">📄</div>';
                          }}
                        />
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        {getStatusBadge(pdf)}
                        <div className="flex items-center gap-2">
                          {pdf.highlights_info &&
                            pdf.highlights_info.highlights_count > 0 && (
                              <div className="text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 px-2 py-1 rounded-full flex items-center gap-1">
                                🖍️ {pdf.highlights_info.highlights_count}
                              </div>
                            )}
                          {pdf.notes_info && (
                            <div className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-1 rounded-full flex items-center gap-1">
                              📝 {pdf.notes_info.notes_count}
                            </div>
                          )}
                        </div>
                        <div className="text-sm text-slate-400 bg-slate-700/50 px-3 py-1 rounded-full">
                          {pdf.num_pages} pages
                        </div>
                      </div>
                    </div>

                    <h3
                      className="font-bold text-slate-200 mb-3 line-clamp-2 overflow-hidden text-lg group-hover:text-purple-300 transition-colors duration-200"
                      style={{
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                      }}
                    >
                      {pdf.title}
                    </h3>

                    <p className="text-sm text-slate-400 mb-4 font-medium">
                      by {pdf.author}
                    </p>

                    <div className="text-xs text-slate-500 space-y-2">
                      <div className="flex items-center justify-between">
                        <span>Size:</span>
                        <span className="text-slate-400">
                          {formatFileSize(pdf.file_size)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Added:</span>
                        <span className="text-slate-400">
                          {formatDate(pdf.modified_date)}
                        </span>
                      </div>
                    </div>

                    {pdf.reading_progress && (
                      <div className="mt-4 pt-3 border-t border-slate-600/50">
                        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                          <span>Reading Progress</span>
                          <span className="text-purple-400 font-medium">
                            {pdf.reading_progress.progress_percentage}%
                          </span>
                        </div>
                        <div className="w-full bg-slate-700/50 rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-purple-500 to-blue-500 h-full rounded-full transition-all duration-300"
                            style={{
                              width: `${pdf.reading_progress.progress_percentage}%`,
                            }}
                          ></div>
                        </div>
                        <div className="text-xs text-slate-500 mt-1">
                          Page {pdf.reading_progress.last_page} of{' '}
                          {pdf.reading_progress.total_pages}
                        </div>
                      </div>
                    )}

                    {pdf.notes_info && (
                      <div
                        className={`${pdf.reading_progress ? 'mt-3' : 'mt-4'} pt-3 border-t border-slate-600/50`}
                      >
                        <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                          <div className="flex items-center gap-1">
                            <span>📝</span>
                            <span>Notes</span>
                          </div>
                          <span className="text-green-400 font-medium">
                            {pdf.notes_info.notes_count}{' '}
                            {pdf.notes_info.notes_count === 1
                              ? 'note'
                              : 'notes'}
                          </span>
                        </div>
                        <div className="text-xs text-slate-500">
                          Latest: {pdf.notes_info.latest_note_title}
                        </div>
                        <div className="text-xs text-slate-600 mt-1">
                          {formatDate(pdf.notes_info.latest_note_date)}
                        </div>
                      </div>
                    )}

                    {pdf.error && (
                      <div className="mt-3 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2">
                        ⚠️ {pdf.error}
                      </div>
                    )}
                  </div>

                  <div className="px-6 py-4 bg-slate-700/30 border-t border-slate-600/50">
                    <div className="text-xs text-slate-400 truncate font-mono">
                      {pdf.filename}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {filteredPdfs.length === 0 && activeTab !== 'all' && (
              <div className="text-center py-16">
                <div className="text-slate-600 text-6xl mb-4">
                  {activeTab === 'new' && '📚'}
                  {activeTab === 'reading' && '📖'}
                  {activeTab === 'finished' && '✅'}
                </div>
                <h3 className="text-xl font-bold text-slate-300 mb-2">
                  No {activeTab} books found
                </h3>
                <p className="text-slate-400">
                  {activeTab === 'new' &&
                    'Add some PDFs to your library to get started!'}
                  {activeTab === 'reading' &&
                    'Start reading a book to see it here.'}
                  {activeTab === 'finished' &&
                    'Mark books as finished to see them here.'}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
