import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  captureVisibleEpubCfi,
  type EpubCfiResult,
  resolveEpubCfi,
  scrollRangeIntoEpubContainer,
} from '../../src/utils/epubCfi';

type RangeGeometryMethodName = 'getClientRects' | 'getBoundingClientRect';
type RangeWithOptionalGeometry = Range &
  Partial<Record<RangeGeometryMethodName, () => DOMRectList | DOMRect>>;

const originalRangeGetClientRects = (
  Range.prototype as RangeWithOptionalGeometry
).getClientRects;
const originalRangeGetBoundingClientRect = (
  Range.prototype as RangeWithOptionalGeometry
).getBoundingClientRect;

function setupContent(html: string): HTMLElement {
  document.body.innerHTML = `
    <div id="reader">
      <div class="epub-content-container">${html}</div>
    </div>
  `;
  return document.querySelector<HTMLElement>('#reader')!;
}

function rect(top: number, height = 10): DOMRect {
  return {
    x: 0,
    y: top,
    top,
    bottom: top + height,
    left: 0,
    right: 100,
    width: 100,
    height,
    toJSON: () => ({}),
  } as DOMRect;
}

function expectCaptured(captured: EpubCfiResult | null): EpubCfiResult {
  expect(captured).not.toBeNull();
  if (!captured) {
    throw new Error('Expected EPUB CFI capture to succeed');
  }
  return captured;
}

afterEach(() => {
  document.body.innerHTML = '';
  vi.restoreAllMocks();
  restoreRangeMethod('getClientRects', originalRangeGetClientRects);
  restoreRangeMethod(
    'getBoundingClientRect',
    originalRangeGetBoundingClientRect
  );
});

function restoreRangeMethod(
  name: RangeGeometryMethodName,
  original: (() => DOMRectList | DOMRect) | undefined
): void {
  if (original) {
    Object.defineProperty(Range.prototype, name, {
      value: original,
      configurable: true,
    });
    return;
  }
  delete (Range.prototype as Partial<Record<RangeGeometryMethodName, unknown>>)[
    name
  ];
}

describe('EPUB CFI utility', () => {
  it('captures and resolves a locator for the first visible text node', () => {
    const container = setupContent(`
      <p>First paragraph text.</p>
      <p>Second paragraph text.</p>
    `);

    const captured = expectCaptured(captureVisibleEpubCfi(container));

    expect(captured.cfi).toMatch(/^epubcfi\(/);
    expect(captured.textSnippet).toContain('First paragraph text.');

    const resolved = resolveEpubCfi(captured.cfi, container);
    expect(resolved?.range.startContainer.textContent).toBe(
      'First paragraph text.'
    );
    expect(resolved?.textMatched).toBe(true);
  });

  it('uses viewport geometry when range rectangles are available', () => {
    const container = setupContent(`
      <p>Offscreen paragraph text.</p>
      <p>Visible paragraph text.</p>
    `);
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(
      rect(100, 400)
    );
    Object.defineProperty(Range.prototype, 'getClientRects', {
      value: () => [] as unknown as DOMRectList,
      configurable: true,
    });
    Object.defineProperty(Range.prototype, 'getBoundingClientRect', {
      value: function (this: Range) {
        return this.startContainer.textContent?.includes('Visible')
          ? rect(140)
          : rect(700);
      },
      configurable: true,
    });

    const captured = expectCaptured(captureVisibleEpubCfi(container));
    const resolved = resolveEpubCfi(captured.cfi, container);

    expect(resolved?.range.startContainer.textContent).toBe(
      'Visible paragraph text.'
    );
  });

  it('falls back to snippet matching when the stored XPath no longer resolves', () => {
    const container = setupContent('<p>Stable semantic paragraph.</p>');
    const captured = expectCaptured(captureVisibleEpubCfi(container));

    const content = container.querySelector<HTMLElement>(
      '.epub-content-container'
    )!;
    content.innerHTML = '<section><p>Stable semantic paragraph.</p></section>';

    const resolved = resolveEpubCfi(captured.cfi, container);

    expect(resolved?.range.startContainer.textContent).toBe(
      'Stable semantic paragraph.'
    );
    expect(resolved?.textMatched).toBe(true);
  });

  it('falls back to snippet matching when the stored XPath points at changed text', () => {
    const container = setupContent('<p>Original semantic paragraph.</p>');
    const captured = expectCaptured(captureVisibleEpubCfi(container));

    const content = container.querySelector<HTMLElement>(
      '.epub-content-container'
    )!;
    content.innerHTML = `
      <p>Different text at the old path.</p>
      <section><p>Original semantic paragraph.</p></section>
    `;

    const resolved = resolveEpubCfi(captured.cfi, container);

    expect(resolved?.range.startContainer.textContent).toBe(
      'Original semantic paragraph.'
    );
    expect(resolved?.textMatched).toBe(true);
  });

  it('returns null for unsupported CFI strings', () => {
    const container = setupContent('<p>Paragraph text.</p>');

    expect(resolveEpubCfi('epubcfi(/6/2[chapter])', container)).toBeNull();
    expect(resolveEpubCfi('not-a-cfi', container)).toBeNull();
  });

  it('scrolls a resolved range into the EPUB container', () => {
    const container = setupContent('<p>Paragraph text.</p>');
    const text = container.querySelector('p')!.firstChild as Text;
    const range = document.createRange();
    range.setStart(text, 0);
    range.collapse(true);
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(
      rect(100, 400)
    );
    Object.defineProperty(range, 'getClientRects', {
      value: () => [] as unknown as DOMRectList,
      configurable: true,
    });
    Object.defineProperty(range, 'getBoundingClientRect', {
      value: () => rect(250),
      configurable: true,
    });
    const scrollTo = vi.fn(({ top }: ScrollToOptions) => {
      container.scrollTop = top ?? 0;
    });
    Object.defineProperty(container, 'scrollTo', {
      value: scrollTo,
      configurable: true,
    });

    scrollRangeIntoEpubContainer(container, range, { topPaddingPx: 20 });

    expect(scrollTo).toHaveBeenCalledWith({ top: 130, behavior: 'auto' });
    expect(container.scrollTop).toBe(130);
  });
});
