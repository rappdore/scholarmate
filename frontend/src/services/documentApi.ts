/**
 * Document-type-agnostic API surface (A-1 frontend unification).
 *
 * The backend keeps per-format routes (/pdf/..., /epub/... — owner decision),
 * but most frontend call sites don't care about the format. This module owns
 * the type dispatch once so pages and panels stop branching on documentType
 * for operations whose semantics are identical across formats.
 *
 * Format-specific operations (progress payloads, note creation anchors,
 * AI context) stay on pdfService/epubService — they differ for real.
 */

import { pdfService, notesService, epubNotesService } from './api';
import { epubService } from './epubService';
import type { Document, DocumentType } from '../types/document';
import type { BookStatus } from '../types/pdf';

export interface StatusCounts {
  all: number;
  new: number;
  reading: number;
  finished: number;
}

const EMPTY_COUNTS = { new: 0, reading: 0, finished: 0 };

export const documentApi = {
  /**
   * List all documents (PDFs and EPUBs merged), with status fields derived
   * from reading progress. A failing service contributes an empty list so
   * one broken format doesn't blank the whole library.
   */
  listAll: async (): Promise<Document[]> => {
    const [pdfData, epubData] = await Promise.all([
      pdfService.listPDFs().catch(() => []),
      epubService.listEPUBs().catch(() => []),
    ]);

    const allDocuments: Document[] = [
      ...pdfData.map(pdf => ({ ...pdf, type: 'pdf' as const })),
      ...epubData,
    ];

    // The backend provides status directly in reading_progress
    return allDocuments.map(doc => {
      const status = (doc.reading_progress?.status || 'new') as BookStatus;
      return {
        ...doc,
        computed_status: status,
        manual_status: doc.reading_progress?.manually_set ? status : undefined,
      };
    });
  },

  /** Combined status counts across both formats. */
  statusCounts: async (): Promise<StatusCounts> => {
    const [pdfCounts, epubCounts] = await Promise.all([
      pdfService.getStatusCounts().catch(() => EMPTY_COUNTS),
      epubService.getEPUBStatusCounts().catch(() => EMPTY_COUNTS),
    ]);

    const sum = (key: 'new' | 'reading' | 'finished') =>
      (pdfCounts[key] ?? 0) + (epubCounts[key] ?? 0);

    return {
      all: sum('new') + sum('reading') + sum('finished'),
      new: sum('new'),
      reading: sum('reading'),
      finished: sum('finished'),
    };
  },

  updateStatus: (
    type: DocumentType,
    id: number,
    status: BookStatus,
    manuallySet: boolean = true
  ): Promise<unknown> =>
    type === 'pdf'
      ? pdfService.updateBookStatus(id, status, manuallySet)
      : epubService.updateEPUBBookStatus(id, status, manuallySet),

  deleteDocument: (type: DocumentType, id: number): Promise<unknown> =>
    type === 'pdf' ? pdfService.deleteBook(id) : epubService.deleteEPUBBook(id),

  thumbnailUrl: (type: DocumentType, id: number): string =>
    type === 'pdf'
      ? pdfService.getThumbnailUrl(id)
      : epubService.getThumbnailUrl(id),

  /** Refresh both backend caches; returns the per-format document counts. */
  refreshCaches: async (): Promise<{
    pdf_count: number;
    epub_count: number;
  }> => {
    const [pdfResult, epubResult] = await Promise.all([
      pdfService.refreshPDFCache(),
      epubService.refreshEPUBCache(),
    ]);
    return {
      pdf_count: pdfResult.pdf_count,
      epub_count: epubResult.epub_count,
    };
  },

  // Notes: reading and deleting are format-agnostic; creation is not
  // (the anchor shapes differ) and stays on the per-format services.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getChatNotes: (type: DocumentType, id: number): Promise<any[]> =>
    type === 'pdf'
      ? notesService.getChatNotesForPdf(id)
      : epubNotesService.getChatNotesForEpub(id),

  deleteChatNote: (type: DocumentType, noteId: number): Promise<unknown> =>
    type === 'pdf'
      ? notesService.deleteChatNote(noteId)
      : epubNotesService.deleteChatNote(noteId),
};
