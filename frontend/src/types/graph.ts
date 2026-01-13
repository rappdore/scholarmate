import type { SimulationNodeDatum, SimulationLinkDatum } from 'd3';
import type { GraphNode, RelationshipType } from './knowledge';

/**
 * D3 simulation node - extends GraphNode with simulation properties
 */
export interface D3Node extends GraphNode, SimulationNodeDatum {
  // D3 adds these during simulation
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null; // Fixed x position (when dragged)
  fy?: number | null; // Fixed y position (when dragged)
}

/**
 * D3 simulation link - source/target become node references during simulation
 */
export interface D3Link extends SimulationLinkDatum<D3Node> {
  id: number;
  source: D3Node | number;
  target: D3Node | number;
  type: RelationshipType;
  description: string | null;
  weight: number;
}

/**
 * Processed graph data ready for D3
 */
export interface D3GraphData {
  nodes: D3Node[];
  links: D3Link[];
}

/**
 * Node size configuration based on importance
 */
export interface NodeSizeConfig {
  minRadius: number; // Radius for importance=1
  maxRadius: number; // Radius for importance=5
  strokeWidth: number; // Node border width
}

/**
 * Edge color configuration by relationship type
 */
export type EdgeColorConfig = Record<RelationshipType, string>;

/**
 * Graph layout configuration
 */
export interface GraphLayoutConfig {
  width: number;
  height: number;
  nodeSize: NodeSizeConfig;
  edgeColors: EdgeColorConfig;
  // Force simulation settings
  chargeStrength: number; // Node repulsion (negative = repel)
  linkDistance: number; // Target distance between linked nodes
  linkStrength: number; // How strongly links pull nodes together
  centerStrength: number; // Pull toward center
  collisionRadius: number; // Extra padding for collision detection
  alphaDecay: number; // How fast simulation cools down
}

/**
 * Filter state for the graph
 */
export interface GraphFilterState {
  searchQuery: string;
  minImportance: number; // 1-5
  relationshipTypes: RelationshipType[]; // Which types to show
  navIds: string[]; // For EPUB: which sections to show
  pageRange: [number, number] | null; // For PDF: page range filter
  highlightNodeId: number | null; // Currently highlighted node
  selectedNodeId: number | null; // Currently selected node (for details)
  selectedEdgeId: number | null; // Currently selected edge (for details)
}

/**
 * Graph interaction callbacks
 */
export interface GraphCallbacks {
  onNodeClick: (node: D3Node) => void;
  onNodeDoubleClick: (node: D3Node) => void;
  onNodeHover: (node: D3Node | null) => void;
  onEdgeClick: (edge: D3Link) => void;
  onEdgeHover: (edge: D3Link | null) => void;
  onBackgroundClick: () => void;
  onZoomChange: (transform: { k: number; x: number; y: number }) => void;
}

/**
 * Default configuration values
 */
export const DEFAULT_GRAPH_CONFIG: GraphLayoutConfig = {
  width: 800,
  height: 600,
  nodeSize: {
    minRadius: 8,
    maxRadius: 24,
    strokeWidth: 2,
  },
  edgeColors: {
    explains: '#22c55e', // Green - explanatory
    contrasts: '#ef4444', // Red - opposing
    requires: '#f59e0b', // Amber - prerequisite
    'builds-on': '#3b82f6', // Blue - builds upon
    examples: '#8b5cf6', // Purple - examples
    causes: '#ec4899', // Pink - causal
    'related-to': '#6b7280', // Gray - general relation
  },
  chargeStrength: -300,
  linkDistance: 100,
  linkStrength: 0.5,
  centerStrength: 0.05,
  collisionRadius: 10,
  alphaDecay: 0.02,
};

/**
 * All relationship types
 */
export const RELATIONSHIP_TYPES: RelationshipType[] = [
  'explains',
  'contrasts',
  'requires',
  'builds-on',
  'examples',
  'causes',
  'related-to',
];

/**
 * Initial filter state
 */
export const DEFAULT_FILTER_STATE: GraphFilterState = {
  searchQuery: '',
  minImportance: 1,
  relationshipTypes: [...RELATIONSHIP_TYPES],
  navIds: [],
  pageRange: null,
  highlightNodeId: null,
  selectedNodeId: null,
  selectedEdgeId: null,
};
