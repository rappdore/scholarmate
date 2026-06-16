import { generateXPath, getElementByXPath } from './epubHighlights';

// ScholarMate CFI subset: current_nav_id identifies the EPUB section; this
// locator records a rendered-section XPath, text offset, and snippet.
const CFI_PREFIX = 'epubcfi(/scholarmate!';
const CFI_SUFFIX = ')';
const SNIPPET_RADIUS = 40;

interface ScholarMateCfiPayload {
  version: 1;
  xpath: string;
  offset: number;
  textSnippet: string;
}

export interface EpubCfiResult {
  cfi: string;
  textSnippet: string;
}

export interface EpubCfiResolveResult {
  range: Range;
  textMatched: boolean;
}

interface TextCandidate {
  node: Text;
  offset: number;
  distanceFromTop: number;
}

function getContentRoot(container: HTMLElement): HTMLElement {
  return (
    container.querySelector<HTMLElement>('.epub-content-container') ?? container
  );
}

function isSkippableElement(element: Element | null): boolean {
  const tagName = element?.tagName.toLowerCase();
  return tagName === 'script' || tagName === 'style' || tagName === 'noscript';
}

function findFirstMeaningfulOffset(text: string): number {
  const match = /\S/.exec(text);
  return match?.index ?? 0;
}

function normalizeSnippet(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

function makeSnippet(text: string, offset: number): string {
  const start = Math.max(0, offset - SNIPPET_RADIUS);
  const end = Math.min(text.length, offset + SNIPPET_RADIUS);
  return normalizeSnippet(text.slice(start, end));
}

function encodePayload(payload: ScholarMateCfiPayload): string {
  return `${CFI_PREFIX}${encodeURIComponent(JSON.stringify(payload))}${CFI_SUFFIX}`;
}

function decodePayload(cfi: string): ScholarMateCfiPayload | null {
  if (!cfi.startsWith(CFI_PREFIX) || !cfi.endsWith(CFI_SUFFIX)) {
    return null;
  }

  try {
    const encoded = cfi.slice(CFI_PREFIX.length, -CFI_SUFFIX.length);
    const payload = JSON.parse(
      decodeURIComponent(encoded)
    ) as Partial<ScholarMateCfiPayload>;

    if (
      payload.version !== 1 ||
      typeof payload.xpath !== 'string' ||
      typeof payload.offset !== 'number' ||
      typeof payload.textSnippet !== 'string'
    ) {
      return null;
    }

    return {
      version: 1,
      xpath: payload.xpath,
      offset: Math.max(0, Math.floor(payload.offset)),
      textSnippet: payload.textSnippet,
    };
  } catch {
    return null;
  }
}

function walkTextNodes(root: HTMLElement): Text[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (isSkippableElement(parent)) {
        return NodeFilter.FILTER_REJECT;
      }
      if (!node.textContent || !/\S/.test(node.textContent)) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  const nodes: Text[] = [];
  let current = walker.nextNode();
  while (current) {
    nodes.push(current as Text);
    current = walker.nextNode();
  }
  return nodes;
}

function getRangeRect(range: Range): DOMRect | null {
  const geometryRange = range as Range & {
    getClientRects?: () => DOMRectList;
    getBoundingClientRect?: () => DOMRect;
  };
  const rects = geometryRange.getClientRects
    ? Array.from(geometryRange.getClientRects())
    : [];
  const visibleRect = rects.find(rect => rect.width > 0 || rect.height > 0);
  if (visibleRect) {
    return visibleRect;
  }

  const rect = geometryRange.getBoundingClientRect?.();
  if (rect && (rect.width > 0 || rect.height > 0)) {
    return rect;
  }

  return null;
}

function buildCandidate(
  node: Text,
  containerRect: DOMRect,
  topPaddingPx: number
): TextCandidate | null {
  const text = node.textContent ?? '';
  const offset = findFirstMeaningfulOffset(text);
  const range = document.createRange();
  range.setStart(node, offset);
  range.setEnd(node, Math.min(text.length, offset + 1));

  const rect = getRangeRect(range);

  if (!rect) {
    return {
      node,
      offset,
      distanceFromTop: Number.MAX_SAFE_INTEGER,
    };
  }

  const viewportTop = containerRect.top + topPaddingPx;
  const viewportBottom = containerRect.bottom;
  if (rect.bottom < viewportTop || rect.top > viewportBottom) {
    return null;
  }

  return {
    node,
    offset,
    distanceFromTop: Math.abs(rect.top - viewportTop),
  };
}

function findBestVisibleTextNode(
  container: HTMLElement,
  root: HTMLElement
): TextCandidate | null {
  const textNodes = walkTextNodes(root);
  const containerRect = container.getBoundingClientRect();
  const topPaddingPx = 8;
  let bestCandidate: TextCandidate | null = null;

  for (const node of textNodes) {
    const candidate = buildCandidate(node, containerRect, topPaddingPx);
    if (
      candidate &&
      (!bestCandidate ||
        candidate.distanceFromTop < bestCandidate.distanceFromTop)
    ) {
      bestCandidate = candidate;
    }
  }

  return bestCandidate;
}

function createCollapsedRange(node: Text, offset: number): Range | null {
  const safeOffset = Math.min(
    Math.max(0, offset),
    node.textContent?.length ?? 0
  );
  const range = document.createRange();
  try {
    range.setStart(node, safeOffset);
    range.collapse(true);
    return range;
  } catch {
    return null;
  }
}

function findRangeBySnippet(
  root: HTMLElement,
  snippet: string
): EpubCfiResolveResult | null {
  const normalizedSnippet = normalizeSnippet(snippet);
  if (!normalizedSnippet) {
    return null;
  }

  for (const node of walkTextNodes(root)) {
    const text = node.textContent ?? '';
    const index = text.indexOf(snippet);
    if (index >= 0) {
      const range = createCollapsedRange(node, index);
      return range ? { range, textMatched: true } : null;
    }

    if (normalizeSnippet(text).includes(normalizedSnippet)) {
      const range = createCollapsedRange(node, findFirstMeaningfulOffset(text));
      return range ? { range, textMatched: true } : null;
    }
  }

  return null;
}

function snippetMatchesAtOffset(
  node: Text,
  offset: number,
  snippet: string
): boolean {
  const text = node.textContent ?? '';
  const localSnippet = makeSnippet(text, offset);
  return Boolean(
    localSnippet &&
      snippet &&
      (localSnippet.includes(snippet) || snippet.includes(localSnippet))
  );
}

export function captureVisibleEpubCfi(
  container: HTMLElement
): EpubCfiResult | null {
  const root = getContentRoot(container);
  const candidate = findBestVisibleTextNode(container, root);
  if (!candidate) {
    return null;
  }

  const text = candidate.node.textContent ?? '';
  const textSnippet = makeSnippet(text, candidate.offset);
  if (!textSnippet) {
    return null;
  }

  const payload: ScholarMateCfiPayload = {
    version: 1,
    xpath: generateXPath(candidate.node),
    offset: candidate.offset,
    textSnippet,
  };
  if (!payload.xpath) {
    return null;
  }

  return {
    cfi: encodePayload(payload),
    textSnippet,
  };
}

export function resolveEpubCfi(
  cfi: string,
  container: HTMLElement
): EpubCfiResolveResult | null {
  const payload = decodePayload(cfi);
  if (!payload) {
    return null;
  }

  const root = getContentRoot(container);
  const node = getElementByXPath(payload.xpath, root);
  if (node?.nodeType === Node.TEXT_NODE) {
    const textNode = node as Text;
    const range = createCollapsedRange(textNode, payload.offset);
    if (
      range &&
      snippetMatchesAtOffset(textNode, payload.offset, payload.textSnippet)
    ) {
      return { range, textMatched: true };
    }
  }

  return findRangeBySnippet(root, payload.textSnippet);
}

export function scrollRangeIntoEpubContainer(
  container: HTMLElement,
  range: Range,
  options: { topPaddingPx?: number } = {}
): void {
  const topPaddingPx = options.topPaddingPx ?? 24;
  const rect = getRangeRect(range);
  if (!rect) {
    return;
  }

  const containerRect = container.getBoundingClientRect();
  const top = Math.max(
    0,
    container.scrollTop + rect.top - containerRect.top - topPaddingPx
  );

  if (typeof container.scrollTo === 'function') {
    container.scrollTo({ top, behavior: 'auto' });
    return;
  }

  container.scrollTop = top;
}
