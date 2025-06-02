import React from 'react';

interface EPUBViewerProps {
  filename?: string;
}

export default function EPUBViewer({ filename }: EPUBViewerProps) {
  return (
    <div className="flex items-center justify-center h-full bg-gray-900 text-gray-300">
      <div className="text-center">
        <div className="text-6xl mb-6">📚</div>
        <h2 className="text-2xl font-bold mb-4">EPUB Viewer Coming Soon</h2>
        <p className="text-gray-400 mb-2">
          We're working on bringing you an amazing EPUB reading experience.
        </p>
        {filename && (
          <p className="text-sm text-gray-500">
            File: {decodeURIComponent(filename)}
          </p>
        )}
        <div className="mt-6 text-purple-400">
          📖 Stay tuned for chapter-based navigation and reading features!
        </div>
      </div>
    </div>
  );
}
