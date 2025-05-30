import type { BookStatus, PDF } from '../types/pdf';

/**
 * Determines the computed status of a book based on its reading progress
 */
export function computeBookStatus(pdf: PDF): BookStatus {
  // If there's no reading progress, it's a new book
  if (!pdf.reading_progress) {
    return 'new';
  }

  const progress = pdf.reading_progress.progress_percentage;

  // If progress is 95% or higher, consider it finished
  if (progress >= 95) {
    return 'finished';
  }

  // If there's any progress (more than 0%), it's being read
  if (progress > 0) {
    return 'reading';
  }

  // Default to new if no meaningful progress
  return 'new';
}

/**
 * Gets the effective book status, prioritizing manual status over computed status
 */
export function getBookStatus(pdf: PDF): BookStatus {
  // If there's a manual status set, use that
  if (pdf.manual_status) {
    return pdf.manual_status;
  }

  // Otherwise, use the computed status
  return pdf.computed_status;
}

/**
 * Determines if we should prompt the user to mark a book as finished
 * This happens when:
 * 1. The computed status is 'finished' (95%+ progress)
 * 2. The current effective status is not already 'finished'
 * 3. The status hasn't been manually set (to avoid re-prompting)
 */
export function shouldPromptFinished(pdf: PDF): boolean {
  const computedStatus = computeBookStatus(pdf);
  const currentStatus = getBookStatus(pdf);
  const isManuallySet = pdf.reading_progress?.manually_set || false;

  return (
    computedStatus === 'finished' &&
    currentStatus !== 'finished' &&
    !isManuallySet
  );
}

/**
 * Checks if a book matches a given status filter
 */
export function matchesStatusFilter(
  pdf: PDF,
  filter: 'all' | BookStatus
): boolean {
  if (filter === 'all') {
    return true;
  }

  return getBookStatus(pdf) === filter;
}

/**
 * Groups an array of PDFs by their status
 */
export function groupBooksByStatus(pdfs: PDF[]): Record<BookStatus, PDF[]> {
  return pdfs.reduce(
    (groups, pdf) => {
      const status = getBookStatus(pdf);
      groups[status].push(pdf);
      return groups;
    },
    { new: [], reading: [], finished: [] } as Record<BookStatus, PDF[]>
  );
}

/**
 * Calculates status counts from an array of PDFs
 */
export function calculateStatusCounts(pdfs: PDF[]): {
  all: number;
  new: number;
  reading: number;
  finished: number;
} {
  const groups = groupBooksByStatus(pdfs);

  return {
    all: pdfs.length,
    new: groups.new.length,
    reading: groups.reading.length,
    finished: groups.finished.length,
  };
}

/**
 * Gets a human-readable status label with emoji
 */
export function getStatusLabel(status: BookStatus): string {
  const labels = {
    new: '📚 New',
    reading: '📖 Reading',
    finished: '✅ Finished',
  };

  return labels[status];
}

/**
 * Gets the CSS color class for a status
 */
export function getStatusColor(status: BookStatus): string {
  const colors = {
    new: 'text-gray-600',
    reading: 'text-blue-600',
    finished: 'text-green-600',
  };

  return colors[status];
}
