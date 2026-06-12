import { describe, it, expect, beforeEach } from 'vitest';
import { StrictMode } from 'react';
import { render, screen, act } from '@testing-library/react';
import {
  SettingsProvider,
  useSettings,
  defaultSettings,
} from '../../src/contexts/SettingsContext';

const SETTINGS_KEY = 'scholarmate-settings';

function ShowSettings() {
  const { settings, updateSettings } = useSettings();
  return (
    <div>
      <span data-testid="reading-goal">{settings.readingGoal}</span>
      <span data-testid="theme">{settings.theme}</span>
      <span data-testid="highlight-color">
        {settings.defaultHighlightColor}
      </span>
      <button onClick={() => updateSettings({ readingGoal: 42 })}>
        update
      </button>
    </div>
  );
}

function renderProvider() {
  return render(
    <StrictMode>
      <SettingsProvider>
        <ShowSettings />
      </SettingsProvider>
    </StrictMode>
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe('SettingsProvider hydration (C-6 regression)', () => {
  it('hydrates saved settings on first render, even under StrictMode', () => {
    localStorage.setItem(
      SETTINGS_KEY,
      JSON.stringify({ readingGoal: 25, theme: 'light' })
    );

    renderProvider();

    expect(screen.getByTestId('reading-goal').textContent).toBe('25');
    expect(screen.getByTestId('theme').textContent).toBe('light');
  });

  it('does not overwrite saved settings with defaults on mount', () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({ readingGoal: 25 }));

    renderProvider();

    const persisted = JSON.parse(localStorage.getItem(SETTINGS_KEY)!);
    expect(persisted.readingGoal).toBe(25);
  });

  it('falls back to defaults when nothing is saved', () => {
    renderProvider();

    expect(screen.getByTestId('reading-goal').textContent).toBe(
      String(defaultSettings.readingGoal)
    );
  });

  it('falls back to defaults on corrupt saved settings', () => {
    localStorage.setItem(SETTINGS_KEY, '{not json');

    renderProvider();

    expect(screen.getByTestId('reading-goal').textContent).toBe(
      String(defaultSettings.readingGoal)
    );
  });

  it('normalizes a legacy hex defaultHighlightColor to a canonical name', () => {
    localStorage.setItem(
      SETTINGS_KEY,
      JSON.stringify({ defaultHighlightColor: '#00ff00' })
    );

    renderProvider();

    expect(screen.getByTestId('highlight-color').textContent).toBe('green');
  });

  it('persists updates to localStorage', () => {
    renderProvider();

    act(() => {
      screen.getByText('update').click();
    });

    const persisted = JSON.parse(localStorage.getItem(SETTINGS_KEY)!);
    expect(persisted.readingGoal).toBe(42);
    expect(screen.getByTestId('reading-goal').textContent).toBe('42');
  });
});
