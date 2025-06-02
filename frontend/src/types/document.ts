import type {
  PDF,
  PDFInfo,
  BookStatus,
  ReadingProgress,
  NotesInfo,
  HighlightsInfo,
} from './pdf';

// Document type discriminator
export type DocumentType = 'pdf' | 'epub';

// Base document interface with common fields
export interface BaseDocument {
  filename: string;
  type: DocumentType;
  title: string;
  author: string;
  file_size: number;
  modified_date: string;
  created_date: string;
  reading_progress?: ReadingProgress | null;
  notes_info?: NotesInfo | null;
  highlights_info?: HighlightsInfo | null;
  error?: string;
  // Status fields for smart categorization
  computed_status: BookStatus;
  manual_status?: BookStatus;
}

// PDF-specific document interface
export interface PDFDocument extends BaseDocument {
  type: 'pdf';
  num_pages: number;
}

// EPUB-specific document interface
export interface EPUBDocument extends BaseDocument {
  type: 'epub';
  chapters: number;
  subject?: string;
  publisher?: string;
  language?: string;
}

// Union type for all documents
export type Document = PDFDocument | EPUBDocument;

// Extended info interfaces
export interface PDFDocumentInfo extends PDFDocument {
  subject?: string;
  creator?: string;
  producer?: string;
  creation_date?: string;
  modification_date?: string;
}

export interface EPUBDocumentInfo extends EPUBDocument {
  // EPUB info is already included in the base interface
}

export type DocumentInfo = PDFDocumentInfo | EPUBDocumentInfo;

// Type guards
export const isPDFDocument = (doc: Document): doc is PDFDocument => {
  return doc.type === 'pdf';
};

export const isEPUBDocument = (doc: Document): doc is EPUBDocument => {
  return doc.type === 'epub';
};

// Utility function to get page/chapter count
export const getDocumentLength = (doc: Document): number => {
  return isPDFDocument(doc) ? doc.num_pages : doc.chapters;
};

// Utility function to get length unit
export const getDocumentLengthUnit = (doc: Document): string => {
  return isPDFDocument(doc) ? 'pages' : 'chapters';
};
