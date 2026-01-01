import React from 'react';
import type { HighlightColor } from '../utils/epubHighlights';

interface EPUBHighlightMenuProps {
  position: { x: number; y: number };
  onHighlight: (color: HighlightColor) => void;
  onClose: () => void;
  selectedText: string;
  onReadAloud?: (text: string) => void;
  onContinueReading?: (text: string) => void;
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
  onReadAloud,
  onContinueReading,
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

      {/* Read Aloud button - reads only selected text */}
      {onReadAloud && (
        <button
          className="tts-read-aloud-btn"
          title="Read Selection"
          onClick={() => {
            onReadAloud(selectedText);
            onClose();
          }}
          aria-label="Read selected text aloud"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
          </svg>
        </button>
      )}

      {/* Continue Reading button - reads from selection to end of chapter */}
      {onContinueReading && (
        <button
          className="tts-continue-reading-btn"
          title="Continue Reading from Here"
          onClick={() => {
            onContinueReading(selectedText);
            onClose();
          }}
          aria-label="Continue reading from selection to end of chapter"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
          </svg>
        </button>
      )}
    </div>
  );
}
