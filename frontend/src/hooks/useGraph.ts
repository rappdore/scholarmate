import { useState, useEffect, useCallback, useMemo } from 'react';
import { knowledgeService } from '../services/knowledgeApi';
import type { GraphData } from '../types/knowledge';
import type { D3GraphData, GraphFilterState } from '../types/graph';
import { DEFAULT_FILTER_STATE } from '../types/graph';
import {
  toD3Graph,
  applyFilters,
  getGraphStats,
  getUniqueSections,
} from '../utils/graphUtils';

interface UseGraphOptions {
  bookId: number;
  bookType: 'epub' | 'pdf';
  autoLoad?: boolean;
}

interface UseGraphReturn {
  // Data
  rawData: GraphData | null;
  graphData: D3GraphData | null; // Filtered data for rendering
  isLoading: boolean;
  error: string | null;

  // Filter state
  filter: GraphFilterState;
  setFilter: (updates: Partial<GraphFilterState>) => void;
  resetFilters: () => void;

  // Stats
  stats: ReturnType<typeof getGraphStats> | null;
  sections: string[] | number[];

  // Actions
  loadGraph: () => Promise<void>;
  selectNode: (nodeId: number | null) => void;
  selectEdge: (edgeId: number | null) => void;
  highlightNode: (nodeId: number | null) => void;
  searchNodes: (query: string) => void;
}

export function useGraph({
  bookId,
  bookType,
  autoLoad = true,
}: UseGraphOptions): UseGraphReturn {
  // Raw data from API
  const [rawData, setRawData] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [filter, setFilterState] =
    useState<GraphFilterState>(DEFAULT_FILTER_STATE);

  // Load graph data
  const loadGraph = useCallback(async () => {
    if (!bookId) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await knowledgeService.getGraph(bookId, bookType);
      setRawData(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load graph';
      setError(message);
      console.error('Error loading graph:', err);
    } finally {
      setIsLoading(false);
    }
  }, [bookId, bookType]);

  // Auto-load on mount
  useEffect(() => {
    if (autoLoad) {
      loadGraph();
    }
  }, [autoLoad, loadGraph]);

  // Convert and filter data
  const graphData = useMemo(() => {
    if (!rawData) return null;
    const d3Data = toD3Graph(rawData);
    return applyFilters(d3Data, filter);
  }, [rawData, filter]);

  // Calculate stats on filtered data
  const stats = useMemo(() => {
    if (!graphData) return null;
    return getGraphStats(graphData);
  }, [graphData]);

  // Get available sections for filtering
  const sections = useMemo(() => {
    if (!rawData) return [];
    const d3Data = toD3Graph(rawData);
    return getUniqueSections(d3Data.nodes, bookType);
  }, [rawData, bookType]);

  // Update filter
  const setFilter = useCallback((updates: Partial<GraphFilterState>) => {
    setFilterState(prev => ({ ...prev, ...updates }));
  }, []);

  // Reset filters
  const resetFilters = useCallback(() => {
    setFilterState(DEFAULT_FILTER_STATE);
  }, []);

  // Convenience methods
  const selectNode = useCallback(
    (nodeId: number | null) => {
      setFilter({ selectedNodeId: nodeId, selectedEdgeId: null });
    },
    [setFilter]
  );

  const selectEdge = useCallback(
    (edgeId: number | null) => {
      setFilter({ selectedEdgeId: edgeId, selectedNodeId: null });
    },
    [setFilter]
  );

  const highlightNode = useCallback(
    (nodeId: number | null) => {
      setFilter({ highlightNodeId: nodeId });
    },
    [setFilter]
  );

  const searchNodes = useCallback(
    (query: string) => {
      setFilter({ searchQuery: query });
    },
    [setFilter]
  );

  return {
    rawData,
    graphData,
    isLoading,
    error,
    filter,
    setFilter,
    resetFilters,
    stats,
    sections,
    loadGraph,
    selectNode,
    selectEdge,
    highlightNode,
    searchNodes,
  };
}
