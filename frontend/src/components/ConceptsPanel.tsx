import { useState } from 'react';
import { useKnowledge } from '../hooks/useKnowledge';
import type { Concept, ExtractionStatusInfo } from '../types/knowledge';

interface ConceptsPanelProps {
  pdfId?: number;
  epubId?: number;
  filename?: string;
  documentType: 'pdf' | 'epub';
  currentPage: number;
  currentNavId?: string;
  currentChapterTitle?: string;
  onNavigateToSource?: (concept: Concept) => void;
}

export default function ConceptsPanel({
  pdfId,
  epubId,
  filename,
  documentType,
  currentPage,
  currentNavId,
  currentChapterTitle,
  onNavigateToSource,
}: ConceptsPanelProps) {
  const [expandedConceptId, setExpandedConceptId] = useState<number | null>(
    null
  );
  const [importanceFilter, setImportanceFilter] = useState<number>(1);
  const [searchText, setSearchText] = useState('');

  const bookId = documentType === 'pdf' ? pdfId : epubId;

  const {
    concepts,
    relationshipCount,
    isLoading,
    isExtracting,
    error,
    isSectionExtracted,
    extractionStatus,
    extractConcepts,
    cancelExtraction,
    clearError,
  } = useKnowledge({
    bookId,
    bookType: documentType,
    navId: currentNavId,
    pageNum: documentType === 'pdf' ? currentPage : undefined,
  });

  const filteredConcepts = concepts.filter(concept => {
    if (concept.importance < importanceFilter) return false;

    if (searchText) {
      const searchLower = searchText.toLowerCase();
      const nameMatch = concept.name.toLowerCase().includes(searchLower);
      const defMatch = concept.definition?.toLowerCase().includes(searchLower);
      if (!nameMatch && !defMatch) return false;
    }

    return true;
  });

  const sortedConcepts = [...filteredConcepts].sort(
    (a, b) => b.importance - a.importance
  );

  function handleConceptClick(concept: Concept): void {
    setExpandedConceptId(expandedConceptId === concept.id ? null : concept.id);
  }

  function handleNavigateToSource(concept: Concept, e: React.MouseEvent): void {
    e.stopPropagation();
    onNavigateToSource?.(concept);
  }

  async function handleExtract(): Promise<void> {
    const result = await extractConcepts();
    if (result) {
      console.log(
        `Extracted ${result.concepts_extracted} concepts, ${result.relationships_found} relationships`
      );
    }
  }

  async function handleCancel(): Promise<void> {
    const success = await cancelExtraction();
    if (success) {
      console.log('Cancellation requested');
    }
  }

  function renderImportanceStars(importance: number): React.ReactNode {
    return (
      <span className="text-yellow-400" title={`Importance: ${importance}/5`}>
        {'★'.repeat(importance)}
        {'☆'.repeat(5 - importance)}
      </span>
    );
  }

  function getSectionName(): string {
    if (documentType === 'epub') {
      return currentChapterTitle || currentNavId || 'Current Section';
    }
    return `Page ${currentPage}`;
  }

  function getExtractButtonText(): string {
    if (isExtracting) return '';
    if (isSectionExtracted) return 'Re-extract Concepts';
    return 'Extract Concepts';
  }

  function getExtractButtonClass(): string {
    if (isExtracting) {
      return 'bg-gray-600 text-gray-400 cursor-not-allowed';
    }
    if (isSectionExtracted) {
      return 'bg-gray-700 text-gray-300 hover:bg-gray-600';
    }
    return 'bg-blue-600 text-white hover:bg-blue-700';
  }

  if (!filename || !bookId) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <p className="text-gray-400 text-sm">
          Open a document to view concepts
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-900">
      <div className="border-b border-gray-700 px-4 py-3 bg-gray-800">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-200">Concepts</h3>
          <a
            href={`/graph/${bookId}?type=${documentType}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            View Full Graph →
          </a>
        </div>
        <p className="text-xs text-gray-400">
          {getSectionName()} • {concepts.length} concept
          {concepts.length !== 1 ? 's' : ''}
          {relationshipCount > 0 &&
            ` • ${relationshipCount} relation${relationshipCount !== 1 ? 's' : ''}`}
          {isSectionExtracted && (
            <span className="ml-2 text-green-400">✓ Extracted</span>
          )}
        </p>
      </div>

      <div className="border-b border-gray-700 px-4 py-3">
        {isExtracting ? (
          <ExtractionProgress
            status={extractionStatus}
            onCancel={handleCancel}
          />
        ) : (
          <>
            <button
              onClick={handleExtract}
              disabled={isExtracting}
              className={`w-full py-2 px-4 rounded-md text-sm font-medium transition-colors ${getExtractButtonClass()}`}
            >
              {getExtractButtonText()}
            </button>
            {!isSectionExtracted && concepts.length === 0 && !isLoading && (
              <p className="text-xs text-gray-500 mt-2 text-center">
                Click to extract concepts from this section
              </p>
            )}
          </>
        )}
      </div>

      {concepts.length > 0 && (
        <div className="border-b border-gray-700 px-4 py-3 space-y-3">
          <div className="relative">
            <input
              type="text"
              placeholder="Search concepts..."
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              className="w-full px-3 py-2 pl-8 text-sm bg-gray-800 border border-gray-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="absolute left-2.5 top-2.5 text-gray-400 text-sm">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Min importance:</span>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map(level => (
                <button
                  key={level}
                  onClick={() => setImportanceFilter(level)}
                  className={`w-6 h-6 text-xs rounded transition-colors ${
                    importanceFilter === level
                      ? 'bg-yellow-600 text-white'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="px-4 py-3 bg-red-900/30 border-b border-red-700">
          <div className="flex items-center justify-between">
            <span className="text-sm text-red-400">{error}</span>
            <button
              onClick={clearError}
              className="text-red-400 hover:text-red-300"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-gray-400 text-sm">Loading concepts...</div>
          </div>
        ) : sortedConcepts.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-center">
              <div className="text-gray-500 text-2xl mb-2">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-8 w-8 mx-auto"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                  />
                </svg>
              </div>
              <p className="text-gray-400 text-sm">
                {concepts.length === 0
                  ? 'No concepts extracted yet'
                  : 'No concepts match your filters'}
              </p>
            </div>
          </div>
        ) : (
          <div className="p-4 space-y-3">
            {sortedConcepts.map(concept => (
              <ConceptCard
                key={concept.id}
                concept={concept}
                isExpanded={expandedConceptId === concept.id}
                onClick={() => handleConceptClick(concept)}
                onNavigateToSource={e => handleNavigateToSource(concept, e)}
                renderImportanceStars={renderImportanceStars}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface ExtractionProgressProps {
  status: ExtractionStatusInfo | null;
  onCancel: () => void;
}

function ExtractionProgress({ status, onCancel }: ExtractionProgressProps) {
  const isCancelling = status?.status === 'cancelling';

  // Single-phase progress (concepts and relationships extracted together)
  const progress = status?.progress_percent ?? 0;
  const chunksProcessed = status?.chunks_processed ?? 0;
  const totalChunks = status?.total_chunks ?? 0;
  const conceptsStored = status?.concepts_stored ?? 0;
  const relationshipsStored = status?.relationships_stored ?? 0;
  const elapsedSeconds = status?.elapsed_seconds ?? 0;

  // Format elapsed time
  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="space-y-3">
      {/* Progress bar */}
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ${
            isCancelling ? 'bg-yellow-500' : 'bg-blue-500'
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Chunk progress */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-blue-400">
          Chunk {chunksProcessed}/{totalChunks}
        </span>
        <span className="text-gray-400">{formatTime(elapsedSeconds)}</span>
      </div>

      {/* Status text */}
      <div className="text-xs text-gray-300">
        {isCancelling ? (
          <span className="text-yellow-400">Cancelling...</span>
        ) : status ? (
          `Extracting knowledge... ${progress.toFixed(0)}%`
        ) : (
          'Starting extraction...'
        )}
      </div>

      {/* Stats */}
      {status && (
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>{conceptsStored} concepts</span>
          <span>{relationshipsStored} relationships</span>
        </div>
      )}

      {/* Cancel button */}
      <button
        onClick={onCancel}
        disabled={isCancelling}
        className={`w-full py-2 px-4 rounded-md text-sm font-medium transition-colors ${
          isCancelling
            ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
            : 'bg-red-600/80 text-white hover:bg-red-600'
        }`}
      >
        {isCancelling ? 'Cancelling...' : 'Stop Extraction'}
      </button>

      {/* Info message */}
      <p className="text-xs text-gray-500 text-center">
        {isCancelling
          ? 'Waiting for current chunk to finish...'
          : 'Progress is saved. You can stop and resume later.'}
      </p>
    </div>
  );
}

interface ConceptCardProps {
  concept: Concept;
  isExpanded: boolean;
  onClick: () => void;
  onNavigateToSource: (e: React.MouseEvent) => void;
  renderImportanceStars: (importance: number) => React.ReactNode;
}

function ConceptCard({
  concept,
  isExpanded,
  onClick,
  onNavigateToSource,
  renderImportanceStars,
}: ConceptCardProps) {
  return (
    <div
      className={`p-3 rounded-md border transition-all cursor-pointer ${
        isExpanded
          ? 'border-blue-500 bg-blue-900/20'
          : 'border-gray-700 bg-gray-800 hover:bg-gray-750'
      }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-gray-200 flex-1">
          {concept.name}
        </h4>
        <div className="flex items-center gap-2 flex-shrink-0 text-xs">
          {renderImportanceStars(concept.importance)}
        </div>
      </div>

      {concept.definition && !isExpanded && (
        <p className="text-xs text-gray-400 mt-2 line-clamp-2">
          {concept.definition}
        </p>
      )}

      {isExpanded && (
        <div className="mt-3 space-y-3">
          {concept.definition && (
            <div>
              <h5 className="text-xs font-medium text-gray-400 mb-1">
                Definition
              </h5>
              <p className="text-sm text-gray-300">{concept.definition}</p>
            </div>
          )}

          {concept.source_quote && (
            <div>
              <h5 className="text-xs font-medium text-gray-400 mb-1">Source</h5>
              <blockquote className="text-sm text-gray-400 italic border-l-2 border-gray-600 pl-3">
                "{concept.source_quote}"
              </blockquote>
            </div>
          )}

          <div className="flex items-center gap-2 pt-2 border-t border-gray-700">
            <button
              onClick={onNavigateToSource}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1"
              title="Navigate to source passage"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-3 w-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                />
              </svg>
              Go to Source
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
