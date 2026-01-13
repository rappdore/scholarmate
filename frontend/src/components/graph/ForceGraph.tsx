import { useRef, useEffect, useMemo, useCallback } from 'react';
import * as d3 from 'd3';
import type {
  D3Node,
  D3Link,
  D3GraphData,
  GraphLayoutConfig,
  GraphCallbacks,
} from '../../types/graph';
import { DEFAULT_GRAPH_CONFIG } from '../../types/graph';
import {
  getNodeRadius,
  getEdgeColor,
  getEdgeWidth,
} from '../../utils/graphUtils';

interface ForceGraphProps {
  data: D3GraphData;
  width: number;
  height: number;
  config?: Partial<GraphLayoutConfig>;
  callbacks: Partial<GraphCallbacks>;
  highlightedNodes?: Set<number>;
  selectedNodeId?: number | null;
  selectedEdgeId?: number | null;
}

/**
 * ForceGraph component using correct React + D3 integration pattern:
 * - Initialization happens once
 * - Simulation is stored in ref and updated, not recreated
 * - Visual updates are separate from data updates
 */
export function ForceGraph({
  data,
  width,
  height,
  config: configOverrides = {},
  callbacks,
  highlightedNodes,
  selectedNodeId,
  selectedEdgeId,
}: ForceGraphProps) {
  // Refs for D3 elements - these persist across renders
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<D3Node, D3Link> | null>(null);
  const containerRef = useRef<d3.Selection<
    SVGGElement,
    unknown,
    null,
    undefined
  > | null>(null);
  const linksRef = useRef<d3.Selection<
    SVGLineElement,
    D3Link,
    SVGGElement,
    unknown
  > | null>(null);
  const nodesRef = useRef<d3.Selection<
    SVGGElement,
    D3Node,
    SVGGElement,
    unknown
  > | null>(null);

  // Store current data for D3 to mutate - separate from React's data prop
  const simulationDataRef = useRef<{
    nodes: D3Node[];
    links: D3Link[];
    nodeIds: string;
    linkIds: string;
  } | null>(null);

  // Store callbacks in ref to avoid re-renders
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  // Merge config with defaults
  const config: GraphLayoutConfig = useMemo(
    () => ({
      ...DEFAULT_GRAPH_CONFIG,
      ...configOverrides,
      width,
      height,
      nodeSize: {
        ...DEFAULT_GRAPH_CONFIG.nodeSize,
        ...configOverrides.nodeSize,
      },
      edgeColors: {
        ...DEFAULT_GRAPH_CONFIG.edgeColors,
        ...configOverrides.edgeColors,
      },
    }),
    [width, height, configOverrides]
  );

  // Create stable data fingerprint for comparison
  const dataFingerprint = useMemo(() => {
    const nodeIds = data.nodes
      .map(n => n.id)
      .sort((a, b) => a - b)
      .join(',');
    const linkIds = data.links
      .map(l => l.id)
      .sort((a, b) => a - b)
      .join(',');
    return { nodeIds, linkIds };
  }, [data]);

  // Drag behavior factory - uses ref to access simulation
  const createDragBehavior = useCallback(() => {
    return d3
      .drag<SVGGElement, D3Node>()
      .on('start', (event, d) => {
        if (!event.active) simulationRef.current?.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) simulationRef.current?.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
  }, []);

  // EFFECT 1: Initialize SVG structure (runs once)
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);

    // Clear any existing content
    svg.selectAll('*').remove();

    // Create defs for arrow markers
    const defs = svg.append('defs');
    const markerTypes = Object.keys(config.edgeColors) as Array<
      keyof typeof config.edgeColors
    >;

    markerTypes.forEach(type => {
      defs
        .append('marker')
        .attr('id', `arrow-${type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', config.edgeColors[type])
        .attr('d', 'M0,-5L10,0L0,5');
    });

    // Create container group for zoom/pan
    const container = svg.append('g').attr('class', 'graph-container');
    containerRef.current = container;

    // Create groups for links and nodes (links first so nodes render on top)
    container.append('g').attr('class', 'links');
    container.append('g').attr('class', 'nodes');

    // Setup zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', event => {
        container.attr('transform', event.transform);
        callbacksRef.current.onZoomChange?.(event.transform);
      });

    svg.call(zoom);

    // Background click handler
    svg.on('click', event => {
      if (event.target === svgRef.current) {
        callbacksRef.current.onBackgroundClick?.();
      }
    });

    // Cleanup on unmount
    return () => {
      if (simulationRef.current) {
        simulationRef.current.stop();
        simulationRef.current = null;
      }
    };
    // Only run once on mount - config.edgeColors needed for markers
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // EFFECT 2: Manage simulation and data binding
  useEffect(() => {
    if (!svgRef.current || !containerRef.current || data.nodes.length === 0)
      return;

    const container = containerRef.current;
    const linkGroup = container.select<SVGGElement>('.links');
    const nodeGroup = container.select<SVGGElement>('.nodes');

    // Check if data actually changed
    const prevData = simulationDataRef.current;
    const dataChanged =
      !prevData ||
      prevData.nodeIds !== dataFingerprint.nodeIds ||
      prevData.linkIds !== dataFingerprint.linkIds;

    if (!dataChanged && simulationRef.current) {
      // Data hasn't changed, simulation exists - nothing to do
      return;
    }

    // Stop existing simulation
    if (simulationRef.current) {
      simulationRef.current.stop();
    }

    // Create deep copies of data for D3 to mutate
    const nodes: D3Node[] = data.nodes.map(n => ({ ...n }));
    const links: D3Link[] = data.links.map(l => ({ ...l }));

    // Store the new data reference
    simulationDataRef.current = {
      nodes,
      links,
      nodeIds: dataFingerprint.nodeIds,
      linkIds: dataFingerprint.linkIds,
    };

    // LINKS: Use D3's data join pattern
    const linkSelection = linkGroup
      .selectAll<SVGLineElement, D3Link>('line')
      .data(links, d => d.id.toString());

    // Remove old links
    linkSelection.exit().remove();

    // Add new links
    const linkEnter = linkSelection
      .enter()
      .append('line')
      .attr('stroke-opacity', 0.6)
      .style('cursor', 'pointer');

    // Merge enter + update
    const linkMerge = linkEnter.merge(linkSelection);

    linkMerge
      .attr('stroke', d => getEdgeColor(d.type, config.edgeColors))
      .attr('stroke-width', d => getEdgeWidth(d.weight))
      .attr('marker-end', d => `url(#arrow-${d.type})`)
      .on('click', (event, d) => {
        event.stopPropagation();
        callbacksRef.current.onEdgeClick?.(d);
      })
      .on('mouseenter', (_, d) => callbacksRef.current.onEdgeHover?.(d))
      .on('mouseleave', () => callbacksRef.current.onEdgeHover?.(null));

    linksRef.current = linkMerge;

    // NODES: Use D3's data join pattern
    const nodeSelection = nodeGroup
      .selectAll<SVGGElement, D3Node>('g.node')
      .data(nodes, d => d.id.toString());

    // Remove old nodes
    nodeSelection.exit().remove();

    // Add new nodes
    const nodeEnter = nodeSelection
      .enter()
      .append('g')
      .attr('class', 'node')
      .style('cursor', 'pointer');

    // Add circle to new nodes
    nodeEnter
      .append('circle')
      .attr('fill', '#1f2937')
      .attr('stroke', '#6366f1');

    // Add text label to new nodes
    nodeEnter
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('fill', '#d1d5db')
      .attr('font-size', '10px')
      .attr('pointer-events', 'none');

    // Merge enter + update
    const nodeMerge = nodeEnter.merge(nodeSelection);

    // Update all nodes (enter + existing)
    nodeMerge
      .on('click', (event, d) => {
        event.stopPropagation();
        callbacksRef.current.onNodeClick?.(d);
      })
      .on('dblclick', (event, d) => {
        event.stopPropagation();
        callbacksRef.current.onNodeDoubleClick?.(d);
      })
      .on('mouseenter', (_, d) => callbacksRef.current.onNodeHover?.(d))
      .on('mouseleave', () => callbacksRef.current.onNodeHover?.(null))
      .call(createDragBehavior());

    // Update circles
    nodeMerge
      .select('circle')
      .attr('r', d => getNodeRadius(d.importance, config.nodeSize))
      .attr('stroke-width', config.nodeSize.strokeWidth);

    // Update labels
    nodeMerge
      .select('text')
      .text(d =>
        d.name.length > 15 ? d.name.substring(0, 12) + '...' : d.name
      )
      .attr('dy', d => getNodeRadius(d.importance, config.nodeSize) + 14);

    nodesRef.current = nodeMerge;

    // Create force simulation
    const simulation = d3
      .forceSimulation<D3Node>(nodes)
      .force(
        'link',
        d3
          .forceLink<D3Node, D3Link>(links)
          .id(d => d.id)
          .distance(config.linkDistance)
          .strength(config.linkStrength)
      )
      .force('charge', d3.forceManyBody().strength(config.chargeStrength))
      .force(
        'center',
        d3.forceCenter(width / 2, height / 2).strength(config.centerStrength)
      )
      .force(
        'collision',
        d3
          .forceCollide<D3Node>()
          .radius(
            d =>
              getNodeRadius(d.importance, config.nodeSize) +
              config.collisionRadius
          )
      )
      .alphaDecay(config.alphaDecay);

    simulationRef.current = simulation;

    // Update positions on tick
    simulation.on('tick', () => {
      linksRef.current
        ?.attr('x1', d => (d.source as D3Node).x!)
        .attr('y1', d => (d.source as D3Node).y!)
        .attr('x2', d => (d.target as D3Node).x!)
        .attr('y2', d => (d.target as D3Node).y!);

      nodesRef.current?.attr('transform', d => `translate(${d.x},${d.y})`);
    });
  }, [data, dataFingerprint, width, height, config, createDragBehavior]);

  // EFFECT 3: Update visual styles (highlighting, selection) WITHOUT touching simulation
  useEffect(() => {
    if (!nodesRef.current || !linksRef.current) return;

    // Update node styles based on highlighting/selection
    nodesRef.current.select('circle').attr('stroke', d => {
      if (selectedNodeId === d.id) return '#22c55e'; // green-500 for selected
      if (highlightedNodes?.has(d.id)) return '#fbbf24'; // amber-400 for highlighted
      return '#6366f1'; // indigo-500 default
    });

    nodesRef.current.select('circle').attr('stroke-width', d => {
      if (selectedNodeId === d.id || highlightedNodes?.has(d.id)) {
        return config.nodeSize.strokeWidth + 2;
      }
      return config.nodeSize.strokeWidth;
    });

    nodesRef.current.select('circle').attr('opacity', d => {
      if (
        highlightedNodes &&
        highlightedNodes.size > 0 &&
        !highlightedNodes.has(d.id)
      ) {
        return 0.3;
      }
      return 1;
    });

    // Update link styles based on selection
    linksRef.current.attr('stroke-opacity', d => {
      if (selectedEdgeId === d.id) return 1;
      if (highlightedNodes && highlightedNodes.size > 0) {
        const sourceId = typeof d.source === 'number' ? d.source : d.source.id;
        const targetId = typeof d.target === 'number' ? d.target : d.target.id;
        if (
          !highlightedNodes.has(sourceId) ||
          !highlightedNodes.has(targetId)
        ) {
          return 0.1;
        }
      }
      return 0.6;
    });

    linksRef.current.attr('stroke-width', d => {
      if (selectedEdgeId === d.id) return getEdgeWidth(d.weight) + 2;
      return getEdgeWidth(d.weight);
    });
  }, [
    highlightedNodes,
    selectedNodeId,
    selectedEdgeId,
    config.nodeSize.strokeWidth,
  ]);

  // EFFECT 4: Update center force when dimensions change
  useEffect(() => {
    if (simulationRef.current) {
      simulationRef.current
        .force(
          'center',
          d3.forceCenter(width / 2, height / 2).strength(config.centerStrength)
        )
        .alpha(0.3)
        .restart();
    }
  }, [width, height, config.centerStrength]);

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className="bg-gray-900 rounded-lg"
      style={{ touchAction: 'none' }}
    />
  );
}
