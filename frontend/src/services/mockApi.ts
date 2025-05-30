import type { BookStatus, PDF } from '../types/pdf';

// Mock data for development - simulates backend responses
let mockStatusCounts = {
  all: 0,
  new: 0,
  reading: 0,
  finished: 0,
};

// In-memory storage for book statuses during mocked development
const mockBookStatuses = new Map<
  string,
  { status: BookStatus; manually_set: boolean; updated_at: string }
>();

export const mockPdfService = {
  /**
   * Update book status for a specific book
   */
  updateBookStatus: async (
    filename: string,
    status: BookStatus,
    manually_set: boolean = true
  ): Promise<void> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 200));

    // Store the status update
    mockBookStatuses.set(filename, {
      status,
      manually_set,
      updated_at: new Date().toISOString(),
    });

    console.log(`Mock: Updated book status for "${filename}" to "${status}"`);
  },

  /**
   * Delete a book and all its associated data
   */
  deleteBook: async (filename: string): Promise<void> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 300));

    // Remove from mock storage
    mockBookStatuses.delete(filename);

    console.log(`Mock: Deleted book "${filename}"`);
  },

  /**
   * List PDFs filtered by status
   */
  listPDFsByStatus: async (status?: BookStatus): Promise<PDF[]> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 400));

    // This would normally call the real API
    // For now, return empty array as we'll integrate with existing pdfService.listPDFs()
    console.log(`Mock: Fetching books with status: ${status || 'all'}`);
    return [];
  },

  /**
   * Get counts of books by status
   */
  getStatusCounts: async (): Promise<{
    all: number;
    new: number;
    reading: number;
    finished: number;
  }> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 150));

    // In a real implementation, this would query the backend
    // For now, return mock counts that will be updated as we develop
    return { ...mockStatusCounts };
  },

  /**
   * Get the current status of a book from mock storage
   */
  getBookStatus: (
    filename: string
  ): {
    status: BookStatus;
    manually_set: boolean;
    updated_at: string;
  } | null => {
    return mockBookStatuses.get(filename) || null;
  },

  /**
   * Update mock status counts (for development testing)
   */
  updateMockCounts: (counts: Partial<typeof mockStatusCounts>) => {
    mockStatusCounts = { ...mockStatusCounts, ...counts };
  },
};

// Development helper to initialize with some test data
export const initializeMockData = () => {
  mockStatusCounts = {
    all: 12,
    new: 4,
    reading: 6,
    finished: 2,
  };

  // Add some mock book statuses for testing
  mockBookStatuses.set('sample-book-1.pdf', {
    status: 'reading',
    manually_set: false,
    updated_at: new Date().toISOString(),
  });

  mockBookStatuses.set('sample-book-2.pdf', {
    status: 'finished',
    manually_set: true,
    updated_at: new Date().toISOString(),
  });

  console.log('Mock API data initialized for development');
};
