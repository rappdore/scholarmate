import React, { useState, useEffect } from 'react';
import { useHighlightsContext } from '../contexts/HighlightsContext';
import type { Highlight } from '../types/highlights';
import { HighlightColor } from '../types/highlights';

interface HighlightsPanelProps {
  filename?: string;
  currentPage: number;
  selectedHighlightId?: string;
  onHighlightSelect?: (highlight: Highlight) => void;
  onPageJump?: (pageNumber: number) => void;
}

export default function HighlightsPanel({
  filename,
  currentPage,
  selectedHighlightId,
  onHighlightSelect,
  onPageJump,
}: HighlightsPanelProps) {
  const [searchText, setSearchText] = useState('');
  const [colorFilter, setColorFilter] = useState<HighlightColor | 'all'>('all');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'page'>('newest');
  const [expandedPages, setExpandedPages] = useState<Set<number>>(
    new Set([currentPage])
  );

  // Use shared context for highlights
  const {
    highlights,
    isLoading,
    error,
    deleteHighlight,
    updateHighlightColor,
    setCurrentFilename,
  } = useHighlightsContext();

  // Set current filename when it changes
  useEffect(() => {
    setCurrentFilename(filename || null);
  }, [filename, setCurrentFilename]);

  // Auto-expand current page section
  useEffect(() => {
    setExpandedPages(prev => new Set([...prev, currentPage]));
  }, [currentPage]);

  // Filter and sort highlights
  const filteredHighlights = highlights
    .filter(highlight => {
      // Text search filter
      if (
        searchText &&
        !highlight.selectedText.toLowerCase().includes(searchText.toLowerCase())
      ) {
        return false;
      }
      // Color filter
      if (colorFilter !== 'all' && highlight.color !== colorFilter) {
        return false;
      }
      return true;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'newest':
          return (
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          );
        case 'oldest':
          return (
            new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
          );
        case 'page':
          return (
            a.pageNumber - b.pageNumber ||
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          );
        default:
          return 0;
      }
    });

  // Group highlights by page
  const highlightsByPage = filteredHighlights.reduce(
    (acc, highlight) => {
      if (!acc[highlight.pageNumber]) {
        acc[highlight.pageNumber] = [];
      }
      acc[highlight.pageNumber].push(highlight);
      return acc;
    },
    {} as Record<number, Highlight[]>
  );

  const pageNumbers = Object.keys(highlightsByPage)
    .map(Number)
    .sort((a, b) => a - b);

  // Handle highlight selection
  const handleHighlightClick = (highlight: Highlight) => {
    onHighlightSelect?.(highlight);
    // Jump to page if not current page
    if (highlight.pageNumber !== currentPage) {
      onPageJump?.(highlight.pageNumber);
    }
  };

  // Handle highlight deletion
  const handleDeleteHighlight = async (highlightId: string) => {
    const success = await deleteHighlight(highlightId);
    if (success) {
      console.log('Highlight deleted from panel:', highlightId);
    }
  };

  // Handle color change
  const handleColorChange = async (
    highlightId: string,
    newColor: HighlightColor
  ) => {
    const success = await updateHighlightColor(highlightId, newColor);
    if (success) {
      console.log('Highlight color updated:', highlightId, newColor);
    }
  };

  // Toggle page expansion
  const togglePageExpansion = (pageNumber: number) => {
    setExpandedPages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(pageNumber)) {
        newSet.delete(pageNumber);
      } else {
        newSet.add(pageNumber);
      }
      return newSet;
    });
  };

  // Format date for display
  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Get color name for display
  const getColorName = (color: HighlightColor): string => {
    const colorNames: Record<HighlightColor, string> = {
      [HighlightColor.YELLOW]: 'Yellow',
      [HighlightColor.GREEN]: 'Green',
      [HighlightColor.BLUE]: 'Blue',
      [HighlightColor.PINK]: 'Pink',
      [HighlightColor.ORANGE]: 'Orange',
      [HighlightColor.PURPLE]: 'Purple',
      [HighlightColor.RED]: 'Red',
      [HighlightColor.CYAN]: 'Cyan',
    };
    return colorNames[color] || 'Unknown';
  };

  if (!filename) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <p className="text-gray-400 text-sm">Open a PDF to view highlights</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="border-b border-gray-700 px-4 py-3 bg-gray-800">
        <h3 className="text-sm font-medium text-gray-200 mb-2">
          Highlights for {filename}
        </h3>
        <p className="text-xs text-gray-400">
          {highlights.length}{' '}
          {highlights.length === 1 ? 'highlight' : 'highlights'} total
          {filteredHighlights.length !== highlights.length &&
            ` • ${filteredHighlights.length} shown`}
        </p>
      </div>

      {/* Search and Filters */}
      <div className="border-b border-gray-700 px-4 py-3 space-y-3">
        {/* Search Bar */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search highlights..."
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            className="w-full px-3 py-2 pl-8 text-sm bg-gray-800 border border-gray-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <div className="absolute left-2.5 top-2.5 text-gray-400">🔍</div>
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <select
            value={colorFilter}
            onChange={e =>
              setColorFilter(e.target.value as HighlightColor | 'all')
            }
            className="flex-1 px-2 py-1 text-xs bg-gray-800 border border-gray-600 rounded text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All Colors</option>
            {Object.values(HighlightColor).map(color => (
              <option key={color} value={color}>
                {getColorName(color)}
              </option>
            ))}
          </select>

          <select
            value={sortBy}
            onChange={e =>
              setSortBy(e.target.value as 'newest' | 'oldest' | 'page')
            }
            className="flex-1 px-2 py-1 text-xs bg-gray-800 border border-gray-600 rounded text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
            <option value="page">By Page</option>
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-gray-400 text-sm">Loading highlights...</div>
          </div>
        ) : error ? (
          <div className="p-4">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        ) : filteredHighlights.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-center">
              <div className="text-gray-500 text-2xl mb-2">🖍️</div>
              <p className="text-gray-400 text-sm">
                {highlights.length === 0
                  ? 'No highlights created yet'
                  : 'No highlights match your filters'}
              </p>
              <p className="text-gray-500 text-xs mt-1">
                {highlights.length === 0
                  ? 'Select text in the PDF to create highlights'
                  : 'Try adjusting your search or filters'}
              </p>
            </div>
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {sortBy === 'page' ? (
              // Page-grouped view (existing logic)
              <>
                {/* Current Page Highlights */}
                {highlightsByPage[currentPage] && (
                  <div>
                    <h4 className="text-xs font-semibold text-blue-400 mb-3 uppercase tracking-wider">
                      Current Page ({currentPage})
                    </h4>
                    <div className="space-y-2">
                      {highlightsByPage[currentPage].map(highlight => (
                        <HighlightItem
                          key={highlight.id}
                          highlight={highlight}
                          isSelected={selectedHighlightId === highlight.id}
                          isCurrent={true}
                          onSelect={() => handleHighlightClick(highlight)}
                          onDelete={() => handleDeleteHighlight(highlight.id)}
                          onColorChange={color =>
                            handleColorChange(highlight.id, color)
                          }
                          onJumpToPage={() =>
                            onPageJump?.(highlight.pageNumber)
                          }
                          formatDate={formatDate}
                          getColorName={getColorName}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Other Pages */}
                {pageNumbers.filter(page => page !== currentPage).length >
                  0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                      Other Pages
                    </h4>
                    <div className="space-y-3">
                      {pageNumbers
                        .filter(page => page !== currentPage)
                        .map(pageNumber => (
                          <div key={pageNumber}>
                            <button
                              onClick={() => togglePageExpansion(pageNumber)}
                              className="w-full flex items-center justify-between p-2 bg-gray-800 hover:bg-gray-700 rounded-md transition-colors"
                            >
                              <span className="text-sm text-gray-200">
                                📄 Page {pageNumber} (
                                {highlightsByPage[pageNumber].length}{' '}
                                {highlightsByPage[pageNumber].length === 1
                                  ? 'highlight'
                                  : 'highlights'}
                                )
                              </span>
                              <svg
                                className={`w-4 h-4 text-gray-400 transition-transform ${
                                  expandedPages.has(pageNumber)
                                    ? 'rotate-180'
                                    : ''
                                }`}
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M19 9l-7 7-7-7"
                                />
                              </svg>
                            </button>

                            {expandedPages.has(pageNumber) && (
                              <div className="mt-2 ml-4 space-y-2">
                                {highlightsByPage[pageNumber].map(highlight => (
                                  <HighlightItem
                                    key={highlight.id}
                                    highlight={highlight}
                                    isSelected={
                                      selectedHighlightId === highlight.id
                                    }
                                    isCurrent={false}
                                    onSelect={() =>
                                      handleHighlightClick(highlight)
                                    }
                                    onDelete={() =>
                                      handleDeleteHighlight(highlight.id)
                                    }
                                    onColorChange={color =>
                                      handleColorChange(highlight.id, color)
                                    }
                                    onJumpToPage={() =>
                                      onPageJump?.(highlight.pageNumber)
                                    }
                                    formatDate={formatDate}
                                    getColorName={getColorName}
                                  />
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              // Chronological view (newest/oldest)
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                  All Highlights (
                  {sortBy === 'newest' ? 'Newest First' : 'Oldest First'})
                </h4>
                <div className="space-y-2">
                  {filteredHighlights.map(highlight => (
                    <HighlightItem
                      key={highlight.id}
                      highlight={highlight}
                      isSelected={selectedHighlightId === highlight.id}
                      isCurrent={highlight.pageNumber === currentPage}
                      onSelect={() => handleHighlightClick(highlight)}
                      onDelete={() => handleDeleteHighlight(highlight.id)}
                      onColorChange={color =>
                        handleColorChange(highlight.id, color)
                      }
                      onJumpToPage={() => onPageJump?.(highlight.pageNumber)}
                      formatDate={formatDate}
                      getColorName={getColorName}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Individual highlight item component
interface HighlightItemProps {
  highlight: Highlight;
  isSelected: boolean;
  isCurrent: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onColorChange: (color: HighlightColor) => void;
  onJumpToPage: () => void;
  formatDate: (date: string) => string;
  getColorName: (color: HighlightColor) => string;
}

function HighlightItem({
  highlight,
  isSelected,
  isCurrent,
  onSelect,
  onDelete,
  onColorChange,
  onJumpToPage,
  formatDate,
  getColorName,
}: HighlightItemProps) {
  const [showColorPicker, setShowColorPicker] = useState(false);

  // Close color picker when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setShowColorPicker(false);
    };

    if (showColorPicker) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showColorPicker]);

  const truncatedText =
    highlight.selectedText.length > 100
      ? highlight.selectedText.substring(0, 100) + '...'
      : highlight.selectedText;

  return (
    <div
      className={`p-3 rounded-md border transition-all cursor-pointer ${
        isSelected
          ? 'border-blue-500 bg-blue-900/30'
          : 'border-gray-700 bg-gray-800 hover:bg-gray-750'
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start gap-3">
        {/* Color indicator */}
        <div
          className="w-3 h-3 rounded-full mt-1 flex-shrink-0 border border-gray-600"
          style={{ backgroundColor: highlight.color }}
          title={getColorName(highlight.color)}
        />

        <div className="flex-1 min-w-0">
          {/* Highlight text */}
          <p className="text-sm text-gray-200 leading-relaxed mb-2">
            "{truncatedText}"
          </p>

          {/* Metadata */}
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>
              {!isCurrent && `Page ${highlight.pageNumber} • `}
              {formatDate(highlight.createdAt.toString())}
            </span>

            <div className="flex items-center gap-1">
              {/* Color change button */}
              <div className="relative">
                <button
                  onClick={e => {
                    e.stopPropagation();
                    e.preventDefault();
                    setShowColorPicker(!showColorPicker);
                  }}
                  className="p-1 hover:bg-gray-600 rounded transition-colors"
                  title="Change color"
                >
                  🎨
                </button>

                {showColorPicker && (
                  <div className="absolute right-0 top-6 z-20 bg-gray-800 border border-gray-600 rounded-lg p-2 shadow-xl min-w-max">
                    <div className="grid grid-cols-4 gap-1 w-max">
                      {Object.values(HighlightColor).map(color => (
                        <button
                          key={color}
                          onClick={e => {
                            e.stopPropagation();
                            onColorChange(color);
                            setShowColorPicker(false);
                          }}
                          className="w-6 h-6 rounded border-2 border-gray-600 hover:border-gray-400 transition-colors flex-shrink-0"
                          style={{ backgroundColor: color }}
                          title={getColorName(color)}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Jump to page button (only for non-current pages) */}
              {!isCurrent && (
                <button
                  onClick={e => {
                    e.stopPropagation();
                    onJumpToPage();
                  }}
                  className="p-1 hover:bg-gray-600 rounded transition-colors"
                  title={`Jump to page ${highlight.pageNumber}`}
                >
                  📄
                </button>
              )}

              {/* Delete button */}
              <button
                onClick={e => {
                  e.stopPropagation();
                  onDelete();
                }}
                className="p-1 hover:bg-red-600 rounded transition-colors"
                title="Delete highlight"
              >
                🗑️
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
