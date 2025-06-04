import React, { useState, useRef, useCallback, useEffect } from 'react';

interface SimpleResizablePanelsProps {
  leftPanel: React.ReactNode;
  rightPanel: React.ReactNode;
}

export default function SimpleResizablePanels({
  leftPanel,
  rightPanel,
}: SimpleResizablePanelsProps) {
  // Panel sizes as percentages
  const [leftWidth, setLeftWidth] = useState(50); // Left panel width (0-100)

  // Dragging states
  const [isDragging, setIsDragging] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Load saved sizes from localStorage
  useEffect(() => {
    const savedLeftWidth = localStorage.getItem('pdf-reader-simple-left-width');

    if (savedLeftWidth) {
      setLeftWidth(Number(savedLeftWidth));
    }
  }, []);

  // Save sizes to localStorage
  useEffect(() => {
    localStorage.setItem('pdf-reader-simple-left-width', leftWidth.toString());
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
      setLeftWidth(Math.max(20, Math.min(80, newLeftWidth))); // Clamp between 20% and 80%
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
        className="border-r border-gray-700 flex flex-col"
        style={{ width: `${leftWidth}%` }}
      >
        <div className="h-full overflow-auto">{leftPanel}</div>
      </div>

      {/* Vertical Splitter */}
      <div
        className="w-1 bg-gray-700 hover:bg-gray-600 cursor-ew-resize flex-shrink-0 relative group"
        onMouseDown={handleMouseDown}
      >
        <div className="absolute inset-0 w-3 -ml-1" />
        <div className="absolute inset-y-0 left-0 w-1 bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Right Panel */}
      <div className="flex flex-col" style={{ width: `${100 - leftWidth}%` }}>
        <div className="h-full overflow-auto">{rightPanel}</div>
      </div>
    </div>
  );
}
