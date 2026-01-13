import { DEFAULT_GRAPH_CONFIG, RELATIONSHIP_TYPES } from '../../types/graph';
import { formatRelationshipType } from '../../utils/graphUtils';

interface GraphLegendProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export function GraphLegend({ collapsed = false, onToggle }: GraphLegendProps) {
  return (
    <div className="bg-gray-800/90 backdrop-blur border border-gray-700 rounded-lg overflow-hidden">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full px-3 py-2 flex items-center justify-between text-sm text-gray-300 hover:bg-gray-700/50"
      >
        <span>Legend</span>
        <span>{collapsed ? '▸' : '▾'}</span>
      </button>

      {/* Content */}
      {!collapsed && (
        <div className="px-3 pb-3 space-y-3">
          {/* Node sizes */}
          <div>
            <h4 className="text-xs text-gray-400 mb-2">
              Node Size = Importance
            </h4>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1">
                <div
                  className="rounded-full bg-gray-700 border-2 border-indigo-500"
                  style={{ width: 16, height: 16 }}
                />
                <span className="text-xs text-gray-500">Low</span>
              </div>
              <div className="flex items-center gap-1">
                <div
                  className="rounded-full bg-gray-700 border-2 border-indigo-500"
                  style={{ width: 28, height: 28 }}
                />
                <span className="text-xs text-gray-500">High</span>
              </div>
            </div>
          </div>

          {/* Edge colors */}
          <div>
            <h4 className="text-xs text-gray-400 mb-2">
              Edge Color = Relationship Type
            </h4>
            <div className="grid grid-cols-2 gap-1">
              {RELATIONSHIP_TYPES.map(type => (
                <div key={type} className="flex items-center gap-2">
                  <div
                    className="w-4 h-0.5 rounded"
                    style={{
                      backgroundColor: DEFAULT_GRAPH_CONFIG.edgeColors[type],
                    }}
                  />
                  <span className="text-xs text-gray-400">
                    {formatRelationshipType(type)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Interaction hints */}
          <div className="pt-2 border-t border-gray-700">
            <h4 className="text-xs text-gray-400 mb-1">Interactions</h4>
            <ul className="text-xs text-gray-500 space-y-0.5">
              <li>• Scroll to zoom</li>
              <li>• Drag background to pan</li>
              <li>• Drag node to reposition</li>
              <li>• Click node/edge for details</li>
              <li>• Double-click to open in reader</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
