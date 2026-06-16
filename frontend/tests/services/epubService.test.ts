import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  epubService,
  type EPUBProgress,
  type EPUBProgressRequest,
} from '../../src/services/epubService';
import { api } from '../../src/services/http';

vi.mock('../../src/services/http', () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

function makeProgress(overrides: Partial<EPUBProgress> = {}): EPUBProgress {
  return {
    id: 1,
    epub_filename: 'book.epub',
    current_nav_id: 'section_1',
    scroll_position: 120,
    epub_cfi: null,
    progress_percentage: 25,
    last_updated: null,
    status: 'reading',
    status_updated_at: null,
    manually_set: false,
    ...overrides,
  };
}

describe('epubService progress', () => {
  it('sends epub_cfi when saving progress', async () => {
    vi.mocked(api.put).mockResolvedValue({
      data: {
        success: true,
        message: 'saved',
        id: 1,
        current_nav_id: 'section_1',
        progress_percentage: 25,
      },
    });
    const progressData: EPUBProgressRequest = {
      current_nav_id: 'section_1',
      scroll_position: 120,
      epub_cfi: 'epubcfi(/4/2[preface]!/4/2/8:42)',
      progress_percentage: 25,
    };

    await epubService.saveEPUBProgress(1, progressData);

    expect(api.put).toHaveBeenCalledWith('/epub/1/progress', progressData);
  });

  it('returns epub_cfi from saved progress', async () => {
    const progress = makeProgress({
      epub_cfi: 'epubcfi(/4/2[preface]!/4/2/8:42)',
    });
    vi.mocked(api.get).mockResolvedValue({ data: progress });

    await expect(epubService.getEPUBProgress(1)).resolves.toEqual(progress);
  });

  it('types all EPUB progress entries with epub_cfi', async () => {
    const response = {
      epub_progress: {
        'book.epub': makeProgress({
          epub_cfi: 'epubcfi(/4/2[preface]!/4/2/8:42)',
        }),
      },
    };
    vi.mocked(api.get).mockResolvedValue({ data: response });

    const result = await epubService.getAllEPUBProgress();

    expect(result.epub_progress['book.epub'].epub_cfi).toBe(
      'epubcfi(/4/2[preface]!/4/2/8:42)'
    );
  });
});
