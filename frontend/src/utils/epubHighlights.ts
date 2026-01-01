// Utility functions for EPUB text selection and highlighting
// DOM-based positioning using XPath + character offsets

export interface EPUBSelection {
  xpath: string;
  startOffset: number;
  endOffset: number;
  selectedText: string;
  navId: string;
  chapterId: string;
}

export interface EPUBHighlight {
  id?: string;
  epub_id: number;
  nav_id: string;
  chapter_id: string;
  xpath: string;
  start_offset: number;
  end_offset: number;
  highlight_text: string;
  color: string;
  created_at?: string;
}

export type HighlightColor = 'yellow' | 'blue' | 'green' | 'pink' | 'orange';

/**
 * Generate XPath for a DOM element
 * This creates a unique path to the element in the DOM tree
 */
export function generateXPath(element: Node): string {
  console.log('🔗 generateXPath called for element:', element);

  if (element.nodeType === Node.TEXT_NODE) {
    console.log('📝 Text node detected, getting parent element');
    const parentXPath = generateXPath(element.parentNode!);
    console.log('📍 Parent XPath:', parentXPath);

    // For text nodes, we need to find which text child this is
    const parent = element.parentNode as Element;
    const textNodes = Array.from(parent.childNodes).filter(
      n => n.nodeType === Node.TEXT_NODE
    );
    const index = textNodes.indexOf(element as Text) + 1;

    console.log('📊 Text node index:', index, 'of', textNodes.length);
    const result = `${parentXPath}/text()[${index}]`;
    console.log('✅ Generated XPath for text node:', result);
    return result;
  }

  if (element.nodeType !== Node.ELEMENT_NODE) {
    console.log('❌ Not an element or text node');
    return '';
  }

  const elem = element as Element;
  console.log('🏷️ Processing element:', elem.tagName, elem.className, elem.id);

  // If element has an ID, use it for more stable path
  if (elem.id) {
    const result = `//*[@id="${elem.id}"]`;
    console.log('🆔 Using ID-based XPath:', result);
    return result;
  }

  let path = '';
  let current: Element | null = elem;

  while (current && current.nodeType === Node.ELEMENT_NODE) {
    const tagName = current.tagName.toLowerCase();

    // Stop at container - we want relative paths from the content container
    if (current.classList.contains('epub-content-container')) {
      console.log('🛑 Reached epub-content-container, using relative path');
      // Don't include the container itself in the path
      break;
    }

    if (current.classList.contains('epub-outer-container')) {
      console.log('🛑 Reached epub-outer-container, stopping');
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

    console.log(`📍 Path segment: ${segment}, current path: ${path}`);

    current = current.parentElement;
  }

  // Ensure we have a relative path starting with ./
  if (path && !path.startsWith('./')) {
    path = '.' + path;
  }

  console.log('✅ Final generated XPath:', path);
  return path;
}

/**
 * Find element by XPath within the EPUB content container
 */
export function getElementByXPath(
  xpath: string,
  container?: Element
): Element | null {
  console.log('🔍 getElementByXPath called with:', xpath);

  const contextNode =
    container || document.querySelector('.epub-content-container');
  console.log('📦 Using context node:', contextNode);

  if (!contextNode) {
    console.log('❌ No context node found');
    return null;
  }

  try {
    // Try the XPath as-is first
    console.log('🔍 Evaluating XPath:', xpath);
    let result = document.evaluate(
      xpath,
      contextNode,
      null,
      XPathResult.FIRST_ORDERED_NODE_TYPE,
      null
    );

    let element = result.singleNodeValue as Element;
    console.log('📍 XPath result:', element);

    if (!element && !xpath.startsWith('.')) {
      console.log('❌ Absolute XPath failed - trying relative XPath');

      // Try a relative XPath
      const relativePath = '.' + xpath;
      console.log('🔄 Trying relative XPath:', relativePath);

      result = document.evaluate(
        relativePath,
        contextNode,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      );

      element = result.singleNodeValue as Element;
      console.log('📍 Relative XPath result:', element);
    }

    if (!element && xpath.startsWith('./')) {
      console.log('❌ Relative XPath failed - trying absolute XPath');

      // Try absolute XPath
      const absolutePath = xpath.substring(1); // Remove the '.'
      console.log('🔄 Trying absolute XPath:', absolutePath);

      result = document.evaluate(
        absolutePath,
        contextNode,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      );

      element = result.singleNodeValue as Element;
      console.log('📍 Absolute XPath result:', element);
    }

    return element;
  } catch (error) {
    console.error('❌ Error evaluating XPath:', error);
    return null;
  }
}

/**
 * Get current text selection and convert to EPUB highlight data
 */
export function getEPUBSelection(
  navId: string,
  chapterId: string
): EPUBSelection | null {
  const selection = window.getSelection();
  console.log('🔍 getEPUBSelection called with:', { navId, chapterId });
  console.log('🔍 Window selection:', selection);

  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
    console.log('❌ No selection or collapsed selection');
    return null;
  }

  console.log('✅ Found selection with', selection.rangeCount, 'ranges');
  const range = selection.getRangeAt(0);
  console.log('📍 Range:', range);

  const container = document.querySelector('.epub-content-container');
  console.log('📦 EPUB container:', container);

  // Ensure selection is within EPUB content
  if (!container || !container.contains(range.commonAncestorContainer)) {
    console.log('❌ Selection not within EPUB container');
    return null;
  }

  // Get selected text
  const selectedText = range.toString().trim();
  console.log('📝 Selected text:', `"${selectedText}"`);
  if (!selectedText) {
    console.log('❌ Empty selected text');
    return null;
  }

  try {
    // Find the text node and calculate character offsets
    const startContainer = range.startContainer;
    const endContainer = range.endContainer;

    // Simple case: selection is within same text node
    if (
      startContainer === endContainer &&
      startContainer.nodeType === Node.TEXT_NODE
    ) {
      const xpath = generateXPath(startContainer);

      return {
        xpath,
        startOffset: range.startOffset,
        endOffset: range.endOffset,
        selectedText,
        navId,
        chapterId,
      };
    }

    // Complex case: selection spans multiple nodes (e.g., entire paragraph)
    // Find the common ancestor element and use it as the reference point
    console.log(
      '📍 Complex selection spanning multiple nodes, using common ancestor approach'
    );

    // Get the common ancestor that contains the entire selection
    let commonAncestor = range.commonAncestorContainer;

    // If common ancestor is a text node, get its parent
    if (commonAncestor.nodeType === Node.TEXT_NODE) {
      commonAncestor = commonAncestor.parentNode!;
    }

    // Find the first text node in the selection to use as anchor
    const firstTextNode = findFirstTextNode(startContainer);
    if (!firstTextNode) {
      console.warn('Could not find first text node in selection');
      return null;
    }

    const xpath = generateXPath(firstTextNode);
    const startOffset =
      startContainer.nodeType === Node.TEXT_NODE ? range.startOffset : 0;

    // For multi-node selections, we store the full selected text
    // The end offset represents the length of text from the start node
    // We'll use the selected text itself to determine the highlight range
    return {
      xpath,
      startOffset,
      endOffset: startOffset + selectedText.length, // Approximate, actual highlight will use text matching
      selectedText,
      navId,
      chapterId,
    };
  } catch (error) {
    console.error('Error processing selection:', error);
    return null;
  }
}

/**
 * Find the first text node within a node (depth-first)
 */
function findFirstTextNode(node: Node): Text | null {
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
 * Apply highlight styling to text based on stored highlight data
 */
export function applyHighlight(highlight: EPUBHighlight): boolean {
  try {
    const element = getElementByXPath(highlight.xpath);
    if (!element || element.nodeType !== Node.TEXT_NODE) {
      console.warn('Could not find element for highlight:', highlight.xpath);
      return false;
    }

    const textNode = element as unknown as Text;
    const fullText = textNode.textContent || '';

    // Validate offsets
    if (
      highlight.start_offset >= fullText.length ||
      highlight.end_offset > fullText.length ||
      highlight.start_offset >= highlight.end_offset
    ) {
      console.warn('Invalid highlight offsets:', highlight);
      return false;
    }

    // Create range for the highlight
    const range = document.createRange();
    range.setStart(textNode, highlight.start_offset);
    range.setEnd(textNode, highlight.end_offset);

    // Create highlight span
    const highlightSpan = document.createElement('span');
    highlightSpan.className = `epub-highlight epub-highlight-${highlight.color}`;
    highlightSpan.setAttribute('data-highlight-id', highlight.id || '');
    highlightSpan.setAttribute('data-highlight-text', highlight.highlight_text);

    try {
      range.surroundContents(highlightSpan);
      return true;
    } catch (error) {
      console.error('Error applying highlight span:', error);
      return false;
    }
  } catch (error) {
    console.error('Error applying highlight:', error);
    return false;
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
    const parent = highlight.parentNode;
    if (parent) {
      // Move text content back to parent and remove highlight span
      while (highlight.firstChild) {
        parent.insertBefore(highlight.firstChild, highlight);
      }
      parent.removeChild(highlight);
    }
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
