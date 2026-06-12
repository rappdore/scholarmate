import { describe, it, expect, vi, beforeEach } from 'vitest';
import { documentApi } from '../../src/services/documentApi';
import {
  pdfService,
  notesService,
  epubNotesService,
} from '../../src/services/api';
import { epubService } from '../../src/services/epubService';

vi.mock('../../src/services/api', () => ({
  pdfService: {
    listPDFs: vi.fn(),
    getStatusCounts: vi.fn(),
    updateBookStatus: vi.fn(),
    deleteBook: vi.fn(),
    getThumbnailUrl: vi.fn(),
    refreshPDFCache: vi.fn(),
  },
  notesService: {
    getChatNotesForPdf: vi.fn(),
    deleteChatNote: vi.fn(),
  },
  epubNotesService: {
    getChatNotesForEpub: vi.fn(),
    deleteChatNote: vi.fn(),
  },
}));

vi.mock('../../src/services/epubService', () => ({
  epubService: {
    listEPUBs: vi.fn(),
    getEPUBStatusCounts: vi.fn(),
    updateEPUBBookStatus: vi.fn(),
    deleteEPUBBook: vi.fn(),
    getThumbnailUrl: vi.fn(),
    refreshEPUBCache: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('documentApi.listAll', () => {
  it('merges PDFs and EPUBs and derives status fields', async () => {
    vi.mocked(pdfService.listPDFs).mockResolvedValue([
      {
        id: 1,
        title: 'A PDF',
        reading_progress: { status: 'reading', manually_set: true },
      },
    ] as never);
    vi.mocked(epubService.listEPUBs).mockResolvedValue([
      { id: 1, type: 'epub', title: 'An EPUB', reading_progress: null },
    ] as never);

    const docs = await documentApi.listAll();

    expect(docs).toHaveLength(2);
    const pdf = docs.find(d => d.type === 'pdf')!;
    expect(pdf.computed_status).toBe('reading');
    expect(pdf.manual_status).toBe('reading');
    const epub = docs.find(d => d.type === 'epub')!;
    expect(epub.computed_status).toBe('new');
    expect(epub.manual_status).toBeUndefined();
  });

  it('tolerates one failing service', async () => {
    vi.mocked(pdfService.listPDFs).mockRejectedValue(new Error('down'));
    vi.mocked(epubService.listEPUBs).mockResolvedValue([
      { id: 2, type: 'epub', title: 'B' },
    ] as never);

    const docs = await documentApi.listAll();
    expect(docs).toHaveLength(1);
    expect(docs[0].type).toBe('epub');
  });
});

describe('documentApi.statusCounts', () => {
  it('combines counts across formats', async () => {
    vi.mocked(pdfService.getStatusCounts).mockResolvedValue({
      all: 6,
      new: 1,
      reading: 2,
      finished: 3,
    });
    vi.mocked(epubService.getEPUBStatusCounts).mockResolvedValue({
      new: 4,
      reading: 0,
      finished: 1,
    });

    expect(await documentApi.statusCounts()).toEqual({
      all: 11,
      new: 5,
      reading: 2,
      finished: 4,
    });
  });

  it('treats a failing service as zero counts', async () => {
    vi.mocked(pdfService.getStatusCounts).mockRejectedValue(new Error('down'));
    vi.mocked(epubService.getEPUBStatusCounts).mockResolvedValue({
      new: 1,
      reading: 1,
      finished: 0,
    });

    expect(await documentApi.statusCounts()).toEqual({
      all: 2,
      new: 1,
      reading: 1,
      finished: 0,
    });
  });
});

describe('documentApi type dispatch', () => {
  it('routes status updates by document type', async () => {
    await documentApi.updateStatus('pdf', 1, 'finished');
    expect(pdfService.updateBookStatus).toHaveBeenCalledWith(
      1,
      'finished',
      true
    );

    await documentApi.updateStatus('epub', 2, 'reading', false);
    expect(epubService.updateEPUBBookStatus).toHaveBeenCalledWith(
      2,
      'reading',
      false
    );
  });

  it('routes deletes by document type', async () => {
    await documentApi.deleteDocument('pdf', 1);
    expect(pdfService.deleteBook).toHaveBeenCalledWith(1);

    await documentApi.deleteDocument('epub', 2);
    expect(epubService.deleteEPUBBook).toHaveBeenCalledWith(2);
  });

  it('routes thumbnail URLs by document type', () => {
    vi.mocked(pdfService.getThumbnailUrl).mockReturnValue('/pdf-thumb');
    vi.mocked(epubService.getThumbnailUrl).mockReturnValue('/epub-thumb');

    expect(documentApi.thumbnailUrl('pdf', 1)).toBe('/pdf-thumb');
    expect(documentApi.thumbnailUrl('epub', 1)).toBe('/epub-thumb');
  });

  it('routes note reads and deletes by document type', async () => {
    vi.mocked(notesService.getChatNotesForPdf).mockResolvedValue([]);
    vi.mocked(epubNotesService.getChatNotesForEpub).mockResolvedValue([]);

    await documentApi.getChatNotes('pdf', 3);
    expect(notesService.getChatNotesForPdf).toHaveBeenCalledWith(3);

    await documentApi.getChatNotes('epub', 4);
    expect(epubNotesService.getChatNotesForEpub).toHaveBeenCalledWith(4);

    await documentApi.deleteChatNote('pdf', 10);
    expect(notesService.deleteChatNote).toHaveBeenCalledWith(10);

    await documentApi.deleteChatNote('epub', 11);
    expect(epubNotesService.deleteChatNote).toHaveBeenCalledWith(11);
  });

  it('refreshes both caches and reports counts', async () => {
    vi.mocked(pdfService.refreshPDFCache).mockResolvedValue({
      success: true,
      cache_built_at: '',
      pdf_count: 7,
      message: '',
    });
    vi.mocked(epubService.refreshEPUBCache).mockResolvedValue({
      success: true,
      cache_built_at: '',
      epub_count: 3,
      message: '',
    });

    expect(await documentApi.refreshCaches()).toEqual({
      pdf_count: 7,
      epub_count: 3,
    });
  });
});
