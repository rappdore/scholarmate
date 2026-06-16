import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'fs';
import { EventEmitter } from 'events';
import os from 'os';
import path from 'path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Rectangle } from 'electron';
import {
  getBrowserWindowBounds,
  getDefaultWindowState,
  getWindowStateFilePath,
  loadWindowState,
  manageWindowState,
  normalizeWindowState,
  restoreWindowState,
  saveWindowState,
} from '../../electron/windowState';

const DISPLAYS = [
  {
    bounds: { x: 0, y: 0, width: 1920, height: 1080 },
    workArea: { x: 0, y: 25, width: 1920, height: 1055 },
  },
];

class FakeWindow extends EventEmitter {
  bounds: Rectangle = { x: 50, y: 60, width: 1200, height: 800 };
  normalBounds: Rectangle = { x: 70, y: 80, width: 1100, height: 700 };
  normal = true;
  maximized = false;
  fullScreen = false;

  getBounds(): Rectangle {
    return this.bounds;
  }

  getNormalBounds(): Rectangle {
    return this.normalBounds;
  }

  isNormal(): boolean {
    return this.normal;
  }

  isMaximized(): boolean {
    return this.maximized;
  }

  isFullScreen(): boolean {
    return this.fullScreen;
  }

  maximize(): void {
    this.maximized = true;
  }

  setFullScreen(fullScreen: boolean): void {
    this.fullScreen = fullScreen;
  }
}

describe('windowState', () => {
  let tempDir: string;
  let stateFilePath: string;

  beforeEach(() => {
    tempDir = mkdtempSync(path.join(os.tmpdir(), 'scholarmate-window-state-'));
    stateFilePath = getWindowStateFilePath(tempDir);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    rmSync(tempDir, { recursive: true, force: true });
  });

  it('loads default bounds when no window state has been saved', () => {
    expect(loadWindowState(stateFilePath, DISPLAYS)).toEqual(
      getDefaultWindowState()
    );
  });

  it('loads valid saved bounds and window presentation flags', () => {
    writeState({
      x: 100,
      y: 125,
      width: 1440,
      height: 900,
      isMaximized: true,
      isFullScreen: false,
    });

    expect(loadWindowState(stateFilePath, DISPLAYS)).toEqual({
      x: 100,
      y: 125,
      width: 1440,
      height: 900,
      isMaximized: true,
      isFullScreen: false,
    });
  });

  it('falls back to defaults when the saved file is corrupt', () => {
    mkdirSync(path.dirname(stateFilePath), { recursive: true });
    writeFileSync(stateFilePath, '{not json');

    expect(loadWindowState(stateFilePath, DISPLAYS)).toEqual(
      getDefaultWindowState()
    );
  });

  it('keeps valid size and presentation flags when saved position is off-screen', () => {
    writeState({
      x: 5000,
      y: 5000,
      width: 1000,
      height: 800,
      isMaximized: true,
    });

    expect(loadWindowState(stateFilePath, DISPLAYS)).toEqual({
      width: 1000,
      height: 800,
      isMaximized: true,
      isFullScreen: false,
    });
  });

  it('rejects undersized saved bounds', () => {
    expect(
      normalizeWindowState(
        {
          x: 100,
          y: 100,
          width: 799,
          height: 600,
        },
        DISPLAYS
      )
    ).toBeNull();
  });

  it('saves state in the app-state directory', () => {
    saveWindowState(stateFilePath, {
      x: 10,
      y: 20,
      width: 1500,
      height: 950,
      isMaximized: false,
      isFullScreen: false,
    });

    expect(existsSync(stateFilePath)).toBe(true);
    expect(JSON.parse(readFileSync(stateFilePath, 'utf8'))).toEqual({
      x: 10,
      y: 20,
      width: 1500,
      height: 950,
      isMaximized: false,
      isFullScreen: false,
    });
  });

  it('omits coordinates from BrowserWindow options when no saved position exists', () => {
    expect(getBrowserWindowBounds(getDefaultWindowState())).toEqual({
      width: 1400,
      height: 900,
    });
  });

  it('restores maximized and fullscreen states after window creation', () => {
    const window = new FakeWindow();

    restoreWindowState(window, {
      width: 1400,
      height: 900,
      isMaximized: true,
      isFullScreen: true,
    });

    expect(window.maximized).toBe(true);
    expect(window.fullScreen).toBe(true);
  });

  it('saves debounced move and resize updates', () => {
    vi.useFakeTimers();
    const window = new FakeWindow();
    manageWindowState(window, stateFilePath);

    window.bounds = { x: 300, y: 200, width: 1300, height: 850 };
    window.emit('move');

    vi.advanceTimersByTime(299);
    expect(existsSync(stateFilePath)).toBe(false);

    vi.advanceTimersByTime(1);
    expect(JSON.parse(readFileSync(stateFilePath, 'utf8'))).toMatchObject({
      x: 300,
      y: 200,
      width: 1300,
      height: 850,
    });
  });

  it('saves immediately when the window closes', () => {
    vi.useFakeTimers();
    const window = new FakeWindow();
    manageWindowState(window, stateFilePath);

    window.bounds = { x: 450, y: 225, width: 1600, height: 950 };
    window.emit('resize');
    window.emit('close');

    expect(JSON.parse(readFileSync(stateFilePath, 'utf8'))).toMatchObject({
      x: 450,
      y: 225,
      width: 1600,
      height: 950,
    });
  });

  function writeState(state: Record<string, unknown>): void {
    saveWindowState(stateFilePath, {
      width: 1400,
      height: 900,
      isMaximized: false,
      isFullScreen: false,
      ...state,
    });
  }
});
