import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import path from 'path';
import type { Rectangle } from 'electron';

const DEFAULT_WINDOW_WIDTH = 1400;
const DEFAULT_WINDOW_HEIGHT = 900;
export const MIN_WINDOW_WIDTH = 800;
export const MIN_WINDOW_HEIGHT = 600;
const MIN_VISIBLE_WIDTH = 100;
const MIN_VISIBLE_HEIGHT = 100;
const WINDOW_STATE_DIR = 'app-state';
const WINDOW_STATE_FILE = 'window-state.json';
const WINDOW_STATE_SAVE_DELAY_MS = 300;

export interface WindowState {
  x?: number;
  y?: number;
  width: number;
  height: number;
  isMaximized: boolean;
  isFullScreen: boolean;
}

export interface DisplayBounds {
  bounds: Rectangle;
  workArea?: Rectangle;
}

type WindowStateEvent = 'resize' | 'move' | 'close' | 'closed';

export interface WindowStateWindow {
  getBounds(): Rectangle;
  getNormalBounds(): Rectangle;
  isNormal(): boolean;
  isMaximized(): boolean;
  isFullScreen(): boolean;
  maximize(): void;
  setFullScreen(fullScreen: boolean): void;
  on(event: WindowStateEvent, listener: () => void): void;
  off(event: WindowStateEvent, listener: () => void): void;
}

export function getDefaultWindowState(): WindowState {
  return {
    width: DEFAULT_WINDOW_WIDTH,
    height: DEFAULT_WINDOW_HEIGHT,
    isMaximized: false,
    isFullScreen: false,
  };
}

export function getWindowStateFilePath(userDataPath: string): string {
  return path.join(userDataPath, WINDOW_STATE_DIR, WINDOW_STATE_FILE);
}

export function getBrowserWindowBounds(state: WindowState): {
  x?: number;
  y?: number;
  width: number;
  height: number;
} {
  const bounds = {
    width: state.width,
    height: state.height,
  };

  if (state.x === undefined || state.y === undefined) {
    return bounds;
  }

  return {
    ...bounds,
    x: state.x,
    y: state.y,
  };
}

export function normalizeWindowState(
  value: unknown,
  displays: DisplayBounds[]
): WindowState | null {
  if (!isRecord(value)) {
    return null;
  }

  const width = value.width;
  const height = value.height;
  if (
    !isValidDimension(width, MIN_WINDOW_WIDTH) ||
    !isValidDimension(height, MIN_WINDOW_HEIGHT)
  ) {
    return null;
  }

  const state: WindowState = {
    width,
    height,
    isMaximized: value.isMaximized === true,
    isFullScreen: value.isFullScreen === true,
  };

  if (
    isValidCoordinate(value.x) &&
    isValidCoordinate(value.y) &&
    isVisibleOnSomeDisplay(
      { x: value.x, y: value.y, width: state.width, height: state.height },
      displays
    )
  ) {
    state.x = value.x;
    state.y = value.y;
  }

  return state;
}

export function loadWindowState(
  stateFilePath: string,
  displays: DisplayBounds[]
): WindowState {
  if (!existsSync(stateFilePath)) {
    return getDefaultWindowState();
  }

  try {
    const parsed = JSON.parse(readFileSync(stateFilePath, 'utf8'));
    return normalizeWindowState(parsed, displays) ?? getDefaultWindowState();
  } catch (error) {
    console.warn('Error loading window state:', error);
    return getDefaultWindowState();
  }
}

export function saveWindowState(
  stateFilePath: string,
  state: WindowState
): void {
  try {
    mkdirSync(path.dirname(stateFilePath), { recursive: true });
    writeFileSync(stateFilePath, JSON.stringify(state, null, 2));
  } catch (error) {
    console.warn('Error saving window state:', error);
  }
}

export function getWindowStateFromWindow(
  window: WindowStateWindow
): WindowState {
  const bounds = window.isNormal()
    ? window.getBounds()
    : window.getNormalBounds();

  return {
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    isMaximized: window.isMaximized(),
    isFullScreen: window.isFullScreen(),
  };
}

export function restoreWindowState(
  window: WindowStateWindow,
  state: WindowState
): void {
  if (state.isMaximized) {
    window.maximize();
  }

  if (state.isFullScreen) {
    window.setFullScreen(true);
  }
}

export function manageWindowState(
  window: WindowStateWindow,
  stateFilePath: string
): void {
  let saveTimer: ReturnType<typeof setTimeout> | undefined;

  const clearSaveTimer = () => {
    if (saveTimer !== undefined) {
      clearTimeout(saveTimer);
      saveTimer = undefined;
    }
  };

  const saveNow = () => {
    clearSaveTimer();
    saveWindowState(stateFilePath, getWindowStateFromWindow(window));
  };

  const scheduleSave = () => {
    clearSaveTimer();
    saveTimer = setTimeout(saveNow, WINDOW_STATE_SAVE_DELAY_MS);
  };

  const cleanup = () => {
    clearSaveTimer();
    window.off('resize', scheduleSave);
    window.off('move', scheduleSave);
    window.off('close', saveNow);
    window.off('closed', cleanup);
  };

  window.on('resize', scheduleSave);
  window.on('move', scheduleSave);
  window.on('close', saveNow);
  window.on('closed', cleanup);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isValidDimension(value: unknown, minValue: number): value is number {
  return (
    typeof value === 'number' && Number.isInteger(value) && value >= minValue
  );
}

function isValidCoordinate(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value);
}

function isVisibleOnSomeDisplay(
  bounds: Rectangle,
  displays: DisplayBounds[]
): boolean {
  if (displays.length === 0) {
    return true;
  }

  return displays.some(display => {
    const workArea = display.workArea ?? display.bounds;
    const visibleWidth =
      Math.min(bounds.x + bounds.width, workArea.x + workArea.width) -
      Math.max(bounds.x, workArea.x);
    const visibleHeight =
      Math.min(bounds.y + bounds.height, workArea.y + workArea.height) -
      Math.max(bounds.y, workArea.y);

    return (
      visibleWidth >= MIN_VISIBLE_WIDTH && visibleHeight >= MIN_VISIBLE_HEIGHT
    );
  });
}
