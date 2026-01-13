import type { GraphData, RelationshipType } from '../types/knowledge';
import type {
  D3Node,
  D3Link,
  D3GraphData,
  GraphFilterState,
  NodeSizeConfig,
  EdgeColorConfig,
} from '../types/graph';
import { DEFAULT_GRAPH_CONFIG } from '../types/graph';

/**
 * Convert backend GraphData to D3-compatible format
 */
export function toD3Graph(data: GraphData): D3GraphData {
  const nodes: D3Node[] = data.nodes.map(node => ({
    ...node,
    // D3 will populate x, y during simulation
  }));

  const links: D3Link[] = data.edges.map(edge => ({
    id: edge.id,
    source: edge.source, // Will be resolved to node reference by D3
    target: edge.target,
    type: edge.type,
    description: edge.description,
    weight: edge.weight,
  }));

  return { nodes, links };
}

/**
 * Calculate node radius based on importance (1-5)
 */
export function getNodeRadius(
  importance: number,
  config: NodeSizeConfig
): number {
  const { minRadius, maxRadius } = config;
  // Linear interpolation: importance 1 -> minRadius, importance 5 -> maxRadius
  const normalized = (importance - 1) / 4; // 0 to 1
  return minRadius + normalized * (maxRadius - minRadius);
}

/**
 * Get edge color based on relationship type
 */
export function getEdgeColor(
  type: RelationshipType,
  colors: EdgeColorConfig
): string {
  return colors[type] || colors['related-to'];
}

/**
 * Get edge stroke width based on weight
 */
export function getEdgeWidth(weight: number): number {
  // Weight typically 0.5 to 2.0, map to stroke width 1 to 3
  return Math.max(1, Math.min(3, weight * 1.5));
}

/**
 * Filter nodes based on filter state
 */
export function filterNodes(
  nodes: D3Node[],
  filter: GraphFilterState
): D3Node[] {
  return nodes.filter(node => {
    // Importance filter
    if (node.importance < filter.minImportance) {
      return false;
    }

    // Search filter
    if (filter.searchQuery) {
      const query = filter.searchQuery.toLowerCase();
      const nameMatch = node.name.toLowerCase().includes(query);
      const defMatch = node.definition?.toLowerCase().includes(query);
      if (!nameMatch && !defMatch) {
        return false;
      }
    }

    // Section filter (EPUB nav_id)
    if (filter.navIds.length > 0 && node.nav_id) {
      if (!filter.navIds.includes(node.nav_id)) {
        return false;
      }
    }

    // Page range filter (PDF)
    if (filter.pageRange && node.page_num !== null) {
      const [start, end] = filter.pageRange;
      if (node.page_num < start || node.page_num > end) {
        return false;
      }
    }

    return true;
  });
}

/**
 * Filter links to only include those between visible nodes
 */
export function filterLinks(
  links: D3Link[],
  visibleNodeIds: Set<number>,
  relationshipTypes: RelationshipType[]
): D3Link[] {
  return links.filter(link => {
    // Get source/target IDs (handle both resolved and unresolved)
    const sourceId =
      typeof link.source === 'number' ? link.source : link.source.id;
    const targetId =
      typeof link.target === 'number' ? link.target : link.target.id;

    // Both endpoints must be visible
    if (!visibleNodeIds.has(sourceId) || !visibleNodeIds.has(targetId)) {
      return false;
    }

    // Relationship type filter
    if (!relationshipTypes.includes(link.type)) {
      return false;
    }

    return true;
  });
}

/**
 * Apply filters to graph data
 */
export function applyFilters(
  data: D3GraphData,
  filter: GraphFilterState
): D3GraphData {
  const filteredNodes = filterNodes(data.nodes, filter);
  const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
  const filteredLinks = filterLinks(
    data.links,
    visibleNodeIds,
    filter.relationshipTypes
  );

  return {
    nodes: filteredNodes,
    links: filteredLinks,
  };
}

/**
 * Find nodes connected to a given node (for highlighting paths)
 */
export function getConnectedNodes(
  nodeId: number,
  links: D3Link[],
  depth: number = 1
): Set<number> {
  const connected = new Set<number>([nodeId]);

  for (let d = 0; d < depth; d++) {
    const newConnections: number[] = [];

    for (const link of links) {
      const sourceId =
        typeof link.source === 'number' ? link.source : link.source.id;
      const targetId =
        typeof link.target === 'number' ? link.target : link.target.id;

      if (connected.has(sourceId) && !connected.has(targetId)) {
        newConnections.push(targetId);
      }
      if (connected.has(targetId) && !connected.has(sourceId)) {
        newConnections.push(sourceId);
      }
    }

    newConnections.forEach(id => connected.add(id));
  }

  return connected;
}

/**
 * Find path between two nodes using BFS
 * Returns array of node IDs in the path, or null if no path exists
 */
export function findPath(
  startId: number,
  endId: number,
  links: D3Link[]
): number[] | null {
  if (startId === endId) return [startId];

  // Build adjacency list
  const adjacency = new Map<number, number[]>();
  for (const link of links) {
    const sourceId =
      typeof link.source === 'number' ? link.source : link.source.id;
    const targetId =
      typeof link.target === 'number' ? link.target : link.target.id;

    if (!adjacency.has(sourceId)) adjacency.set(sourceId, []);
    if (!adjacency.has(targetId)) adjacency.set(targetId, []);
    adjacency.get(sourceId)!.push(targetId);
    adjacency.get(targetId)!.push(sourceId);
  }

  // BFS
  const visited = new Set<number>();
  const parent = new Map<number, number>();
  const queue: number[] = [startId];
  visited.add(startId);

  while (queue.length > 0) {
    const current = queue.shift()!;

    for (const neighbor of adjacency.get(current) || []) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        parent.set(neighbor, current);

        if (neighbor === endId) {
          // Reconstruct path
          const path: number[] = [endId];
          let node = endId;
          while (parent.has(node)) {
            node = parent.get(node)!;
            path.unshift(node);
          }
          return path;
        }

        queue.push(neighbor);
      }
    }
  }

  return null; // No path found
}

/**
 * Calculate statistics about the graph
 */
export function getGraphStats(data: D3GraphData): {
  nodeCount: number;
  edgeCount: number;
  avgDegree: number;
  mostConnected: D3Node | null;
  relationshipCounts: Record<RelationshipType, number>;
} {
  const nodeCount = data.nodes.length;
  const edgeCount = data.links.length;

  // Count degree for each node
  const degreeMap = new Map<number, number>();
  for (const link of data.links) {
    const sourceId =
      typeof link.source === 'number' ? link.source : link.source.id;
    const targetId =
      typeof link.target === 'number' ? link.target : link.target.id;
    degreeMap.set(sourceId, (degreeMap.get(sourceId) || 0) + 1);
    degreeMap.set(targetId, (degreeMap.get(targetId) || 0) + 1);
  }

  const avgDegree =
    nodeCount > 0
      ? Array.from(degreeMap.values()).reduce((a, b) => a + b, 0) / nodeCount
      : 0;

  // Find most connected node
  let mostConnected: D3Node | null = null;
  let maxDegree = 0;
  for (const node of data.nodes) {
    const degree = degreeMap.get(node.id) || 0;
    if (degree > maxDegree) {
      maxDegree = degree;
      mostConnected = node;
    }
  }

  // Count relationships by type
  const relationshipCounts: Record<RelationshipType, number> = {
    explains: 0,
    contrasts: 0,
    requires: 0,
    'builds-on': 0,
    examples: 0,
    causes: 0,
    'related-to': 0,
  };
  for (const link of data.links) {
    relationshipCounts[link.type]++;
  }

  return {
    nodeCount,
    edgeCount,
    avgDegree: Math.round(avgDegree * 10) / 10,
    mostConnected,
    relationshipCounts,
  };
}

/**
 * Get unique sections (nav_ids or page numbers) from nodes
 */
export function getUniqueSections(
  nodes: D3Node[],
  bookType: 'epub' | 'pdf'
): string[] | number[] {
  if (bookType === 'epub') {
    const navIds = new Set<string>();
    for (const node of nodes) {
      if (node.nav_id) navIds.add(node.nav_id);
    }
    return Array.from(navIds).sort();
  } else {
    const pageNums = new Set<number>();
    for (const node of nodes) {
      if (node.page_num !== null) pageNums.add(node.page_num);
    }
    return Array.from(pageNums).sort((a, b) => a - b);
  }
}

/**
 * Format relationship type for display
 */
export function formatRelationshipType(type: RelationshipType): string {
  const labels: Record<RelationshipType, string> = {
    explains: 'Explains',
    contrasts: 'Contrasts',
    requires: 'Requires',
    'builds-on': 'Builds On',
    examples: 'Examples',
    causes: 'Causes',
    'related-to': 'Related To',
  };
  return labels[type] || type;
}

/**
 * Get edge color from default config (convenience function)
 */
export function getDefaultEdgeColor(type: RelationshipType): string {
  return DEFAULT_GRAPH_CONFIG.edgeColors[type];
}
