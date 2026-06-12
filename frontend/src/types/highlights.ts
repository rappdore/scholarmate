// Highlight-related TypeScript interfaces and types

// Canonical highlight color model, shared by PDF and EPUB highlights (audit F-13).
// In-app code always uses the color *name*. The PDF wire format and existing PDF
// rows store hex values, so the PDF API boundary converts name<->hex; the EPUB
// wire format and the epub.css highlight classes are keyed by name directly.
export const HIGHLIGHT_COLORS = [
  { name: 'yellow', hex: '#ffff00', label: 'Yellow' },
  { name: 'green', hex: '#00ff00', label: 'Green' },
  { name: 'blue', hex: '#0080ff', label: 'Blue' },
  { name: 'pink', hex: '#ff69b4', label: 'Pink' },
  { name: 'orange', hex: '#ffa500', label: 'Orange' },
  { name: 'purple', hex: '#9370db', label: 'Purple' },
  { name: 'red', hex: '#ff4444', label: 'Red' },
  { name: 'cyan', hex: '#00ffff', label: 'Cyan' },
] as const;

export type HighlightColor = (typeof HIGHLIGHT_COLORS)[number]['name'];

export const DEFAULT_HIGHLIGHT_COLOR: HighlightColor = 'yellow';

export function highlightColorHex(color: HighlightColor): string {
  return HIGHLIGHT_COLORS.find(c => c.name === color)?.hex ?? '#ffff00';
}

export function highlightColorLabel(color: HighlightColor): string {
  return HIGHLIGHT_COLORS.find(c => c.name === color)?.label ?? 'Unknown';
}

/**
 * Normalize a stored color value (name or legacy hex) to a canonical color
 * name. Unknown values fall back to yellow.
 */
export function toHighlightColor(value: string): HighlightColor {
  const normalized = value.toLowerCase();
  const match = HIGHLIGHT_COLORS.find(
    c => c.name === normalized || c.hex === normalized
  );
  return match?.name ?? DEFAULT_HIGHLIGHT_COLOR;
}

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
