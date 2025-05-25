import React, { useState, useRef, useCallback, useEffect } from 'react';

interface ResizablePanelsProps {
  leftPanel: React.ReactNode;
  rightTopPanel: React.ReactNode;
  rightBottomPanel: React.ReactNode;
}

export default function ResizablePanels({
  leftPanel,
  rightTopPanel,
  rightBottomPanel,
}: ResizablePanelsProps) {
  // Panel sizes as percentages
  const [leftWidth, setLeftWidth] = useState(50); // Left panel width (0-100)
  const [rightTopHeight, setRightTopHeight] = useState(60); // Right top panel height (0-100)

  // Dragging states
  const [isDraggingVertical, setIsDraggingVertical] = useState(false);
  const [isDraggingHorizontal, setIsDraggingHorizontal] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Load saved sizes from localStorage
  useEffect(() => {
    const savedLeftWidth = localStorage.getItem('pdf-reader-left-width');
    const savedRightTopHeight = localStorage.getItem(
      'pdf-reader-right-top-height'
    );

    if (savedLeftWidth) {
      setLeftWidth(Number(savedLeftWidth));
    }
    if (savedRightTopHeight) {
      setRightTopHeight(Number(savedRightTopHeight));
    }
  }, []);

  // Save sizes to localStorage
  useEffect(() => {
    localStorage.setItem('pdf-reader-left-width', leftWidth.toString());
  }, [leftWidth]);

  useEffect(() => {
    localStorage.setItem(
      'pdf-reader-right-top-height',
      rightTopHeight.toString()
    );
  }, [rightTopHeight]);

  // Handle vertical splitter (between left and right panels)
  const handleVerticalMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingVertical(true);
  }, []);

  // Handle horizontal splitter (between right panels)
  const handleHorizontalMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingHorizontal(true);
  }, []);

  // Handle mouse move for resizing
  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();

      if (isDraggingVertical) {
        const newLeftWidth =
          ((e.clientX - containerRect.left) / containerRect.width) * 100;
        setLeftWidth(Math.max(20, Math.min(80, newLeftWidth))); // Clamp between 20% and 80%
      }

      if (isDraggingHorizontal) {
        const rightPanelRect = containerRef.current
          .querySelector('.right-panel')
          ?.getBoundingClientRect();
        if (rightPanelRect) {
          const newRightTopHeight =
            ((e.clientY - rightPanelRect.top) / rightPanelRect.height) * 100;
          setRightTopHeight(Math.max(20, Math.min(80, newRightTopHeight))); // Clamp between 20% and 80%
        }
      }
    },
    [isDraggingVertical, isDraggingHorizontal]
  );

  // Handle mouse up to stop dragging
  const handleMouseUp = useCallback(() => {
    setIsDraggingVertical(false);
    setIsDraggingHorizontal(false);
  }, []);

  // Add global mouse event listeners
  useEffect(() => {
    if (isDraggingVertical || isDraggingHorizontal) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = isDraggingVertical
        ? 'ew-resize'
        : 'ns-resize';
      document.body.style.userSelect = 'none';

      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
    }
  }, [
    isDraggingVertical,
    isDraggingHorizontal,
    handleMouseMove,
    handleMouseUp,
  ]);

  return (
    <div ref={containerRef} className="flex-1 flex h-full">
      {/* Left Panel */}
      <div
        className="border-r border-gray-700 flex flex-col"
        style={{ width: `${leftWidth}%` }}
      >
        <div className="h-full overflow-hidden">{leftPanel}</div>
      </div>

      {/* Vertical Splitter */}
      <div
        className="w-1 bg-gray-700 hover:bg-gray-600 cursor-ew-resize flex-shrink-0 relative group"
        onMouseDown={handleVerticalMouseDown}
      >
        <div className="absolute inset-0 w-3 -ml-1" />
        <div className="absolute inset-y-0 left-0 w-1 bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Right Panel Container */}
      <div
        className="flex flex-col right-panel"
        style={{ width: `${100 - leftWidth}%` }}
      >
        {/* Right Top Panel */}
        <div
          className="border-b border-gray-700 overflow-hidden"
          style={{ height: `${rightTopHeight}%` }}
        >
          {rightTopPanel}
        </div>

        {/* Horizontal Splitter */}
        <div
          className="h-1 bg-gray-700 hover:bg-gray-600 cursor-ns-resize flex-shrink-0 relative group"
          onMouseDown={handleHorizontalMouseDown}
        >
          <div className="absolute inset-0 h-3 -mt-1" />
          <div className="absolute inset-x-0 top-0 h-1 bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        {/* Right Bottom Panel */}
        <div
          className="overflow-hidden"
          style={{ height: `${100 - rightTopHeight}%` }}
        >
          {rightBottomPanel}
        </div>
      </div>
    </div>
  );
}
