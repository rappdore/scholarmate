import { describe, it, expect } from 'vitest';
import {
  HIGHLIGHT_COLORS,
  DEFAULT_HIGHLIGHT_COLOR,
  highlightColorHex,
  highlightColorLabel,
  toHighlightColor,
} from '../../src/types/highlights';

describe('canonical highlight color model', () => {
  it('maps every color name to its hex value and back', () => {
    for (const { name, hex } of HIGHLIGHT_COLORS) {
      expect(highlightColorHex(name)).toBe(hex);
      expect(toHighlightColor(hex)).toBe(name);
    }
  });

  it('passes canonical names through toHighlightColor unchanged', () => {
    for (const { name } of HIGHLIGHT_COLORS) {
      expect(toHighlightColor(name)).toBe(name);
    }
  });

  it('normalizes case before matching', () => {
    expect(toHighlightColor('#FFFF00')).toBe('yellow');
    expect(toHighlightColor('Yellow')).toBe('yellow');
  });

  it('falls back to yellow for unknown values', () => {
    expect(toHighlightColor('#123456')).toBe(DEFAULT_HIGHLIGHT_COLOR);
    expect(toHighlightColor('magenta')).toBe(DEFAULT_HIGHLIGHT_COLOR);
    expect(toHighlightColor('')).toBe(DEFAULT_HIGHLIGHT_COLOR);
  });

  it('has a label for every color', () => {
    for (const { name, label } of HIGHLIGHT_COLORS) {
      expect(highlightColorLabel(name)).toBe(label);
    }
  });
});
