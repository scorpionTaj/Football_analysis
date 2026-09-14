'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

export type ThemeId = 'mocha' | 'latte' | 'tokyo-night' | 'nord' | 'dracula' | 'github-light';
export type ThemeMode = 'auto' | 'dark' | 'light';

export interface ThemeOption {
  id: ThemeId;
  name: string;
  type: 'dark' | 'light';
  accent: string;
  previewBg: string;
  previewText: string;
}

export const AVAILABLE_THEMES: ThemeOption[] = [
  {
    id: 'mocha',
    name: 'Catppuccin Mocha',
    type: 'dark',
    accent: '#89b4fa',
    previewBg: '#1e1e2e',
    previewText: '#cdd6f4',
  },
  {
    id: 'latte',
    name: 'Catppuccin Latte',
    type: 'light',
    accent: '#1e66f5',
    previewBg: '#eff1f5',
    previewText: '#4c4f69',
  },
  {
    id: 'tokyo-night',
    name: 'Tokyo Night',
    type: 'dark',
    accent: '#7aa2f7',
    previewBg: '#1a1b26',
    previewText: '#c0caf5',
  },
  {
    id: 'nord',
    name: 'Nord Frost',
    type: 'dark',
    accent: '#88c0d0',
    previewBg: '#2e3440',
    previewText: '#eceff4',
  },
  {
    id: 'dracula',
    name: 'Dracula',
    type: 'dark',
    accent: '#bd93f9',
    previewBg: '#282a36',
    previewText: '#f8f8f2',
  },
  {
    id: 'github-light',
    name: 'GitHub Clean',
    type: 'light',
    accent: '#0366d6',
    previewBg: '#ffffff',
    previewText: '#24292e',
  },
];

interface ThemeContextType {
  theme: ThemeId;
  mode: ThemeMode;
  setTheme: (theme: ThemeId) => void;
  setMode: (mode: ThemeMode) => void;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>('mocha');
  const [mode, setModeState] = useState<ThemeMode>('auto');
  const [systemDark, setSystemDark] = useState<boolean>(true);

  // Initialize from localStorage and system preference
  useEffect(() => {
    try {
      const savedMode = localStorage.getItem('fa_theme_mode') as ThemeMode | null;
      const savedTheme = localStorage.getItem('fa_theme_id') as ThemeId | null;

      // Check system preference
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      queueMicrotask(() => {
        if (savedMode && ['auto', 'dark', 'light'].includes(savedMode)) {
          setModeState(savedMode);
        }
        if (savedTheme && AVAILABLE_THEMES.some((t) => t.id === savedTheme)) {
          setThemeState(savedTheme);
        }
        setSystemDark(mediaQuery.matches);
      });

      const handleSystemChange = (e: MediaQueryListEvent) => {
        setSystemDark(e.matches);
      };
      mediaQuery.addEventListener('change', handleSystemChange);
      return () => mediaQuery.removeEventListener('change', handleSystemChange);
    } catch {
      // Fallback in case localStorage is restricted
    }
  }, []);

  // Compute active theme based on mode
  const activeTheme: ThemeId = React.useMemo(() => {
    if (mode === 'auto') {
      return systemDark ? (theme === 'latte' || theme === 'github-light' ? 'mocha' : theme) : 'latte';
    }
    if (mode === 'dark') {
      return theme === 'latte' || theme === 'github-light' ? 'mocha' : theme;
    }
    // mode === 'light'
    return theme === 'latte' || theme === 'github-light' ? theme : 'latte';
  }, [mode, theme, systemDark]);

  const isDark = React.useMemo(() => {
    const opt = AVAILABLE_THEMES.find((t) => t.id === activeTheme);
    return opt ? opt.type === 'dark' : true;
  }, [activeTheme]);

  // Apply data-theme to HTML root
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', activeTheme);
    if (isDark) {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
  }, [activeTheme, isDark]);

  const setTheme = (newTheme: ThemeId) => {
    setThemeState(newTheme);
    try {
      localStorage.setItem('fa_theme_id', newTheme);
      const opt = AVAILABLE_THEMES.find((t) => t.id === newTheme);
      if (opt) {
        setModeState(opt.type);
        localStorage.setItem('fa_theme_mode', opt.type);
      }
    } catch {}
  };

  const setMode = (newMode: ThemeMode) => {
    setModeState(newMode);
    try {
      localStorage.setItem('fa_theme_mode', newMode);
    } catch {}
  };

  return (
    <ThemeContext.Provider value={{ theme: activeTheme, mode, setTheme, setMode, isDark }}>
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
