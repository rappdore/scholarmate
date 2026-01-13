import type { D3Link } from '../../types/graph';
import { DEFAULT_GRAPH_CONFIG } from '../../types/graph';
import { getEdgeColor, formatRelationshipType } from '../../utils/graphUtils';

interface EdgeDetailPanelProps {
  edge: D3Link;
  onClose: () => void;
}

export function EdgeDetailPanel({ edge, onClose }: EdgeDetailPanelProps) {
  const sourceName =
    typeof edge.source === 'number'
      ? `Concept #${edge.source}`
      : edge.source.name;
  const targetName =
    typeof edge.target === 'number'
      ? `Concept #${edge.target}`
      : edge.target.name;

  const color = getEdgeColor(edge.type, DEFAULT_GRAPH_CONFIG.edgeColors);

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-lg font-medium text-gray-200">Relationship</h3>
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

      {/* Type with color */}
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: color }}
        />
        <span className="text-sm font-medium" style={{ color }}>
          {formatRelationshipType(edge.type)}
        </span>
      </div>

      {/* Concepts */}
      <div className="mb-4 p-3 bg-gray-900 rounded">
        <div className="text-sm text-gray-300 mb-2">
          <span className="text-gray-400">From: </span>
          {sourceName}
        </div>
        <div className="flex justify-center text-gray-500 my-1">
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </div>
        <div className="text-sm text-gray-300">
          <span className="text-gray-400">To: </span>
          {targetName}
        </div>
      </div>

      {/* Description */}
      {edge.description && (
        <div className="mb-4">
          <h4 className="text-xs font-medium text-gray-400 mb-1">
            Description
          </h4>
          <p className="text-sm text-gray-300">{edge.description}</p>
        </div>
      )}

      {/* Weight */}
      <div>
        <h4 className="text-xs font-medium text-gray-400 mb-1">Weight</h4>
        <p className="text-sm text-gray-400">{edge.weight.toFixed(2)}</p>
      </div>
    </div>
  );
}
