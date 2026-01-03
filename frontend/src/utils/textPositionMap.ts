/**
 * Maps character positions in extracted text back to DOM text nodes.
 * This allows us to use character offsets from the backend to find
 * the exact DOM range for highlighting.
 */

export interface TextNodePosition {
  node: Text;
  /** Start position in the full extracted text (inclusive) */
  textStart: number;
  /** End position in the full extracted text (exclusive) */
  textEnd: number;
}

export interface TextPositionMap {
  fullText: string;
  positions: TextNodePosition[];
}

/**
 * Build a TextPositionMap from a container element.
 * Walks all text nodes and records their positions in the concatenated text.
 */
export function buildTextPositionMap(container: HTMLElement): TextPositionMap {
  const positions: TextNodePosition[] = [];
  let fullText = '';

  const walker = document.createTreeWalker(
    container,
    NodeFilter.SHOW_TEXT,
    null
  );

  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    const nodeText = node.textContent || '';
    if (nodeText.length > 0) {
      const textStart = fullText.length;
      fullText += nodeText;
      const textEnd = fullText.length;

      positions.push({
        node,
        textStart,
        textEnd,
      });
    }
  }

  return { fullText, positions };
}

/**
 * Find the DOM nodes and offsets for a character offset range.
 * Returns start node/offset and end node/offset.
 */
export function offsetToRange(
  map: TextPositionMap,
  startOffset: number,
  endOffset: number
): {
  startNode: Text;
  startNodeOffset: number;
  endNode: Text;
  endNodeOffset: number;
} | null {
  let startNode: Text | null = null;
  let startNodeOffset = 0;
  let endNode: Text | null = null;
  let endNodeOffset = 0;

  for (const pos of map.positions) {
    // Find start node: the node that contains startOffset
    if (
      !startNode &&
      pos.textStart <= startOffset &&
      startOffset < pos.textEnd
    ) {
      startNode = pos.node;
      startNodeOffset = startOffset - pos.textStart;
    }

    // Find end node: the node that contains endOffset
    // We use <= for endOffset because it can be at the exact end of a node
    if (startNode && pos.textStart < endOffset && endOffset <= pos.textEnd) {
      endNode = pos.node;
      endNodeOffset = endOffset - pos.textStart;
      break;
    }
  }

  // Handle edge case: endOffset is exactly at a node boundary
  // and we haven't found it yet (can happen at document end)
  if (startNode && !endNode) {
    const lastPos = map.positions[map.positions.length - 1];
    if (lastPos && endOffset >= lastPos.textEnd) {
      endNode = lastPos.node;
      endNodeOffset = lastPos.node.textContent?.length || 0;
    }
  }

  if (!startNode || !endNode) {
    return null;
  }

  return { startNode, startNodeOffset, endNode, endNodeOffset };
}

/**
 * Create a DOM Range from character offset range.
 */
export function createRangeFromOffsets(
  map: TextPositionMap,
  startOffset: number,
  endOffset: number
): Range | null {
  const nodes = offsetToRange(map, startOffset, endOffset);
  if (!nodes) {
    return null;
  }

  try {
    const range = document.createRange();

    // Clamp offsets to valid ranges to prevent errors
    const startLen = nodes.startNode.textContent?.length || 0;
    const endLen = nodes.endNode.textContent?.length || 0;

    range.setStart(
      nodes.startNode,
      Math.max(0, Math.min(nodes.startNodeOffset, startLen))
    );
    range.setEnd(
      nodes.endNode,
      Math.max(0, Math.min(nodes.endNodeOffset, endLen))
    );

    return range;
  } catch (e) {
    console.warn('Failed to create range from offsets:', e);
    return null;
  }
}
