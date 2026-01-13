import type { D3Node } from '../../types/graph';

interface NodeDetailPanelProps {
  node: D3Node;
  bookType: 'epub' | 'pdf';
  onClose: () => void;
  onNavigateToSource: () => void;
}

export function NodeDetailPanel({
  node,
  bookType,
  onClose,
  onNavigateToSource,
}: NodeDetailPanelProps) {
  const locationText =
    bookType === 'epub'
      ? node.nav_id || 'Unknown section'
      : node.page_num !== null
        ? `Page ${node.page_num}`
        : 'Unknown page';

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-lg font-medium text-gray-200">{node.name}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-300">
          <span className="sr-only">Close</span>
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Importance */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-gray-400">Importance:</span>
        <span className="text-yellow-400">
          {'★'.repeat(node.importance)}
          {'☆'.repeat(5 - node.importance)}
        </span>
      </div>

      {/* Definition */}
      {node.definition && (
        <div className="mb-4">
          <h4 className="text-xs font-medium text-gray-400 mb-1">Definition</h4>
          <p className="text-sm text-gray-300">{node.definition}</p>
        </div>
      )}

      {/* Location */}
      <div className="mb-4">
        <h4 className="text-xs font-medium text-gray-400 mb-1">Location</h4>
        <p className="text-sm text-gray-400">{locationText}</p>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-3 border-t border-gray-700">
        <button
          onClick={onNavigateToSource}
          className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded transition-colors"
        >
          View in Reader
        </button>
      </div>
    </div>
  );
}
