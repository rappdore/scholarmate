// Utility functions for EPUB text selection and highlighting
// DOM-based positioning using XPath + character offsets for both start and end boundaries

/**
 * Base interface for text ranges - used by both highlights and TTS
 */
export interface EPUBTextRange {
  // Start boundary
  startXPath: string;
  startOffset: number;

  // End boundary
  endXPath: string;
  endOffset: number;

  // Context
  navId: string;
  chapterId: string;

  // Content
  text: string;
}

/**
 * Selection captured from user interaction (before saving)
 */
export interface EPUBSelection extends EPUBTextRange {
  // No additional fields - just the range data
}

/**
 * Highlight stored in database
 */
export interface EPUBHighlight extends EPUBTextRange {
  id?: number;
  epub_id: number;
  nav_id: string;
  chapter_id: string;
  start_xpath: string;
  start_offset: number;
  end_xpath: string;
  end_offset: number;
  highlight_text: string;
  color: string;
  created_at?: string;
}

export type HighlightColor = 'yellow' | 'blue' | 'green' | 'pink' | 'orange';

/**
 * Generate XPath for a DOM element
 * Creates a unique path to the element in the DOM tree
 */
export function generateXPath(element: Node): string {
  if (element.nodeType === Node.TEXT_NODE) {
    const parentXPath = generateXPath(element.parentNode!);

    // For text nodes, find which text child this is
    const parent = element.parentNode as Element;
    const textNodes = Array.from(parent.childNodes).filter(
      n => n.nodeType === Node.TEXT_NODE
    );
    const index = textNodes.indexOf(element as Text) + 1;

    return `${parentXPath}/text()[${index}]`;
  }

  if (element.nodeType !== Node.ELEMENT_NODE) {
    return '';
  }

  const elem = element as Element;

  // If element has an ID, use it for more stable path
  if (elem.id) {
    return `//*[@id="${elem.id}"]`;
  }

  let path = '';
  let current: Element | null = elem;

  while (current && current.nodeType === Node.ELEMENT_NODE) {
    const tagName = current.tagName.toLowerCase();

    // Stop at container - we want relative paths from the content container
    if (current.classList.contains('epub-content-container')) {
      break;
    }

    if (current.classList.contains('epub-outer-container')) {
      break;
    }

    // Count siblings with same tag name
    let index = 1;
    let sibling = current.previousElementSibling;
    while (sibling) {
      if (sibling.tagName.toLowerCase() === tagName) {
        index++;
      }
      sibling = sibling.previousElementSibling;
    }

    // Build path segment
    const segment = `${tagName}[${index}]`;
    path = '/' + segment + path;

    current = current.parentElement;
  }

  // Ensure we have a relative path starting with ./
  if (path && !path.startsWith('./')) {
    path = '.' + path;
  }

  return path;
}

/**
 * Find element by XPath within the EPUB content container
 */
export function getElementByXPath(
  xpath: string,
  container?: Element
): Node | null {
  const contextNode =
    container || document.querySelector('.epub-content-container');

  if (!contextNode) {
    return null;
  }

  try {
    // Try the XPath as-is first
    let result = document.evaluate(
      xpath,
      contextNode,
      null,
      XPathResult.FIRST_ORDERED_NODE_TYPE,
      null
    );

    let element = result.singleNodeValue;

    if (!element && !xpath.startsWith('.')) {
      // Try a relative XPath
      const relativePath = '.' + xpath;

      result = document.evaluate(
        relativePath,
        contextNode,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      );

      element = result.singleNodeValue;
    }

    if (!element && xpath.startsWith('./')) {
      // Try absolute XPath
      const absolutePath = xpath.substring(1); // Remove the '.'

      result = document.evaluate(
        absolutePath,
        contextNode,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      );

      element = result.singleNodeValue;
    }

    return element;
  } catch (error) {
    console.error('Error evaluating XPath:', error);
    return null;
  }
}

/**
 * Find the first text node within a node (depth-first)
 */
export function findFirstTextNode(node: Node): Text | null {
  if (node.nodeType === Node.TEXT_NODE) {
    return node as Text;
  }

  for (const child of Array.from(node.childNodes)) {
    const textNode = findFirstTextNode(child);
    if (textNode) {
      return textNode;
    }
  }

  return null;
}

/**
 * Find the last text node within a node (depth-first, reverse order)
 */
export function findLastTextNode(node: Node): Text | null {
  if (node.nodeType === Node.TEXT_NODE) {
    return node as Text;
  }

  // Search children in reverse order to find the last text node
  const children = Array.from(node.childNodes).reverse();
  for (const child of children) {
    const textNode = findLastTextNode(child);
    if (textNode) {
      return textNode;
    }
  }

  return null;
}

/**
 * Get current text selection and convert to EPUB selection data
 * Always captures both start and end boundaries
 */
export function getEPUBSelection(
  navId: string,
  chapterId: string
): EPUBSelection | null {
  const selection = window.getSelection();

  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
    return null;
  }

  const range = selection.getRangeAt(0);
  const container = document.querySelector('.epub-content-container');

  if (!container || !container.contains(range.commonAncestorContainer)) {
    return null;
  }

  const selectedText = range.toString().trim();
  if (!selectedText) {
    return null;
  }

  try {
    // Get start boundary
    const startNode =
      range.startContainer.nodeType === Node.TEXT_NODE
        ? range.startContainer
        : findFirstTextNode(range.startContainer);

    if (!startNode) return null;

    const startXPath = generateXPath(startNode);
    const startOffset =
      range.startContainer.nodeType === Node.TEXT_NODE ? range.startOffset : 0;

    // Get end boundary
    const endNode =
      range.endContainer.nodeType === Node.TEXT_NODE
        ? range.endContainer
        : findLastTextNode(range.endContainer);

    if (!endNode) return null;

    const endXPath = generateXPath(endNode);
    const endOffset =
      range.endContainer.nodeType === Node.TEXT_NODE
        ? range.endOffset
        : endNode.textContent?.length || 0;

    return {
      startXPath,
      startOffset,
      endXPath,
      endOffset,
      text: selectedText,
      navId,
      chapterId,
    };
  } catch (error) {
    console.error('Error processing selection:', error);
    return null;
  }
}

/**
 * Apply highlight styling to text based on stored highlight data
 * Uses precise XPath boundaries for both start and end
 */
export function applyHighlight(highlight: EPUBHighlight): boolean {
  try {
    // Find start text node
    const startNode = getElementByXPath(highlight.start_xpath);
    if (!startNode || startNode.nodeType !== Node.TEXT_NODE) {
      console.warn('Could not find start node:', highlight.start_xpath);
      return false;
    }

    // Find end text node
    const endNode = getElementByXPath(highlight.end_xpath);
    if (!endNode || endNode.nodeType !== Node.TEXT_NODE) {
      console.warn('Could not find end node:', highlight.end_xpath);
      return false;
    }

    const startTextNode = startNode as Text;
    const endTextNode = endNode as Text;

    // Validate offsets
    const startText = startTextNode.textContent || '';
    const endText = endTextNode.textContent || '';

    if (highlight.start_offset > startText.length) {
      console.warn('Start offset exceeds node length');
      return false;
    }
    if (highlight.end_offset > endText.length) {
      console.warn('End offset exceeds node length');
      return false;
    }

    // Create range
    const range = document.createRange();
    range.setStart(startTextNode, highlight.start_offset);
    range.setEnd(endTextNode, highlight.end_offset);

    // Verify range text matches (optional safety check)
    const rangeText = range.toString();
    if (rangeText !== highlight.highlight_text) {
      console.warn('Range text mismatch - DOM may have changed:', {
        expected: highlight.highlight_text,
        actual: rangeText,
      });
      // Still attempt to apply - user can delete if wrong
    }

    // Handle single-node vs multi-node differently
    if (startTextNode === endTextNode) {
      // Single node - can use surroundContents
      const highlightSpan = document.createElement('span');
      highlightSpan.className = `epub-highlight epub-highlight-${highlight.color}`;
      highlightSpan.setAttribute(
        'data-highlight-id',
        highlight.id?.toString() || ''
      );
      highlightSpan.setAttribute(
        'data-highlight-text',
        highlight.highlight_text
      );

      try {
        range.surroundContents(highlightSpan);
        return true;
      } catch (e) {
        console.error('Error applying single-node highlight:', e);
        return false;
      }
    } else {
      // Multi-node - need to highlight each text node in range
      return applyMultiNodeHighlight(range, highlight);
    }
  } catch (error) {
    console.error('Error applying highlight:', error);
    return false;
  }
}

/**
 * Apply highlight across multiple text nodes
 */
function applyMultiNodeHighlight(
  range: Range,
  highlight: EPUBHighlight
): boolean {
  // Get all text nodes within the range
  const textNodes: Text[] = [];
  const walker = document.createTreeWalker(
    range.commonAncestorContainer,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode: node => {
        return range.intersectsNode(node)
          ? NodeFilter.FILTER_ACCEPT
          : NodeFilter.FILTER_REJECT;
      },
    }
  );

  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    textNodes.push(node);
  }

  if (textNodes.length === 0) {
    return false;
  }

  // Wrap each text node (or portion) in a highlight span
  for (let i = 0; i < textNodes.length; i++) {
    const textNode = textNodes[i];
    const isFirst = i === 0;
    const isLast = i === textNodes.length - 1;

    const nodeRange = document.createRange();

    if (isFirst) {
      nodeRange.setStart(textNode, highlight.start_offset);
    } else {
      nodeRange.setStart(textNode, 0);
    }

    if (isLast) {
      nodeRange.setEnd(textNode, highlight.end_offset);
    } else {
      nodeRange.setEnd(textNode, textNode.textContent?.length || 0);
    }

    const span = document.createElement('span');
    span.className = `epub-highlight epub-highlight-${highlight.color}`;
    span.setAttribute('data-highlight-id', highlight.id?.toString() || '');
    // Only set full text on first span
    if (isFirst) {
      span.setAttribute('data-highlight-text', highlight.highlight_text);
    }

    try {
      nodeRange.surroundContents(span);
    } catch (e) {
      // surroundContents can fail if range crosses element boundaries
      // Use extractContents + insertNode as fallback
      const fragment = nodeRange.extractContents();
      span.appendChild(fragment);
      nodeRange.insertNode(span);
    }
  }

  return true;
}

/**
 * Apply a range-based highlight with a custom CSS class
 * Used by both persistent highlights and TTS
 * Returns the created highlight span(s) or null if failed
 */
export function applyRangeHighlight(
  textRange: EPUBTextRange,
  cssClass: string
): HTMLSpanElement | null {
  try {
    // Find start text node
    const startNode = getElementByXPath(textRange.startXPath);
    if (!startNode || startNode.nodeType !== Node.TEXT_NODE) {
      return null;
    }

    // Find end text node
    const endNode = getElementByXPath(textRange.endXPath);
    if (!endNode || endNode.nodeType !== Node.TEXT_NODE) {
      return null;
    }

    const startTextNode = startNode as Text;
    const endTextNode = endNode as Text;

    // Create range
    const range = document.createRange();
    range.setStart(
      startTextNode,
      Math.min(textRange.startOffset, startTextNode.textContent?.length || 0)
    );
    range.setEnd(
      endTextNode,
      Math.min(textRange.endOffset, endTextNode.textContent?.length || 0)
    );

    // Create highlight span
    const highlightSpan = document.createElement('span');
    highlightSpan.className = cssClass;

    // Handle single-node vs multi-node
    if (startTextNode === endTextNode) {
      try {
        range.surroundContents(highlightSpan);
        return highlightSpan;
      } catch (e) {
        console.warn('Could not apply range highlight:', e);
        return null;
      }
    } else {
      // Multi-node - wrap entire range
      try {
        const fragment = range.extractContents();
        highlightSpan.appendChild(fragment);
        range.insertNode(highlightSpan);
        return highlightSpan;
      } catch (e) {
        console.warn('Could not apply multi-node range highlight:', e);
        return null;
      }
    }
  } catch (error) {
    console.error('Error applying range highlight:', error);
    return null;
  }
}

/**
 * Remove a highlight span, restoring the original text nodes
 */
export function removeHighlight(highlightSpan: HTMLSpanElement): void {
  const parent = highlightSpan.parentNode;
  if (parent) {
    while (highlightSpan.firstChild) {
      parent.insertBefore(highlightSpan.firstChild, highlightSpan);
    }
    parent.removeChild(highlightSpan);
    parent.normalize(); // Merge adjacent text nodes
  }
}

/**
 * Remove all highlights from the current content
 */
export function clearAllHighlights(): void {
  const container = document.querySelector('.epub-content-container');
  if (!container) return;

  const highlights = container.querySelectorAll('.epub-highlight');
  highlights.forEach(highlight => {
    removeHighlight(highlight as HTMLSpanElement);
  });

  // Normalize text nodes to merge adjacent text nodes
  container.normalize();
}

/**
 * Get highlight color CSS class mapping
 */
export function getHighlightColorClass(color: HighlightColor): string {
  return `epub-highlight-${color}`;
}

/**
 * Extract chapter ID from navigation ID
 * Matches the existing pattern in EPUBViewer
 */
export function extractChapterIdFromNavId(navId: string): string {
  // Handle hierarchical nav IDs like 'section_2_1_3' -> 'chapter_2'
  const parts = navId.split('_');
  if (parts.length >= 2 && parts[0] === 'section') {
    return `chapter_${parts[1]}`;
  }

  // Fallback for other patterns
  if (navId.includes('chapter')) {
    return navId.split('_')[0] + '_' + navId.split('_')[1];
  }

  return navId;
}

/**
 * Convert EPUBSelection to API request format
 */
export function selectionToHighlightRequest(
  selection: EPUBSelection,
  epubId: number,
  color: HighlightColor
): Omit<EPUBHighlight, 'id' | 'created_at'> {
  return {
    epub_id: epubId,
    nav_id: selection.navId,
    chapter_id: selection.chapterId,
    start_xpath: selection.startXPath,
    start_offset: selection.startOffset,
    end_xpath: selection.endXPath,
    end_offset: selection.endOffset,
    highlight_text: selection.text,
    color,
    // Also include the interface fields for EPUBTextRange compatibility
    startXPath: selection.startXPath,
    startOffset: selection.startOffset,
    endXPath: selection.endXPath,
    endOffset: selection.endOffset,
    navId: selection.navId,
    chapterId: selection.chapterId,
    text: selection.text,
  };
}
