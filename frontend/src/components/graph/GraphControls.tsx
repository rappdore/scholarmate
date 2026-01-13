import type { RelationshipType } from '../../types/knowledge';
import type { GraphFilterState } from '../../types/graph';
import { DEFAULT_GRAPH_CONFIG, RELATIONSHIP_TYPES } from '../../types/graph';
import { formatRelationshipType } from '../../utils/graphUtils';

interface GraphControlsProps {
  filter: GraphFilterState;
  onFilterChange: (updates: Partial<GraphFilterState>) => void;
  onReset: () => void;
  sections: string[] | number[];
  bookType: 'epub' | 'pdf';
  nodeCount: number;
  edgeCount: number;
}

export function GraphControls({
  filter,
  onFilterChange,
  onReset,
  sections,
  bookType,
  nodeCount,
  edgeCount,
}: GraphControlsProps) {
  const handleRelationshipToggle = (type: RelationshipType) => {
    const current = filter.relationshipTypes;
    const newTypes = current.includes(type)
      ? current.filter(t => t !== type)
      : [...current, type];
    onFilterChange({ relationshipTypes: newTypes });
  };

  const handleSelectAllRelationships = () => {
    onFilterChange({ relationshipTypes: [...RELATIONSHIP_TYPES] });
  };

  const handleSelectNoneRelationships = () => {
    onFilterChange({ relationshipTypes: [] });
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-4">
      {/* Stats */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-400">
          Showing: <span className="text-gray-200">{nodeCount} concepts</span>,{' '}
          <span className="text-gray-200">{edgeCount} relationships</span>
        </span>
        <button
          onClick={onReset}
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          Reset Filters
        </button>
      </div>

      {/* Search */}
      <div>
        <label className="block text-xs text-gray-400 mb-1">
          Search Concepts
        </label>
        <input
          type="text"
          value={filter.searchQuery}
          onChange={e => onFilterChange({ searchQuery: e.target.value })}
          placeholder="Search by name or definition..."
          className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-md text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Importance Filter */}
      <div>
        <label className="block text-xs text-gray-400 mb-1">
          Minimum Importance: {filter.minImportance}
        </label>
        <input
          type="range"
          min={1}
          max={5}
          value={filter.minImportance}
          onChange={e =>
            onFilterChange({ minImportance: parseInt(e.target.value) })
          }
          className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>1</span>
          <span>2</span>
          <span>3</span>
          <span>4</span>
          <span>5</span>
        </div>
      </div>

      {/* Relationship Type Filters */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs text-gray-400">Relationship Types</label>
          <div className="flex gap-2">
            <button
              onClick={handleSelectAllRelationships}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              All
            </button>
            <button
              onClick={handleSelectNoneRelationships}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              None
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {RELATIONSHIP_TYPES.map(type => {
            const isActive = filter.relationshipTypes.includes(type);
            const color = DEFAULT_GRAPH_CONFIG.edgeColors[type];
            return (
              <button
                key={type}
                onClick={() => handleRelationshipToggle(type)}
                className={`px-2 py-1 text-xs rounded border transition-colors ${
                  isActive
                    ? 'border-transparent text-white'
                    : 'border-gray-600 text-gray-500 hover:text-gray-400'
                }`}
                style={{
                  backgroundColor: isActive ? color : 'transparent',
                }}
              >
                {formatRelationshipType(type)}
              </button>
            );
          })}
        </div>
      </div>

      {/* Section Filter (for EPUB) */}
      {bookType === 'epub' && sections.length > 0 && (
        <div>
          <label className="block text-xs text-gray-400 mb-1">
            Filter by Section
          </label>
          <select
            multiple
            value={filter.navIds}
            onChange={e => {
              const selected = Array.from(
                e.target.selectedOptions,
                opt => opt.value
              );
              onFilterChange({ navIds: selected });
            }}
            className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-md text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            size={Math.min(5, (sections as string[]).length)}
          >
            {(sections as string[]).map(navId => (
              <option key={navId} value={navId} className="py-1">
                {navId}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500 mt-1">
            Hold Ctrl/Cmd to select multiple. Empty = show all.
          </p>
        </div>
      )}

      {/* Page Range Filter (for PDF) */}
      {bookType === 'pdf' && sections.length > 0 && (
        <div>
          <label className="block text-xs text-gray-400 mb-1">
            Filter by Page Range
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              placeholder="From"
              value={filter.pageRange?.[0] || ''}
              onChange={e => {
                const start = parseInt(e.target.value) || 1;
                const end =
                  filter.pageRange?.[1] || Math.max(...(sections as number[]));
                onFilterChange({ pageRange: [start, end] });
              }}
              className="w-20 px-2 py-1 bg-gray-900 border border-gray-600 rounded text-sm text-gray-200"
            />
            <span className="text-gray-500">to</span>
            <input
              type="number"
              min={1}
              placeholder="To"
              value={filter.pageRange?.[1] || ''}
              onChange={e => {
                const start = filter.pageRange?.[0] || 1;
                const end =
                  parseInt(e.target.value) ||
                  Math.max(...(sections as number[]));
                onFilterChange({ pageRange: [start, end] });
              }}
              className="w-20 px-2 py-1 bg-gray-900 border border-gray-600 rounded text-sm text-gray-200"
            />
            <button
              onClick={() => onFilterChange({ pageRange: null })}
              className="text-xs text-gray-400 hover:text-gray-300"
            >
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
