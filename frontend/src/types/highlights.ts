// Highlight-related TypeScript interfaces and types

export interface HighlightCoordinates {
  x: number;
  y: number;
  width: number;
  height: number;
  pageWidth: number;
  pageHeight: number;
  zoom: number;
}

export interface TextSelection {
  text: string;
  startOffset: number;
  endOffset: number;
  coordinates: HighlightCoordinates[];
  pageNumber: number;
}

export interface Highlight {
  id: string; // Will be generated on frontend, then replaced with backend ID
  pdf_id: number; // Primary identifier for the PDF document
  pdfFilename: string; // Keep for backward compatibility and display
  pageNumber: number;
  selectedText: string;
  startOffset: number;
  endOffset: number;
  color: HighlightColor;
  coordinates: HighlightCoordinates[];
  createdAt: Date;
  updatedAt: Date;
}

export enum HighlightColor {
  YELLOW = '#ffff00',
  GREEN = '#00ff00',
  BLUE = '#0080ff',
  PINK = '#ff69b4',
  ORANGE = '#ffa500',
  PURPLE = '#9370db',
  RED = '#ff4444',
  CYAN = '#00ffff',
}

export interface HighlightRequest {
  pdf_id: number; // Use ID instead of filename for API requests
  pdfFilename?: string; // Optional, for backward compatibility during transition
  pageNumber: number;
  selectedText: string;
  startOffset: number;
  endOffset: number;
  color: HighlightColor;
  coordinates: HighlightCoordinates[];
}

export interface HighlightResponse {
  id: number;
  pdf_id: number; // Primary identifier for the PDF document
  pdfFilename: string; // Keep for backward compatibility
  pageNumber: number;
  selectedText: string;
  startOffset: number;
  endOffset: number;
  color: HighlightColor;
  coordinates: string; // JSON string from backend
  createdAt: string;
  updatedAt: string;
}

export interface UpdateColorRequest {
  color: HighlightColor;
}

// UI-specific types
export interface HighlightContextMenu {
  x: number;
  y: number;
  visible: boolean;
  selectedText: string;
  selection: TextSelection | null;
}

export interface HighlightState {
  highlights: Highlight[];
  selectedHighlight: Highlight | null;
  isLoading: boolean;
  error: string | null;
  contextMenu: HighlightContextMenu;
}

// Utility type for creating highlights without backend-specific fields
// Includes pdf_id as required, pdfFilename optional for display
export type CreateHighlightData = Omit<
  Highlight,
  'id' | 'createdAt' | 'updatedAt'
>;
