/**
 * Utilities for highlighting the currently-being-read sentence in EPUB content.
 * Uses shared EPUBTextRange utilities from epubHighlights.ts for ephemeral TTS highlighting.
 */

import {
  type EPUBTextRange,
  generateXPath,
  applyRangeHighlight,
  removeHighlight,
} from './epubHighlights';
import { type TextPositionMap } from './textPositionMap';

const HIGHLIGHT_CLASS = 'tts-reading-highlight';

/**
 * Normalize text for comparison (collapse whitespace)
 */
function normalizeText(text: string): string {
  return text.replace(/\s+/g, ' ').trim().toLowerCase();
}

/**
 * Convert a normalized index within a node's text back to the original string offset.
 * Iterates through the original string, building the normalized version character by character,
 * until we reach the target normalized index.
 */
function normalizedIndexToOriginal(
  original: string,
  normalizedIndex: number
): number {
  let normalizedPos = 0;
  let inWhitespace = false;
  let foundStart = false;

  for (let i = 0; i < original.length; i++) {
    const char = original[i];
    const isSpace = /\s/.test(char);

    if (isSpace) {
      // In normalized form, consecutive whitespace becomes a single space
      if (!inWhitespace && foundStart) {
        normalizedPos++;
        if (normalizedPos >= normalizedIndex) {
          return i + 1; // Position after this whitespace
        }
      }
      inWhitespace = true;
    } else {
      // Non-whitespace character
      if (!foundStart) {
        foundStart = true; // Skip leading whitespace (trim)
      }
      if (normalizedPos >= normalizedIndex) {
        return i;
      }
      normalizedPos++;
      inWhitespace = false;
    }
  }

  return original.length;
}

/**
 * Find sentence in DOM and return as EPUBTextRange
 * Uses text matching to locate, then captures precise XPath boundaries
 */
export function findSentenceRange(
  container: HTMLElement,
  sentenceText: string
): EPUBTextRange | null {
  const normalizedTarget = normalizeText(sentenceText);

  // Find all text nodes in container
  const walker = document.createTreeWalker(
    container,
    NodeFilter.SHOW_TEXT,
    null
  );

  // Build text nodes with normalized positions
  let normalizedAccumulatedPos = 0;
  const textNodes: {
    node: Text;
    originalText: string;
    normalizedText: string;
    normalizedStartPos: number;
  }[] = [];

  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    const originalText = node.textContent || '';
    if (originalText.trim()) {
      const normalizedText = normalizeText(originalText);
      textNodes.push({
        node,
        originalText,
        normalizedText,
        normalizedStartPos: normalizedAccumulatedPos,
      });
      // Add 1 for space between nodes (mimics how normalizeText joins with spaces)
      normalizedAccumulatedPos += normalizedText.length + 1;
    }
  }

  // Build full normalized text for matching
  const normalizedAccumulated = textNodes.map(n => n.normalizedText).join(' ');
  const matchIndex = normalizedAccumulated.indexOf(normalizedTarget);

  if (matchIndex === -1) {
    return null;
  }

  // Find which text nodes contain the start and end (in normalized space)
  const matchEnd = matchIndex + normalizedTarget.length;
  let startNode: Text | null = null;
  let startOffsetNormalized = 0;
  let startNodeInfo: (typeof textNodes)[0] | null = null;
  let endNode: Text | null = null;
  let endOffsetNormalized = 0;
  let endNodeInfo: (typeof textNodes)[0] | null = null;

  for (const nodeInfo of textNodes) {
    const nodeStart = nodeInfo.normalizedStartPos;
    const nodeEnd = nodeStart + nodeInfo.normalizedText.length;

    // Find start node
    if (!startNode && nodeStart <= matchIndex && matchIndex < nodeEnd) {
      startNode = nodeInfo.node;
      startOffsetNormalized = matchIndex - nodeStart;
      startNodeInfo = nodeInfo;
    }

    // Find end node
    if (startNode && nodeStart <= matchEnd && matchEnd <= nodeEnd) {
      endNode = nodeInfo.node;
      endOffsetNormalized = matchEnd - nodeStart;
      endNodeInfo = nodeInfo;
      break;
    }

    // Handle case where match ends exactly at node boundary (in the space between nodes)
    if (startNode && matchEnd === nodeEnd + 1) {
      endNode = nodeInfo.node;
      endOffsetNormalized = nodeInfo.normalizedText.length;
      endNodeInfo = nodeInfo;
      break;
    }
  }

  if (!startNode || !endNode || !startNodeInfo || !endNodeInfo) {
    return null;
  }

  // Convert normalized offsets back to original string offsets
  const startOffset = normalizedIndexToOriginal(
    startNodeInfo.originalText,
    startOffsetNormalized
  );
  const endOffset = normalizedIndexToOriginal(
    endNodeInfo.originalText,
    endOffsetNormalized
  );

  // Return as EPUBTextRange (same structure used by highlights)
  return {
    startXPath: generateXPath(startNode),
    startOffset,
    endXPath: generateXPath(endNode),
    endOffset,
    text: sentenceText,
    navId: '', // Not needed for ephemeral TTS
    chapterId: '',
  };
}

/**
 * Find and highlight text within a container.
 * Returns a cleanup function to remove the highlight.
 */
export function highlightSentence(
  container: HTMLElement,
  sentenceText: string
): (() => void) | null {
  const normalizedTarget = normalizeText(sentenceText);

  // Find all text nodes in container
  const walker = document.createTreeWalker(
    container,
    NodeFilter.SHOW_TEXT,
    null
  );

  const textNodes: Text[] = [];
  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    if (node.textContent?.trim()) {
      textNodes.push(node);
    }
  }

  // Try to find the sentence in text nodes
  let accumulatedText = '';

  for (const textNode of textNodes) {
    const nodeText = textNode.textContent || '';
    accumulatedText += nodeText;

    const normalizedAccumulated = normalizeText(accumulatedText);
    const matchIndex = normalizedAccumulated.indexOf(normalizedTarget);

    if (matchIndex !== -1) {
      // Found the text - check if sentence is contained in single node
      const nodeNormalized = normalizeText(nodeText);
      const nodeMatchIndex = nodeNormalized.indexOf(normalizedTarget);

      if (nodeMatchIndex !== -1) {
        // Sentence is in this single node
        const actualOffset = findActualOffset(nodeText, sentenceText);
        if (actualOffset !== -1) {
          return highlightRange(
            textNode,
            actualOffset,
            textNode,
            Math.min(
              actualOffset + sentenceText.length,
              (textNode.textContent || '').length
            )
          );
        }
      }

      // Sentence spans multiple nodes or partial match - highlight the primary containing node
      if (nodeNormalized.includes(normalizedTarget.substring(0, 20))) {
        return highlightTextNode(textNode);
      }
    }
  }

  // Try using the EPUBTextRange-based approach
  const range = findSentenceRange(container, sentenceText);
  if (range) {
    const highlightSpan = applyRangeHighlight(range, HIGHLIGHT_CLASS);
    if (highlightSpan) {
      return () => removeHighlight(highlightSpan);
    }
  }

  // Fallback: try to find by substring in innerHTML
  const html = container.innerHTML;
  const textIndex = html.indexOf(sentenceText.substring(0, 30));
  if (textIndex !== -1) {
    console.warn(
      'TTS: Sentence found in HTML but not in text nodes, skipping highlight'
    );
  }

  return null;
}

/**
 * Find actual character offset accounting for whitespace differences
 */
function findActualOffset(nodeText: string, searchText: string): number {
  const normalized = normalizeText(searchText);
  const words = normalized.split(' ');
  const firstWord = words[0];

  // Find first word in node text
  const lowerNodeText = nodeText.toLowerCase();
  return lowerNodeText.indexOf(firstWord);
}

/**
 * Highlight a range between two text nodes
 */
function highlightRange(
  startNode: Text,
  startOffset: number,
  endNode: Text,
  endOffset: number
): (() => void) | null {
  try {
    const range = document.createRange();
    range.setStart(startNode, Math.max(0, startOffset));
    range.setEnd(
      endNode,
      Math.min((endNode.textContent || '').length, endOffset)
    );

    const wrapper = document.createElement('span');
    wrapper.className = HIGHLIGHT_CLASS;

    range.surroundContents(wrapper);

    return () => {
      const parent = wrapper.parentNode;
      if (parent) {
        while (wrapper.firstChild) {
          parent.insertBefore(wrapper.firstChild, wrapper);
        }
        parent.removeChild(wrapper);
        parent.normalize(); // Merge adjacent text nodes
      }
    };
  } catch (e) {
    console.warn('TTS: Could not highlight range:', e);
    return null;
  }
}

/**
 * Highlight entire text node
 */
function highlightTextNode(textNode: Text): (() => void) | null {
  try {
    const wrapper = document.createElement('span');
    wrapper.className = HIGHLIGHT_CLASS;

    const parent = textNode.parentNode;
    if (!parent) return null;

    parent.insertBefore(wrapper, textNode);
    wrapper.appendChild(textNode);

    return () => {
      const parent = wrapper.parentNode;
      if (parent) {
        while (wrapper.firstChild) {
          parent.insertBefore(wrapper.firstChild, wrapper);
        }
        parent.removeChild(wrapper);
        parent.normalize();
      }
    };
  } catch (e) {
    console.warn('TTS: Could not highlight text node:', e);
    return null;
  }
}

/**
 * Remove all TTS highlights from container
 */
export function clearAllHighlights(container: HTMLElement) {
  const highlights = container.querySelectorAll(`.${HIGHLIGHT_CLASS}`);
  highlights.forEach(el => {
    const parent = el.parentNode;
    if (parent) {
      while (el.firstChild) {
        parent.insertBefore(el.firstChild, el);
      }
      parent.removeChild(el);
      parent.normalize();
    }
  });
}

/**
 * Highlight a sentence using character offsets from the backend.
 * This is the preferred method - uses pre-computed position map for accuracy.
 *
 * Uses a non-destructive approach: wraps only text node content within each
 * affected node, preserving the original DOM structure. This prevents issues
 * where sentences spanning multiple elements would break the document structure.
 *
 * @param map - TextPositionMap built from the container before TTS started
 * @param startOffset - Character offset where the sentence starts
 * @param endOffset - Character offset where the sentence ends
 * @returns Cleanup function to remove the highlight, or null if highlighting failed
 */
export function highlightByOffset(
  map: TextPositionMap,
  startOffset: number,
  endOffset: number
): (() => void) | null {
  // Find all text nodes that overlap with the range
  const affectedNodes: {
    node: Text;
    highlightStart: number;
    highlightEnd: number;
  }[] = [];

  for (const pos of map.positions) {
    // Check if this node overlaps with our range
    if (pos.textEnd <= startOffset || pos.textStart >= endOffset) {
      // No overlap
      continue;
    }

    // Calculate the portion of this node to highlight
    const highlightStart = Math.max(0, startOffset - pos.textStart);
    const highlightEnd = Math.min(
      pos.node.textContent?.length || 0,
      endOffset - pos.textStart
    );

    if (highlightStart < highlightEnd) {
      affectedNodes.push({
        node: pos.node,
        highlightStart,
        highlightEnd,
      });
    }
  }

  if (affectedNodes.length === 0) {
    console.warn('TTS: No text nodes found for offset range', {
      startOffset,
      endOffset,
    });
    return null;
  }

  // Wrap each affected portion in a highlight span
  // Process in reverse order to avoid offset shifts affecting later nodes
  const wrappers: HTMLSpanElement[] = [];

  for (const {
    node,
    highlightStart,
    highlightEnd,
  } of affectedNodes.reverse()) {
    try {
      // Split the text node to isolate the portion to highlight
      const nodeText = node.textContent || '';

      // Only proceed if the node still has the expected content
      if (highlightEnd > nodeText.length) {
        continue;
      }

      // Create a range for just this portion
      const range = document.createRange();
      range.setStart(node, highlightStart);
      range.setEnd(node, highlightEnd);

      // Use surroundContents for single-node ranges (safe operation)
      const wrapper = document.createElement('span');
      wrapper.className = HIGHLIGHT_CLASS;
      range.surroundContents(wrapper);
      wrappers.push(wrapper);
    } catch (e) {
      // If wrapping fails for this node, continue with others
      console.warn('TTS: Failed to highlight text node portion:', e);
    }
  }

  if (wrappers.length === 0) {
    return null;
  }

  // Return cleanup function that removes all wrappers
  return () => {
    for (const wrapper of wrappers) {
      const parent = wrapper.parentNode;
      if (parent) {
        while (wrapper.firstChild) {
          parent.insertBefore(wrapper.firstChild, wrapper);
        }
        parent.removeChild(wrapper);
        parent.normalize();
      }
    }
  };
}
