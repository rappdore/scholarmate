import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import EPUBViewer from '../../src/components/EPUBViewer';
import { epubService } from '../../src/services/epubService';
import type {
  EPUBContentResponse,
  EPUBNavigationResponse,
  EPUBProgress,
} from '../../src/services/epubService';
import {
  captureVisibleEpubCfi,
  resolveEpubCfi,
  scrollRangeIntoEpubContainer,
} from '../../src/utils/epubCfi';

const contextMocks = vi.hoisted(() => ({
  createHighlight: vi.fn(),
  setCurrentEpubId: vi.fn(),
  getHighlightsForSection: vi.fn(() => []),
}));

const sessionMocks = vi.hoisted(() => ({
  setTrackingEnabled: vi.fn(),
}));

vi.mock('../../src/contexts/EPUBHighlightsContext', () => ({
  useEPUBHighlightsContext: () => ({
    createHighlight: contextMocks.createHighlight,
    setCurrentEpubId: contextMocks.setCurrentEpubId,
    getHighlightsForSection: contextMocks.getHighlightsForSection,
  }),
}));

vi.mock('../../src/hooks/useEpubSessionTracking', () => ({
  useEpubSessionTracking: () => ({
    trackingEnabled: false,
    setTrackingEnabled: sessionMocks.setTrackingEnabled,
  }),
}));

vi.mock('../../src/services/epubService', () => ({
  epubService: {
    getNavigation: vi.fn(),
    getStyles: vi.fn(),
    getEPUBProgress: vi.fn(),
    getContent: vi.fn(),
    saveEPUBProgress: vi.fn(),
  },
}));

vi.mock('../../src/utils/epubCfi', () => ({
  captureVisibleEpubCfi: vi.fn(),
  resolveEpubCfi: vi.fn(),
  scrollRangeIntoEpubContainer: vi.fn(),
}));

const NAVIGATION: EPUBNavigationResponse = {
  navigation: [],
  flat_navigation: [
    {
      id: 'section_1',
      title: 'First',
      level: 1,
      parent_id: null,
      order: 0,
      spine_positions: [0],
      child_count: 0,
    },
    {
      id: 'section_2',
      title: 'Second',
      level: 1,
      parent_id: null,
      order: 1,
      spine_positions: [1],
      child_count: 0,
    },
  ],
  spine_length: 2,
  has_toc: true,
};

const CONTENT_BY_NAV_ID: Record<string, EPUBContentResponse> = {
  section_1: {
    nav_id: 'section_1',
    title: 'First',
    content: '<p>First paragraph text.</p>',
    spine_position: 0,
    total_sections: 2,
    progress_percentage: 50,
    previous_nav_id: null,
    next_nav_id: 'section_2',
  },
  section_2: {
    nav_id: 'section_2',
    title: 'Second',
    content: '<p>Second paragraph text.</p>',
    spine_position: 1,
    total_sections: 2,
    progress_percentage: 100,
    previous_nav_id: 'section_1',
    next_nav_id: null,
  },
};

function makeProgress(overrides: Partial<EPUBProgress> = {}): EPUBProgress {
  return {
    id: 1,
    epub_filename: 'book.epub',
    current_nav_id: 'section_1',
    scroll_position: 0,
    epub_cfi: null,
    progress_percentage: 50,
    last_updated: null,
    status: 'reading',
    status_updated_at: null,
    manually_set: false,
    nav_metadata: undefined,
    ...overrides,
  };
}

function setup(progress: EPUBProgress = makeProgress()) {
  vi.mocked(epubService.getNavigation).mockResolvedValue(NAVIGATION);
  vi.mocked(epubService.getStyles).mockResolvedValue({ styles: [], count: 0 });
  vi.mocked(epubService.getEPUBProgress).mockResolvedValue(progress);
  vi.mocked(epubService.getContent).mockImplementation(
    async (_epubId, navId) => {
      return CONTENT_BY_NAV_ID[navId];
    }
  );
  vi.mocked(epubService.saveEPUBProgress).mockResolvedValue({
    success: true,
    message: 'saved',
    id: 1,
    current_nav_id: 'section_1',
    progress_percentage: 50,
  });

  render(<EPUBViewer epubId={1} />);
}

function getScrollContainer(): HTMLElement {
  return document.querySelector('.epub-outer-container')!.parentElement!;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, 'log').mockImplementation(() => {});
  contextMocks.getHighlightsForSection.mockReturnValue([]);
  vi.mocked(captureVisibleEpubCfi).mockReturnValue(null);
  vi.mocked(resolveEpubCfi).mockReturnValue(null);
});

describe('EPUBViewer CFI progress integration', () => {
  it('captures epub_cfi when debounced scroll progress is saved', async () => {
    vi.mocked(captureVisibleEpubCfi).mockReturnValue({
      cfi: 'epubcfi(/scholarmate!captured)',
      textSnippet: 'First paragraph text.',
    });
    setup();

    await screen.findByText('First paragraph text.');
    const scrollContainer = getScrollContainer();
    scrollContainer.scrollTop = 150;
    fireEvent.scroll(scrollContainer);

    await waitFor(
      () =>
        expect(epubService.saveEPUBProgress).toHaveBeenCalledWith(
          1,
          expect.objectContaining({
            current_nav_id: 'section_1',
            scroll_position: 150,
            epub_cfi: 'epubcfi(/scholarmate!captured)',
          })
        ),
      { timeout: 1500 }
    );
  });

  it('omits epub_cfi when same-section capture fails so the backend preserves it', async () => {
    setup(makeProgress({ epub_cfi: 'epubcfi(/scholarmate!saved)' }));

    await screen.findByText('First paragraph text.');
    const scrollContainer = getScrollContainer();
    scrollContainer.scrollTop = 175;
    fireEvent.scroll(scrollContainer);

    await waitFor(
      () =>
        expect(epubService.saveEPUBProgress).toHaveBeenCalledWith(
          1,
          expect.objectContaining({
            current_nav_id: 'section_1',
            scroll_position: 175,
          })
        ),
      { timeout: 1500 }
    );
    const payload = vi.mocked(epubService.saveEPUBProgress).mock.calls[0][1];
    expect('epub_cfi' in payload).toBe(false);
  });

  it('restores from epub_cfi before falling back to scroll_position', async () => {
    vi.mocked(resolveEpubCfi).mockImplementation((_cfi, container) => {
      const text = container.querySelector('p')!.firstChild as Text;
      const range = document.createRange();
      range.setStart(text, 0);
      range.collapse(true);
      return { range, textMatched: true };
    });
    vi.mocked(scrollRangeIntoEpubContainer).mockImplementation(container => {
      container.scrollTop = 222;
    });
    setup(
      makeProgress({
        epub_cfi: 'epubcfi(/scholarmate!saved)',
        scroll_position: 999,
      })
    );

    await screen.findByText('First paragraph text.');

    await waitFor(() =>
      expect(scrollRangeIntoEpubContainer).toHaveBeenCalledWith(
        getScrollContainer(),
        expect.any(Range)
      )
    );
    expect(getScrollContainer().scrollTop).toBe(222);
  });

  it('falls back to scroll_position when saved epub_cfi cannot be resolved', async () => {
    setup(
      makeProgress({
        epub_cfi: 'epubcfi(/scholarmate!saved)',
        scroll_position: 777,
      })
    );

    await screen.findByText('First paragraph text.');

    await waitFor(() => expect(getScrollContainer().scrollTop).toBe(777));
    expect(scrollRangeIntoEpubContainer).not.toHaveBeenCalled();
  });

  it('clears stale epub_cfi when navigation saves before new content renders', async () => {
    vi.mocked(captureVisibleEpubCfi).mockReturnValue({
      cfi: 'epubcfi(/scholarmate!old-section)',
      textSnippet: 'First paragraph text.',
    });
    setup(makeProgress({ epub_cfi: 'epubcfi(/scholarmate!saved)' }));

    await screen.findByText('First paragraph text.');
    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: 'section_2' },
    });

    await waitFor(() =>
      expect(epubService.saveEPUBProgress).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          current_nav_id: 'section_2',
          chapter_title: 'Second',
          scroll_position: 0,
          epub_cfi: null,
        })
      )
    );
  });
});
