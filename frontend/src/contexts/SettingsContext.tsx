import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { HighlightColor } from '../types/highlights';

export interface AppSettings {
  // PDF Viewer Settings
  defaultZoom: number;
  defaultViewMode: 'single' | 'double';

  // Panel Layout Settings
  defaultLeftPanelWidth: number;
  defaultRightTopPanelHeight: number;

  // Highlight Settings
  defaultHighlightColor: HighlightColor;
  highlightOpacity: number;

  // UI Preferences
  theme: 'dark' | 'light';
  autoSaveProgress: boolean;
  showPageNumbers: boolean;

  // Reading Settings
  autoMarkFinished: boolean;
  readingGoal: number; // pages per day

  // AI Settings
  enableAI: boolean;
  aiModel: string;
}

export const defaultSettings: AppSettings = {
  defaultZoom: 1.0,
  defaultViewMode: 'single',
  defaultLeftPanelWidth: 60,
  defaultRightTopPanelHeight: 60,
  defaultHighlightColor: HighlightColor.YELLOW,
  highlightOpacity: 0.4,
  theme: 'dark',
  autoSaveProgress: true,
  showPageNumbers: true,
  autoMarkFinished: false,
  readingGoal: 10,
  enableAI: true,
  aiModel: 'qwen2.5:3b',
};

interface SettingsContextValue {
  settings: AppSettings;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
  resetToDefaults: () => void;
}

const SettingsContext = createContext<SettingsContextValue | undefined>(
  undefined
);

const SETTINGS_KEY = 'scholarmate-settings';

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);

  // Load settings from localStorage on mount
  useEffect(() => {
    const savedSettings = localStorage.getItem(SETTINGS_KEY);
    if (savedSettings) {
      try {
        const parsed = JSON.parse(savedSettings);
        setSettings({ ...defaultSettings, ...parsed });
      } catch (error) {
        console.warn('Error loading settings:', error);
      }
    }
  }, []);

  // Save settings to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }, [settings]);

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings(prev => ({ ...prev, ...newSettings }));
  };

  const resetToDefaults = () => {
    setSettings(defaultSettings);
    // Also clear individual localStorage keys
    localStorage.removeItem('pdf-viewer-zoom');
    localStorage.removeItem('pdf-viewer-view-mode');
    localStorage.removeItem('pdf-reader-left-width');
    localStorage.removeItem('pdf-reader-right-top-height');
    localStorage.removeItem('pdf-reader-simple-left-width');
  };

  return (
    <SettingsContext.Provider
      value={{ settings, updateSettings, resetToDefaults }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (context === undefined) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
}
