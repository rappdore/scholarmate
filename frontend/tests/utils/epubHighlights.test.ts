import { describe, it, expect } from 'vitest';
import { extractChapterIdFromNavId } from '../../src/utils/epubHighlights';

describe('extractChapterIdFromNavId', () => {
  it('maps hierarchical section ids to their chapter', () => {
    expect(extractChapterIdFromNavId('section_2_1_3')).toBe('chapter_2');
    expect(extractChapterIdFromNavId('section_10')).toBe('chapter_10');
  });

  it('truncates chapter ids to the first two parts', () => {
    expect(extractChapterIdFromNavId('chapter_5_2')).toBe('chapter_5');
    expect(extractChapterIdFromNavId('chapter_3')).toBe('chapter_3');
  });

  it('returns the navId unchanged when it contains "chapter" but no underscore', () => {
    // Regression: previously produced 'chapter_undefined'
    expect(extractChapterIdFromNavId('chapter')).toBe('chapter');
    expect(extractChapterIdFromNavId('mychapter')).toBe('mychapter');
  });

  it('returns unrecognized navIds unchanged', () => {
    expect(extractChapterIdFromNavId('intro')).toBe('intro');
    expect(extractChapterIdFromNavId('toc_1')).toBe('toc_1');
  });
});
