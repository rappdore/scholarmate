import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  useParams,
  useSearchParams,
  Link,
  useNavigate,
} from 'react-router-dom';
import { useGraph } from '../hooks/useGraph';
import { ForceGraph } from '../components/graph/ForceGraph';
import { GraphControls } from '../components/graph/GraphControls';
import { NodeDetailPanel } from '../components/graph/NodeDetailPanel';
import { EdgeDetailPanel } from '../components/graph/EdgeDetailPanel';
import { GraphLegend } from '../components/graph/GraphLegend';
import type { D3Node, D3Link, GraphCallbacks } from '../types/graph';
import { getConnectedNodes } from '../utils/graphUtils';

export default function GraphPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const bookType = (searchParams.get('type') as 'epub' | 'pdf') || 'epub';

  const [legendCollapsed, setLegendCollapsed] = useState(false);
  const [selectedNode, setSelectedNode] = useState<D3Node | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<D3Link | null>(null);
  const [hoveredNode, setHoveredNode] = useState<D3Node | null>(null);
  const [dimensions, setDimensions] = useState({
    width: window.innerWidth - 320,
    height: window.innerHeight - 64,
  });

  // Update dimensions on resize
  useEffect(() => {
    const handleResize = () => {
      setDimensions({
        width: window.innerWidth - 320,
        height: window.innerHeight - 64,
      });
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const {
    graphData,
    isLoading,
    error,
    filter,
    setFilter,
    resetFilters,
    stats,
    sections,
    loadGraph,
  } = useGraph({
    bookId: parseInt(bookId || '0'),
    bookType,
  });

  // Calculate highlighted nodes (connected to hovered node)
  const highlightedNodes = useMemo(() => {
    if (!hoveredNode || !graphData) return undefined;
    return getConnectedNodes(hoveredNode.id, graphData.links, 1);
  }, [hoveredNode, graphData]);

  // Graph callbacks
  const callbacks: Partial<GraphCallbacks> = useMemo(
    () => ({
      onNodeClick: node => {
        setSelectedNode(node);
        setSelectedEdge(null);
        setFilter({ selectedNodeId: node.id });
      },
      onNodeDoubleClick: node => {
        // Navigate to reader at concept source
        if (node.nav_id && bookType === 'epub') {
          navigate(`/read/epub/${bookId}?section=${node.nav_id}`);
        } else if (node.page_num && bookType === 'pdf') {
          navigate(`/read/pdf/${bookId}?page=${node.page_num}`);
        }
      },
      onNodeHover: node => {
        setHoveredNode(node);
      },
      onEdgeClick: edge => {
        setSelectedEdge(edge);
        setSelectedNode(null);
        setFilter({ selectedEdgeId: edge.id });
      },
      onEdgeHover: () => {
        // Could add edge highlighting here
      },
      onBackgroundClick: () => {
        setSelectedNode(null);
        setSelectedEdge(null);
        setFilter({ selectedNodeId: null, selectedEdgeId: null });
      },
      onZoomChange: () => {
        // Could display zoom level or save position
      },
    }),
    [bookId, bookType, navigate, setFilter]
  );

  // Handle navigation to source
  const handleNavigateToSource = useCallback(() => {
    if (!selectedNode) return;
    if (selectedNode.nav_id && bookType === 'epub') {
      navigate(`/read/epub/${bookId}?section=${selectedNode.nav_id}`);
    } else if (selectedNode.page_num && bookType === 'pdf') {
      navigate(`/read/pdf/${bookId}?page=${selectedNode.page_num}`);
    }
  }, [selectedNode, bookId, bookType, navigate]);

  // Loading state
  if (isLoading) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <div className="animate-spin text-4xl mb-4">
            <svg
              className="w-12 h-12 mx-auto text-purple-400"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          </div>
          <p className="text-gray-400">Loading knowledge graph...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-gray-900">
        <div className="text-center max-w-md">
          <div className="text-4xl mb-4">
            <svg
              className="w-16 h-16 mx-auto text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-medium text-gray-200 mb-2">
            Error Loading Graph
          </h2>
          <p className="text-gray-400 mb-4">{error}</p>
          <button
            onClick={loadGraph}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-gray-900">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">
            <svg
              className="w-24 h-24 mx-auto text-gray-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-medium text-gray-200 mb-2">
            No Concepts Found
          </h2>
          <p className="text-gray-400 mb-4">
            This book doesn't have any extracted concepts yet. Go to the reader
            and extract concepts from sections to build the knowledge graph.
          </p>
          <Link
            to={`/read/${bookType}/${bookId}`}
            className="inline-block px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded transition-colors"
          >
            Open in Reader
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex bg-gray-900">
      {/* Left sidebar - Controls */}
      <div className="w-80 flex-shrink-0 border-r border-gray-700 p-4 overflow-y-auto">
        <div className="mb-4">
          <Link
            to={`/read/${bookType}/${bookId}`}
            className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
          >
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
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            Back to Reader
          </Link>
        </div>

        <h1 className="text-xl font-bold text-gray-200 mb-4">
          Knowledge Graph
        </h1>

        <GraphControls
          filter={filter}
          onFilterChange={setFilter}
          onReset={resetFilters}
          sections={sections}
          bookType={bookType}
          nodeCount={graphData.nodes.length}
          edgeCount={graphData.links.length}
        />

        {/* Selected item details */}
        {selectedNode && (
          <div className="mt-4">
            <NodeDetailPanel
              node={selectedNode}
              bookType={bookType}
              onClose={() => {
                setSelectedNode(null);
                setFilter({ selectedNodeId: null });
              }}
              onNavigateToSource={handleNavigateToSource}
            />
          </div>
        )}

        {selectedEdge && (
          <div className="mt-4">
            <EdgeDetailPanel
              edge={selectedEdge}
              onClose={() => {
                setSelectedEdge(null);
                setFilter({ selectedEdgeId: null });
              }}
            />
          </div>
        )}

        {/* Stats summary */}
        {stats && (
          <div className="mt-4 p-3 bg-gray-800 border border-gray-700 rounded-lg">
            <h3 className="text-xs font-medium text-gray-400 mb-2">
              Graph Statistics
            </h3>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-gray-500">Concepts:</span>{' '}
                <span className="text-gray-300">{stats.nodeCount}</span>
              </div>
              <div>
                <span className="text-gray-500">Relations:</span>{' '}
                <span className="text-gray-300">{stats.edgeCount}</span>
              </div>
              <div className="col-span-2">
                <span className="text-gray-500">Avg. connections:</span>{' '}
                <span className="text-gray-300">{stats.avgDegree}</span>
              </div>
              {stats.mostConnected && (
                <div className="col-span-2">
                  <span className="text-gray-500">Most connected:</span>{' '}
                  <span className="text-gray-300 truncate">
                    {stats.mostConnected.name}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Main graph area */}
      <div className="flex-1 relative">
        <ForceGraph
          data={graphData}
          width={dimensions.width}
          height={dimensions.height}
          callbacks={callbacks}
          highlightedNodes={highlightedNodes}
          selectedNodeId={filter.selectedNodeId}
          selectedEdgeId={filter.selectedEdgeId}
        />

        {/* Legend overlay */}
        <div className="absolute bottom-4 right-4">
          <GraphLegend
            collapsed={legendCollapsed}
            onToggle={() => setLegendCollapsed(!legendCollapsed)}
          />
        </div>

        {/* Hovered node tooltip */}
        {hoveredNode &&
          hoveredNode.x !== undefined &&
          hoveredNode.y !== undefined && (
            <div
              className="absolute bg-gray-800 border border-gray-600 rounded px-3 py-2 pointer-events-none shadow-lg z-10"
              style={{
                left: hoveredNode.x + 20,
                top: hoveredNode.y,
                maxWidth: 250,
              }}
            >
              <p className="text-sm font-medium text-gray-200">
                {hoveredNode.name}
              </p>
              {hoveredNode.definition && (
                <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                  {hoveredNode.definition}
                </p>
              )}
              <p className="text-xs text-yellow-400 mt-1">
                {'★'.repeat(hoveredNode.importance)}
                {'☆'.repeat(5 - hoveredNode.importance)}
              </p>
            </div>
          )}
      </div>
    </div>
  );
}
