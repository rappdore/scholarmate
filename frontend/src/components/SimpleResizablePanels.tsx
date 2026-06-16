import React, { useState, useRef, useCallback, useEffect } from 'react';

const DEFAULT_LEFT_WIDTH = 50;
const MIN_LEFT_WIDTH = 20;
const MAX_LEFT_WIDTH = 80;
const STORAGE_KEY = 'pdf-reader-simple-left-width';

interface SimpleResizablePanelsProps {
  leftPanel: React.ReactNode;
  rightPanel: React.ReactNode;
}

function clampLeftWidth(width: number): number {
  return Math.max(MIN_LEFT_WIDTH, Math.min(MAX_LEFT_WIDTH, width));
}

function getSavedLeftWidth(): number {
  try {
    const savedLeftWidth = localStorage.getItem(STORAGE_KEY);
    if (savedLeftWidth === null || savedLeftWidth.trim() === '') {
      return DEFAULT_LEFT_WIDTH;
    }

    const parsed = Number(savedLeftWidth);
    return Number.isFinite(parsed)
      ? clampLeftWidth(parsed)
      : DEFAULT_LEFT_WIDTH;
  } catch (error) {
    console.warn('Error reading saved reader split width:', error);
    return DEFAULT_LEFT_WIDTH;
  }
}

export default function SimpleResizablePanels({
  leftPanel,
  rightPanel,
}: SimpleResizablePanelsProps) {
  // Panel sizes as percentages
  const [leftWidth, setLeftWidth] = useState(getSavedLeftWidth); // Left panel width (0-100)

  // Dragging states
  const [isDragging, setIsDragging] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Save sizes to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, leftWidth.toString());
    } catch (error) {
      console.warn('Error saving reader split width:', error);
    }
  }, [leftWidth]);

  // Handle splitter
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  // Handle mouse move for resizing
  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!containerRef.current || !isDragging) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const newLeftWidth =
        ((e.clientX - containerRect.left) / containerRect.width) * 100;
      setLeftWidth(clampLeftWidth(newLeftWidth)); // Clamp between 20% and 80%
    },
    [isDragging]
  );

  // Handle mouse up to stop dragging
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Add global mouse event listeners
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';

      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  return (
    <div ref={containerRef} className="flex-1 flex h-full">
      {/* Left Panel */}
      <div
        data-testid="reader-left-panel"
        className="border-r border-gray-700 flex flex-col"
        style={{ width: `${leftWidth}%` }}
      >
        <div className="h-full overflow-auto">{leftPanel}</div>
      </div>

      {/* Vertical Splitter */}
      <div
        data-testid="reader-splitter"
        className="w-1 bg-gray-700 hover:bg-gray-600 cursor-ew-resize flex-shrink-0 relative group"
        onMouseDown={handleMouseDown}
      >
        <div className="absolute inset-0 w-3 -ml-1" />
        <div className="absolute inset-y-0 left-0 w-1 bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Right Panel */}
      <div
        data-testid="reader-right-panel"
        className="flex flex-col"
        style={{ width: `${100 - leftWidth}%` }}
      >
        <div className="h-full overflow-auto">{rightPanel}</div>
      </div>
    </div>
  );
}
