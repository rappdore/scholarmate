import React, { useState } from 'react';
import type { BookStatus } from '../types/pdf';
import type { Document } from '../types/document';
import { isPDFDocument } from '../types/document';

interface BookActionMenuProps {
  pdf: Document;
  onStatusChange: (status: BookStatus) => void;
  onDelete: () => void;
  isVisible: boolean;
}

const BookActionMenu: React.FC<BookActionMenuProps> = ({
  pdf,
  onStatusChange,
  onDelete,
  isVisible,
}) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const statusOptions: { value: BookStatus; label: string; icon: string }[] = [
    { value: 'new', label: 'Mark as New', icon: '📚' },
    { value: 'reading', label: 'Mark as Reading', icon: '📖' },
    { value: 'finished', label: 'Mark as Finished', icon: '✅' },
  ];

  const handleStatusChange = (status: BookStatus) => {
    onStatusChange(status);
  };

  const handleDeleteClick = () => {
    if (showDeleteConfirm) {
      onDelete();
      setShowDeleteConfirm(false);
    } else {
      setShowDeleteConfirm(true);
      // Auto-cancel after 3 seconds
      setTimeout(() => setShowDeleteConfirm(false), 3000);
    }
  };

  // Generate the correct statistics URL based on document type
  const getStatisticsUrl = () => {
    if (isPDFDocument(pdf)) {
      return `/statistics/${pdf.id}`;
    } else {
      return `/statistics/epub/${pdf.id}`;
    }
  };

  if (!isVisible) return null;

  return (
    <div className="absolute top-2 right-2 bg-slate-800/95 backdrop-blur-sm rounded-lg shadow-xl border border-slate-700/50 py-1 z-10 min-w-[160px]">
      {/* Status Options */}
      <div className="px-2 py-1">
        <div className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-1">
          Status
        </div>
        {statusOptions.map(option => {
          const isCurrentStatus =
            (pdf.manual_status || pdf.computed_status) === option.value;

          return (
            <button
              key={option.value}
              onClick={() => handleStatusChange(option.value)}
              disabled={isCurrentStatus}
              className={`
                w-full text-left px-2 py-1 rounded text-sm flex items-center space-x-2 transition-colors
                ${
                  isCurrentStatus
                    ? 'bg-purple-500/20 text-purple-200 cursor-default border border-purple-400/30'
                    : 'hover:bg-slate-700/50 text-slate-200 hover:text-slate-100'
                }
              `}
            >
              <span>{option.icon}</span>
              <span>{option.label}</span>
              {isCurrentStatus && (
                <span className="ml-auto text-purple-400">
                  <svg
                    className="w-3 h-3"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="border-t border-slate-600/50 my-1"></div>

      {/* Statistics Option */}
      <div className="px-2 py-1">
        <button
          onClick={() => window.open(getStatisticsUrl(), '_blank')}
          className="w-full text-left px-2 py-1 rounded text-sm flex items-center space-x-2 transition-colors hover:bg-slate-700/50 text-slate-200 hover:text-slate-100"
        >
          <span>📊</span>
          <span>View Statistics</span>
        </button>
      </div>

      <div className="border-t border-slate-600/50 my-1"></div>

      {/* Delete Option */}
      <div className="px-2 py-1">
        <button
          onClick={handleDeleteClick}
          className={`
            w-full text-left px-2 py-1 rounded text-sm flex items-center space-x-2 transition-colors
            ${
              showDeleteConfirm
                ? 'bg-red-500/20 text-red-300 hover:bg-red-500/30 border border-red-400/30'
                : 'hover:bg-slate-700/50 text-red-400 hover:text-red-300'
            }
          `}
        >
          <span>🗑️</span>
          <span>{showDeleteConfirm ? 'Confirm Delete' : 'Delete Book'}</span>
        </button>
        {showDeleteConfirm && (
          <div className="text-xs text-slate-400 mt-1 px-2">
            Click again to confirm
          </div>
        )}
      </div>
    </div>
  );
};

export default BookActionMenu;
