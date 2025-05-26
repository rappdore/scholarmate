import React, { useState } from 'react';
import type { Highlight, HighlightCoordinates } from '../types/highlights';

interface HighlightOverlayProps {
  highlights: Highlight[];
  pageNumber: number;
  scale: number;
  selectedHighlightId?: string;
  onHighlightClick?: (highlight: Highlight) => void;
  onHighlightDelete?: (highlightId: string) => void;
}

export default function HighlightOverlay({
  highlights,
  pageNumber,
  scale,
  selectedHighlightId,
  onHighlightClick,
  onHighlightDelete,
}: HighlightOverlayProps) {
  // Filter highlights for current page
  const pageHighlights = highlights.filter(h => h.pageNumber === pageNumber);

  if (pageHighlights.length === 0) {
    return null;
  }

  return (
    <div className="absolute inset-0 pointer-events-none">
      {pageHighlights.map(highlight =>
        highlight.coordinates.map((coord, index) => (
          <HighlightRect
            key={`${highlight.id}-${index}`}
            highlight={highlight}
            coordinates={coord}
            currentScale={scale}
            isSelected={selectedHighlightId === highlight.id}
            onClick={() => onHighlightClick?.(highlight)}
            onDelete={() => onHighlightDelete?.(highlight.id)}
          />
        ))
      )}
    </div>
  );
}

interface HighlightRectProps {
  highlight: Highlight;
  coordinates: HighlightCoordinates;
  currentScale: number;
  isSelected?: boolean;
  onClick?: () => void;
  onDelete?: () => void;
}

function HighlightRect({
  highlight,
  coordinates,
  currentScale,
  isSelected = false,
  onClick,
  onDelete,
}: HighlightRectProps) {
  const [isHovered, setIsHovered] = useState(false);

  // Calculate scaled coordinates
  // The coordinates were stored at a specific zoom level, so we need to adjust for current zoom
  const scaleRatio = currentScale / coordinates.zoom;

  const scaledX = coordinates.x * scaleRatio;
  const scaledY = coordinates.y * scaleRatio;
  const scaledWidth = coordinates.width * scaleRatio;
  const scaledHeight = coordinates.height * scaleRatio;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onClick?.();
  };

  const handleRightClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDelete?.();
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDelete?.();
  };

  return (
    <div
      className={`absolute pointer-events-auto cursor-pointer hover:opacity-80 transition-all group ${
        isSelected ? 'ring-2 ring-blue-400 ring-opacity-70' : ''
      }`}
      style={{
        left: `${scaledX}px`,
        top: `${scaledY}px`,
        width: `${scaledWidth}px`,
        height: `${scaledHeight}px`,
        backgroundColor: highlight.color,
        opacity: isSelected ? 0.5 : 0.3,
        // Note: Removed mixBlendMode as it was interfering with mouse events
        zIndex: 10,
      }}
      onClick={handleClick}
      onContextMenu={handleRightClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      title={`"${highlight.selectedText.substring(0, 50)}${highlight.selectedText.length > 50 ? '...' : ''}" - Click to select, right-click or use × button to delete${isSelected ? ' (Selected - Press Delete key to remove)' : ''}`}
    >
      {/* Delete button that appears on hover */}
      {isHovered && (
        <button
          onClick={handleDeleteClick}
          className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 hover:bg-red-600 text-white text-xs rounded-full flex items-center justify-center shadow-lg transition-colors z-20"
          title="Delete highlight"
        >
          ×
        </button>
      )}
    </div>
  );
}
