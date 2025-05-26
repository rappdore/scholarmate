import React from 'react';
import type { Highlight, HighlightCoordinates } from '../types/highlights';

interface HighlightOverlayProps {
  highlights: Highlight[];
  pageNumber: number;
  scale: number;
  onHighlightClick?: (highlight: Highlight) => void;
  onHighlightDelete?: (highlightId: string) => void;
}

export default function HighlightOverlay({
  highlights,
  pageNumber,
  scale,
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
  onClick?: () => void;
  onDelete?: () => void;
}

function HighlightRect({
  highlight,
  coordinates,
  currentScale,
  onClick,
  onDelete,
}: HighlightRectProps) {
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

  return (
    <div
      className="absolute pointer-events-auto cursor-pointer hover:opacity-80 transition-opacity"
      style={{
        left: `${scaledX}px`,
        top: `${scaledY}px`,
        width: `${scaledWidth}px`,
        height: `${scaledHeight}px`,
        backgroundColor: highlight.color,
        opacity: 0.3,
        mixBlendMode: 'multiply', // This creates a nice highlight effect
      }}
      onClick={handleClick}
      onContextMenu={handleRightClick}
      title={`"${highlight.selectedText}" - Right-click to delete`}
    />
  );
}
