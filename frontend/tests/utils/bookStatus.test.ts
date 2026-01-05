import { describe, it, expect } from 'vitest';
import type { PDF } from '../../src/types/pdf';
import {
  computeBookStatus,
  getBookStatus,
  shouldPromptFinished,
  matchesStatusFilter,
  groupBooksByStatus,
  calculateStatusCounts,
  getStatusLabel,
  getStatusColor,
} from '../../src/utils/bookStatus';

// Helper to create a minimal PDF object for testing
function createPDF(overrides: Partial<PDF> = {}): PDF {
  return {
    id: 1,
    pdf_id: 1,
    filename: 'test.pdf',
    title: 'Test Book',
    author: 'Test Author',
    num_pages: 100,
    file_size: 1000,
    modified_date: '2024-01-01',
    created_date: '2024-01-01',
    computed_status: 'new',
    ...overrides,
  };
}

describe('computeBookStatus', () => {
  it('returns "new" when there is no reading progress', () => {
    const pdf = createPDF({ reading_progress: undefined });
    expect(computeBookStatus(pdf)).toBe('new');
  });

  it('returns "new" when reading progress is null', () => {
    const pdf = createPDF({ reading_progress: null });
    expect(computeBookStatus(pdf)).toBe('new');
  });

  it('returns "finished" when progress is 95% or higher', () => {
    const pdf = createPDF({
      reading_progress: {
        last_page: 95,
        total_pages: 100,
        progress_percentage: 95,
        last_updated: '2024-01-01',
        status: 'reading',
        status_updated_at: '2024-01-01',
        manually_set: false,
      },
    });
    expect(computeBookStatus(pdf)).toBe('finished');
  });

  it('returns "finished" when progress is 100%', () => {
    const pdf = createPDF({
      reading_progress: {
        last_page: 100,
        total_pages: 100,
        progress_percentage: 100,
        last_updated: '2024-01-01',
        status: 'finished',
        status_updated_at: '2024-01-01',
        manually_set: false,
      },
    });
    expect(computeBookStatus(pdf)).toBe('finished');
  });

  it('returns "reading" when progress is between 0% and 95%', () => {
    const pdf = createPDF({
      reading_progress: {
        last_page: 50,
        total_pages: 100,
        progress_percentage: 50,
        last_updated: '2024-01-01',
        status: 'reading',
        status_updated_at: '2024-01-01',
        manually_set: false,
      },
    });
    expect(computeBookStatus(pdf)).toBe('reading');
  });

  it('returns "new" when progress is exactly 0%', () => {
    const pdf = createPDF({
      reading_progress: {
        last_page: 0,
        total_pages: 100,
        progress_percentage: 0,
        last_updated: '2024-01-01',
        status: 'new',
        status_updated_at: '2024-01-01',
        manually_set: false,
      },
    });
    expect(computeBookStatus(pdf)).toBe('new');
  });
});

describe('getBookStatus', () => {
  it('returns manual_status when set', () => {
    const pdf = createPDF({
      computed_status: 'new',
      manual_status: 'finished',
    });
    expect(getBookStatus(pdf)).toBe('finished');
  });

  it('returns computed_status when manual_status is not set', () => {
    const pdf = createPDF({
      computed_status: 'reading',
      manual_status: undefined,
    });
    expect(getBookStatus(pdf)).toBe('reading');
  });
});

describe('shouldPromptFinished', () => {
  it('returns true when computed is finished but current is not and not manually set', () => {
    const pdf = createPDF({
      computed_status: 'reading',
      manual_status: undefined,
      reading_progress: {
        last_page: 96,
        total_pages: 100,
        progress_percentage: 96,
        last_updated: '2024-01-01',
        status: 'reading',
        status_updated_at: '2024-01-01',
        manually_set: false,
      },
    });
    expect(shouldPromptFinished(pdf)).toBe(true);
  });

  it('returns false when already marked as finished', () => {
    const pdf = createPDF({
      computed_status: 'finished',
      manual_status: 'finished',
      reading_progress: {
        last_page: 100,
        total_pages: 100,
        progress_percentage: 100,
        last_updated: '2024-01-01',
        status: 'finished',
        status_updated_at: '2024-01-01',
        manually_set: false,
      },
    });
    expect(shouldPromptFinished(pdf)).toBe(false);
  });

  it('returns false when manually_set is true', () => {
    const pdf = createPDF({
      computed_status: 'reading',
      reading_progress: {
        last_page: 96,
        total_pages: 100,
        progress_percentage: 96,
        last_updated: '2024-01-01',
        status: 'reading',
        status_updated_at: '2024-01-01',
        manually_set: true,
      },
    });
    expect(shouldPromptFinished(pdf)).toBe(false);
  });
});

describe('matchesStatusFilter', () => {
  it('returns true for "all" filter regardless of status', () => {
    const newPdf = createPDF({ computed_status: 'new' });
    const readingPdf = createPDF({ computed_status: 'reading' });
    const finishedPdf = createPDF({ computed_status: 'finished' });

    expect(matchesStatusFilter(newPdf, 'all')).toBe(true);
    expect(matchesStatusFilter(readingPdf, 'all')).toBe(true);
    expect(matchesStatusFilter(finishedPdf, 'all')).toBe(true);
  });

  it('returns true when status matches filter', () => {
    const pdf = createPDF({ computed_status: 'reading' });
    expect(matchesStatusFilter(pdf, 'reading')).toBe(true);
  });

  it('returns false when status does not match filter', () => {
    const pdf = createPDF({ computed_status: 'new' });
    expect(matchesStatusFilter(pdf, 'finished')).toBe(false);
  });
});

describe('groupBooksByStatus', () => {
  it('groups PDFs by their status correctly', () => {
    const pdfs = [
      createPDF({ id: 1, computed_status: 'new' }),
      createPDF({ id: 2, computed_status: 'reading' }),
      createPDF({ id: 3, computed_status: 'finished' }),
      createPDF({ id: 4, computed_status: 'new' }),
    ];

    const groups = groupBooksByStatus(pdfs);

    expect(groups.new).toHaveLength(2);
    expect(groups.reading).toHaveLength(1);
    expect(groups.finished).toHaveLength(1);
  });

  it('returns empty arrays when no PDFs provided', () => {
    const groups = groupBooksByStatus([]);

    expect(groups.new).toHaveLength(0);
    expect(groups.reading).toHaveLength(0);
    expect(groups.finished).toHaveLength(0);
  });
});

describe('calculateStatusCounts', () => {
  it('calculates correct counts for each status', () => {
    const pdfs = [
      createPDF({ id: 1, computed_status: 'new' }),
      createPDF({ id: 2, computed_status: 'reading' }),
      createPDF({ id: 3, computed_status: 'finished' }),
      createPDF({ id: 4, computed_status: 'new' }),
      createPDF({ id: 5, computed_status: 'reading' }),
    ];

    const counts = calculateStatusCounts(pdfs);

    expect(counts.all).toBe(5);
    expect(counts.new).toBe(2);
    expect(counts.reading).toBe(2);
    expect(counts.finished).toBe(1);
  });

  it('returns all zeros for empty array', () => {
    const counts = calculateStatusCounts([]);

    expect(counts.all).toBe(0);
    expect(counts.new).toBe(0);
    expect(counts.reading).toBe(0);
    expect(counts.finished).toBe(0);
  });
});

describe('getStatusLabel', () => {
  it('returns correct label for each status', () => {
    expect(getStatusLabel('new')).toContain('New');
    expect(getStatusLabel('reading')).toContain('Reading');
    expect(getStatusLabel('finished')).toContain('Finished');
  });
});

describe('getStatusColor', () => {
  it('returns correct color class for each status', () => {
    expect(getStatusColor('new')).toBe('text-gray-600');
    expect(getStatusColor('reading')).toBe('text-blue-600');
    expect(getStatusColor('finished')).toBe('text-green-600');
  });
});
