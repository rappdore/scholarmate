/**
 * Utilities for highlighting the currently-being-read sentence in EPUB content.
 */

const HIGHLIGHT_CLASS = 'tts-reading-highlight';

/**
 * Find and highlight text within a container.
 * Returns a cleanup function to remove the highlight.
 */
export function highlightSentence(
  container: HTMLElement,
  sentenceText: string
): (() => void) | null {
  // Normalize text for comparison
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
 * Normalize text for comparison (collapse whitespace)
 */
function normalizeText(text: string): string {
  return text.replace(/\s+/g, ' ').trim().toLowerCase();
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
