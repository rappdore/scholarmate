import { StrictMode } from 'react';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SimpleResizablePanels from '../../src/components/SimpleResizablePanels';

const STORAGE_KEY = 'pdf-reader-simple-left-width';

function renderPanels() {
  return render(
    <StrictMode>
      <SimpleResizablePanels
        leftPanel={<div>reader content</div>}
        rightPanel={<div>ai content</div>}
      />
    </StrictMode>
  );
}

function leftPanel() {
  return screen.getByTestId('reader-left-panel');
}

describe('SimpleResizablePanels split persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('defaults to an even split when no saved width exists', () => {
    renderPanels();

    expect(leftPanel()).toHaveStyle({ width: '50%' });
  });

  it('hydrates a saved width immediately under StrictMode', () => {
    localStorage.setItem(STORAGE_KEY, '63');

    renderPanels();

    expect(leftPanel()).toHaveStyle({ width: '63%' });
    expect(localStorage.getItem(STORAGE_KEY)).toBe('63');
  });

  it('clamps saved widths to the supported range', () => {
    localStorage.setItem(STORAGE_KEY, '95');

    renderPanels();

    expect(leftPanel()).toHaveStyle({ width: '80%' });
    expect(localStorage.getItem(STORAGE_KEY)).toBe('80');
  });

  it('falls back to the default width when saved data is corrupt', () => {
    localStorage.setItem(STORAGE_KEY, 'not-a-number');

    renderPanels();

    expect(leftPanel()).toHaveStyle({ width: '50%' });
    expect(localStorage.getItem(STORAGE_KEY)).toBe('50');
  });

  it('falls back to the default width when saved data is empty', () => {
    localStorage.setItem(STORAGE_KEY, '');

    renderPanels();

    expect(leftPanel()).toHaveStyle({ width: '50%' });
    expect(localStorage.getItem(STORAGE_KEY)).toBe('50');
  });

  it('saves the dragged width for the next reader mount', async () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 1000,
      bottom: 600,
      width: 1000,
      height: 600,
      toJSON: () => ({}),
    });

    renderPanels();

    fireEvent.mouseDown(screen.getByTestId('reader-splitter'));
    fireEvent.mouseMove(document, { clientX: 700 });
    fireEvent.mouseUp(document);

    await waitFor(() => {
      expect(leftPanel()).toHaveStyle({ width: '70%' });
      expect(localStorage.getItem(STORAGE_KEY)).toBe('70');
    });
  });
});
