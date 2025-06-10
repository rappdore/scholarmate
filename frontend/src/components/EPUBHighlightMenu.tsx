import React from 'react';
import type { HighlightColor } from '../utils/epubHighlights';

interface EPUBHighlightMenuProps {
  position: { x: number; y: number };
  onHighlight: (color: HighlightColor) => void;
  onClose: () => void;
  selectedText: string;
}

const HIGHLIGHT_COLORS: Array<{
  color: HighlightColor;
  label: string;
  className: string;
}> = [
  { color: 'yellow', label: 'Yellow', className: 'color-yellow' },
  { color: 'blue', label: 'Blue', className: 'color-blue' },
  { color: 'green', label: 'Green', className: 'color-green' },
  { color: 'pink', label: 'Pink', className: 'color-pink' },
  { color: 'orange', label: 'Orange', className: 'color-orange' },
];

export default function EPUBHighlightMenu({
  position,
  onHighlight,
  onClose,
  selectedText,
}: EPUBHighlightMenuProps) {
  // Calculate position to keep menu within viewport
  const [adjustedPosition, setAdjustedPosition] = React.useState(position);

  React.useEffect(() => {
    const menuWidth = 200; // Approximate menu width
    const menuHeight = 40; // Approximate menu height
    const padding = 10;

    let x = position.x;
    let y = position.y;

    // Adjust horizontal position
    if (x + menuWidth > window.innerWidth - padding) {
      x = window.innerWidth - menuWidth - padding;
    }
    if (x < padding) {
      x = padding;
    }

    // Adjust vertical position
    if (y + menuHeight > window.innerHeight - padding) {
      y = position.y - menuHeight - 10; // Position above selection
    }
    if (y < padding) {
      y = padding;
    }

    setAdjustedPosition({ x, y });
  }, [position]);

  // Close menu when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element;
      if (!target.closest('.epub-highlight-menu')) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  // Close menu on escape key
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleColorClick = (color: HighlightColor) => {
    onHighlight(color);
    onClose();
  };

  // Truncate selected text for display
  const displayText =
    selectedText.length > 50
      ? selectedText.substring(0, 47) + '...'
      : selectedText;

  return (
    <div
      className="epub-highlight-menu"
      style={{
        left: adjustedPosition.x,
        top: adjustedPosition.y,
      }}
    >
      {/* Selected text preview */}
      <div
        className="text-xs text-gray-300 max-w-32 overflow-hidden whitespace-nowrap text-ellipsis mr-2"
        title={selectedText}
      >
        "{displayText}"
      </div>

      {/* Color selection buttons */}
      {HIGHLIGHT_COLORS.map(({ color, label, className }) => (
        <button
          key={color}
          className={className}
          title={`Highlight in ${label}`}
          onClick={() => handleColorClick(color)}
          aria-label={`Highlight selected text in ${label.toLowerCase()}`}
        >
          ✓
        </button>
      ))}

      {/* Close button */}
      <button
        className="delete-button"
        title="Cancel"
        onClick={onClose}
        aria-label="Cancel highlighting"
      >
        ✕
      </button>
    </div>
  );
}
