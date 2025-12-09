import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { pdfService } from '../services/api';
import { epubService } from '../services/epubService';
import type { PDF, BookStatus } from '../types/pdf';
import type { Document } from '../types/document';
import {
  isPDFDocument,
  isEPUBDocument,
  getDocumentLength,
  getDocumentLengthUnit,
} from '../types/document';
import {
  getBookStatus,
  matchesStatusFilter,
  shouldPromptFinished,
} from '../utils/bookStatus';
import LibraryTabs from '../components/LibraryTabs';
import BookActionMenu from '../components/BookActionMenu';

export default function Library() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | BookStatus>('reading');
  const [hoveredBook, setHoveredBook] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [statusCounts, setStatusCounts] = useState({
    all: 0,
    new: 0,
    reading: 0,
    finished: 0,
  });
  const navigate = useNavigate();

  useEffect(() => {
    loadDocuments();
    loadStatusCounts();
  }, []);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);

      // Call both services in parallel
      const [pdfData, epubData] = await Promise.all([
        pdfService.listPDFs().catch(() => []), // Return empty array if service fails
        epubService.listEPUBs().catch(() => []), // Return empty array if service fails
      ]);

      // Convert PDFs to Document format and merge with EPUBs
      const pdfDocuments: Document[] = pdfData.map(pdf => ({
        ...pdf,
        type: 'pdf' as const,
        num_pages: pdf.num_pages,
      }));

      const allDocuments: Document[] = [...pdfDocuments, ...epubData];

      // The backend now provides status information directly in reading_progress
      // No need for complex status computation - just use what the backend provides
      const enhancedDocuments = allDocuments.map(doc => {
        // Get status from reading progress or default to 'new'
        const status = doc.reading_progress?.status || 'new';

        return {
          ...doc,
          computed_status: status as BookStatus,
          manual_status: doc.reading_progress?.manually_set
            ? (status as BookStatus)
            : undefined,
        };
      });

      setDocuments(enhancedDocuments);

      // Check for books that should prompt for finished status
      enhancedDocuments.forEach(doc => {
        if (shouldPromptFinished(doc as any)) {
          // Use 'as any' for now since shouldPromptFinished expects PDF
          console.log(`Book "${doc.title}" is ready to be marked as finished!`);
          // TODO: Show notification or prompt in a future enhancement
        }
      });
    } catch (err) {
      console.error('Error loading documents:', err);
      setError('Failed to load documents. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const loadStatusCounts = async () => {
    try {
      // Load status counts from both PDF and EPUB services in parallel
      const [pdfCounts, epubCounts] = await Promise.all([
        pdfService
          .getStatusCounts()
          .catch(() => ({ new: 0, reading: 0, finished: 0 })),
        epubService
          .getEPUBStatusCounts()
          .catch(() => ({ new: 0, reading: 0, finished: 0 })),
      ]);

      // Combine the counts
      const combinedCounts = {
        all:
          pdfCounts.new +
          pdfCounts.reading +
          pdfCounts.finished +
          epubCounts.new +
          epubCounts.reading +
          epubCounts.finished,
        new: pdfCounts.new + epubCounts.new,
        reading: pdfCounts.reading + epubCounts.reading,
        finished: pdfCounts.finished + epubCounts.finished,
      };

      setStatusCounts(combinedCounts);
    } catch (err) {
      console.error('Error loading status counts:', err);
    }
  };

  const handleStatusChange = async (
    document: Document,
    newStatus: BookStatus
  ) => {
    try {
      // Update status via appropriate API based on document type
      if (isPDFDocument(document)) {
        await pdfService.updateBookStatus(document.filename, newStatus, true);
      } else if (isEPUBDocument(document)) {
        await epubService.updateEPUBBookStatus(
          document.filename,
          newStatus,
          true
        );
      }

      // Update local state
      setDocuments(prevDocs =>
        prevDocs.map(d =>
          d.filename === document.filename
            ? {
                ...d,
                computed_status: newStatus,
                manual_status: newStatus,
                reading_progress: d.reading_progress
                  ? {
                      ...d.reading_progress,
                      status: newStatus,
                      status_updated_at: new Date().toISOString(),
                      manually_set: true,
                    }
                  : null,
              }
            : d
        )
      );

      // Reload status counts
      await loadStatusCounts();

      console.log(`Updated "${document.title}" status to "${newStatus}"`);
    } catch (err) {
      console.error('Error updating book status:', err);
    }
  };

  const handleDeleteBook = async (document: Document) => {
    try {
      // Delete via appropriate API based on document type
      if (isPDFDocument(document)) {
        await pdfService.deleteBook(document.filename);
      } else if (isEPUBDocument(document)) {
        await epubService.deleteEPUBBook(document.filename);
      }

      // Remove from local state
      setDocuments(prevDocs =>
        prevDocs.filter(d => d.filename !== document.filename)
      );

      // Reload status counts
      await loadStatusCounts();

      console.log(`Deleted "${document.title}"`);
    } catch (err) {
      console.error('Error deleting book:', err);
    }
  };

  const handleRefreshCache = async () => {
    try {
      setRefreshing(true);
      console.log('Refreshing library cache (PDFs and EPUBs)...');

      // Refresh both PDF and EPUB caches in parallel
      const [pdfResult, epubResult] = await Promise.all([
        pdfService.refreshPDFCache(),
        epubService.refreshEPUBCache(),
      ]);

      console.log('PDF cache refreshed:', pdfResult);
      console.log('EPUB cache refreshed:', epubResult);

      // Reload documents and status counts
      await loadDocuments();
      await loadStatusCounts();

      console.log(
        `✅ Library cache refreshed successfully! ${pdfResult.pdf_count} PDFs and ${epubResult.epub_count} EPUBs cached.`
      );
    } catch (err) {
      console.error('Error refreshing cache:', err);
      setError('Failed to refresh cache. Please try again.');
    } finally {
      setRefreshing(false);
    }
  };

  const filteredDocuments = documents
    .filter(doc => matchesStatusFilter(doc as any, activeTab))
    .sort((a, b) => {
      // Sort by last_updated in reverse chronological order (most recent first)
      const aLastUpdated = a.reading_progress?.last_updated;
      const bLastUpdated = b.reading_progress?.last_updated;

      // Books with reading progress come before books without
      if (!aLastUpdated && !bLastUpdated) return 0;
      if (!aLastUpdated) return 1;
      if (!bLastUpdated) return -1;

      // Compare dates in reverse chronological order
      return (
        new Date(bLastUpdated).getTime() - new Date(aLastUpdated).getTime()
      );
    });

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

  const handleDocumentClick = (filename: string) => {
    navigate(`/read/${encodeURIComponent(filename)}`);
  };

  const getDocumentIcon = (document: Document): string => {
    return isPDFDocument(document) ? '📄' : '📚';
  };

  const getThumbnailUrl = (document: Document): string => {
    return isPDFDocument(document)
      ? pdfService.getThumbnailUrl(document.filename)
      : epubService.getThumbnailUrl(document.filename);
  };

  const getStatusBadge = (document: Document) => {
    const status = getBookStatus(document as any); // Use 'as any' for now
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
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
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
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <div className="text-center bg-slate-800/50 backdrop-blur-sm rounded-2xl p-8 border border-slate-700/50">
          <div className="text-red-400 text-4xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-slate-200 mb-3">
            Error Loading PDFs
          </h2>
          <p className="text-slate-400 mb-6 max-w-md">{error}</p>
          <button
            onClick={loadDocuments}
            className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all duration-200 font-medium shadow-lg hover:shadow-purple-500/25"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {documents.length === 0 ? (
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
              onClick={loadDocuments}
              className="mt-6 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all duration-200 font-medium shadow-lg hover:shadow-purple-500/25"
            >
              🔄 Refresh Library
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Header with Tabs and Refresh Button */}
          <div className="flex items-center justify-between mb-6">
            <LibraryTabs
              activeTab={activeTab}
              counts={statusCounts}
              onTabChange={setActiveTab}
            />
            <button
              onClick={handleRefreshCache}
              disabled={refreshing}
              className="px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all duration-200 font-medium shadow-lg hover:shadow-purple-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              title="Refresh library cache"
            >
              {refreshing ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Refreshing...</span>
                </>
              ) : (
                <>
                  <span>🔄</span>
                  <span>Refresh Cache</span>
                </>
              )}
            </button>
          </div>

          {/* Books Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-8">
            {filteredDocuments.map(doc => (
              <div
                key={doc.filename}
                className="relative group bg-slate-800/60 backdrop-blur-sm rounded-2xl shadow-xl hover:shadow-2xl hover:shadow-purple-500/20 transition-all duration-300 cursor-pointer border border-slate-700/50 hover:border-purple-500/50 overflow-hidden transform hover:scale-105 flex flex-col"
                onMouseEnter={() => setHoveredBook(doc.filename)}
                onMouseLeave={() => setHoveredBook(null)}
              >
                {/* Book Action Menu */}
                <BookActionMenu
                  pdf={doc as any} // Temporary fix until BookActionMenu is updated to support Document type
                  onStatusChange={status => handleStatusChange(doc, status)}
                  onDelete={() => handleDeleteBook(doc)}
                  isVisible={hoveredBook === doc.filename}
                />

                <div
                  className="p-6 flex-1"
                  onClick={() => handleDocumentClick(doc.filename)}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-16 h-20 bg-slate-700/50 rounded-lg overflow-hidden group-hover:scale-110 transition-transform duration-200 border border-slate-600/50">
                      <img
                        src={getThumbnailUrl(doc)}
                        alt={`${doc.title} thumbnail`}
                        className="w-full h-full object-cover"
                        onError={e => {
                          const target = e.target as HTMLImageElement;
                          target.style.display = 'none';
                          target.parentElement!.innerHTML = `
                            <div class="w-full h-full flex items-center justify-center text-purple-400 text-2xl">
                              ${getDocumentIcon(doc)}
                            </div>
                          `;
                        }}
                      />
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      {getStatusBadge(doc)}
                      <div className="flex items-center gap-2">
                        {doc.highlights_info &&
                          doc.highlights_info.highlights_count > 0 && (
                            <div className="text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 px-2 py-1 rounded-full flex items-center gap-1">
                              🖍️ {doc.highlights_info.highlights_count}
                            </div>
                          )}
                        {doc.notes_info && (
                          <div className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-1 rounded-full flex items-center gap-1">
                            📝 {doc.notes_info.notes_count}
                          </div>
                        )}
                      </div>
                      <div className="text-sm text-slate-400 bg-slate-700/50 px-3 py-1 rounded-full">
                        {getDocumentLength(doc)} {getDocumentLengthUnit(doc)}
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
                    {doc.title}
                  </h3>

                  <p className="text-sm text-slate-400 mb-4 font-medium">
                    by {doc.author}
                  </p>

                  <div className="text-xs text-slate-500 space-y-2">
                    <div className="flex items-center justify-between">
                      <span>Size:</span>
                      <span className="text-slate-400">
                        {formatFileSize(doc.file_size)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Added:</span>
                      <span className="text-slate-400">
                        {formatDate(doc.modified_date)}
                      </span>
                    </div>
                  </div>

                  {doc.reading_progress && (
                    <div className="mt-4 pt-3 border-t border-slate-600/50">
                      <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                        <span>Reading Progress</span>
                        <span className="text-purple-400 font-medium">
                          {doc.reading_progress.progress_percentage}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-700/50 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-purple-500 to-blue-500 h-full rounded-full transition-all duration-300"
                          style={{
                            width: `${doc.reading_progress.progress_percentage}%`,
                          }}
                        ></div>
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        Page {doc.reading_progress.last_page} of{' '}
                        {doc.reading_progress.total_pages}
                      </div>
                    </div>
                  )}

                  {doc.notes_info && (
                    <div
                      className={`${doc.reading_progress ? 'mt-3' : 'mt-4'} pt-3 border-t border-slate-600/50`}
                    >
                      <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                        <div className="flex items-center gap-1">
                          <span>📝</span>
                          <span>Notes</span>
                        </div>
                        <span className="text-green-400 font-medium">
                          {doc.notes_info.notes_count}{' '}
                          {doc.notes_info.notes_count === 1 ? 'note' : 'notes'}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500">
                        Latest: {doc.notes_info.latest_note_title}
                      </div>
                      <div className="text-xs text-slate-600 mt-1">
                        {formatDate(doc.notes_info.latest_note_date)}
                      </div>
                    </div>
                  )}

                  {doc.error && (
                    <div className="mt-3 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2">
                      ⚠️ {doc.error}
                    </div>
                  )}
                </div>

                <div className="px-6 py-4 bg-slate-700/30 border-t border-slate-600/50">
                  <div className="text-xs text-slate-400 truncate font-mono">
                    {doc.filename}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filteredDocuments.length === 0 && activeTab !== 'all' && (
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
  );
}
