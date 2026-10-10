'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

export type ThemeMode = 'auto' | 'dark' | 'light';

interface ThemeContextType {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
const MODES: ThemeMode[] = ['auto', 'dark', 'light'];

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>('auto');
  const [systemDark, setSystemDark] = useState<boolean>(true);
  // Until saved preferences load, keep what the layout's inline script applied before paint.
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem('fa_theme_mode') as ThemeMode | null;
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      queueMicrotask(() => {
        if (saved && MODES.includes(saved)) setModeState(saved);
        setSystemDark(mediaQuery.matches);
        setLoaded(true);
      });
      const handleSystemChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
      mediaQuery.addEventListener('change', handleSystemChange);
      return () => mediaQuery.removeEventListener('change', handleSystemChange);
    } catch {
      // localStorage can be unavailable (private windows); the system preference still applies.
    }
  }, []);

  const isDark = mode === 'auto' ? systemDark : mode === 'dark';

  useEffect(() => {
    if (!loaded) return;
    const root = document.documentElement;
    root.classList.toggle('dark', isDark);
    root.classList.toggle('light', !isDark);
  }, [isDark, loaded]);

  const setMode = (newMode: ThemeMode) => {
    setModeState(newMode);
    try {
      localStorage.setItem('fa_theme_mode', newMode);
    } catch {}
  };

  return (
    <ThemeContext.Provider value={{ mode, setMode, isDark }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
