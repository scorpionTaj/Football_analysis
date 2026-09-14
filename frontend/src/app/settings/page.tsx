'use client';

import React, { useState } from 'react';
import { useTheme, AVAILABLE_THEMES, type ThemeId, type ThemeMode } from '@/components/theme-provider';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import {
  Palette,
  Sun,
  Moon,
  Laptop,
  Check,
  Server,
  Activity,
  Database,
  Sliders,
  RefreshCw,
} from 'lucide-react';

export default function SettingsPage() {
  const { theme, mode, setTheme, setMode } = useTheme();
  const [pingLatency, setPingLatency] = useState<number | null>(null);
  const [isPinging, setIsPinging] = useState(false);

  const { data: health, isLoading: isHealthLoading, refetch: refetchHealth } = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.health(),
  });

  const testPing = async () => {
    setIsPinging(true);
    const start = performance.now();
    try {
      await api.health();
      const end = performance.now();
      setPingLatency(Math.round(end - start));
    } catch {
      setPingLatency(-1);
    } finally {
      setIsPinging(false);
    }
  };

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-text tracking-tight">Application Settings</h1>
        <p className="text-sm text-subtext0 mt-1">
          Customize themes, color palettes, appearance mode, and inspect backend API diagnostics.
        </p>
      </div>

      {/* Section 1: Appearance Mode */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-4">
        <div className="flex items-center gap-2.5 pb-2 border-b border-surface1">
          <Palette className="h-5 w-5 text-blue" />
          <h2 className="text-base font-semibold text-text">Theme Mode & Auto-Detection</h2>
        </div>

        <p className="text-xs text-subtext0">
          Select whether the theme automatically adapts to your operating system or stays permanently dark or light.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
          {/* Auto */}
          <button
            onClick={() => setMode('auto')}
            className={`flex items-center gap-3 p-4 rounded-xl border text-left transition-all cursor-pointer ${
              mode === 'auto'
                ? 'bg-blue/15 border-blue text-text shadow-sm'
                : 'bg-mantle border-surface1 text-subtext1 hover:bg-surface1'
            }`}
          >
            <Laptop className={`h-5 w-5 ${mode === 'auto' ? 'text-blue' : 'text-subtext0'}`} />
            <div>
              <p className="text-sm font-semibold">Automatic</p>
              <p className="text-xs text-subtext0 mt-0.5">Sync with system</p>
            </div>
          </button>

          {/* Dark */}
          <button
            onClick={() => setMode('dark')}
            className={`flex items-center gap-3 p-4 rounded-xl border text-left transition-all cursor-pointer ${
              mode === 'dark'
                ? 'bg-blue/15 border-blue text-text shadow-sm'
                : 'bg-mantle border-surface1 text-subtext1 hover:bg-surface1'
            }`}
          >
            <Moon className={`h-5 w-5 ${mode === 'dark' ? 'text-blue' : 'text-subtext0'}`} />
            <div>
              <p className="text-sm font-semibold">Force Dark</p>
              <p className="text-xs text-subtext0 mt-0.5">Dark background</p>
            </div>
          </button>

          {/* Light */}
          <button
            onClick={() => setMode('light')}
            className={`flex items-center gap-3 p-4 rounded-xl border text-left transition-all cursor-pointer ${
              mode === 'light'
                ? 'bg-blue/15 border-blue text-text shadow-sm'
                : 'bg-mantle border-surface1 text-subtext1 hover:bg-surface1'
            }`}
          >
            <Sun className={`h-5 w-5 ${mode === 'light' ? 'text-blue' : 'text-subtext0'}`} />
            <div>
              <p className="text-sm font-semibold">Force Light</p>
              <p className="text-xs text-subtext0 mt-0.5">Light background</p>
            </div>
          </button>
        </div>
      </div>

      {/* Section 2: 6 Theme Palettes */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-surface1">
          <div className="flex items-center gap-2.5">
            <Sliders className="h-5 w-5 text-teal" />
            <h2 className="text-base font-semibold text-text">Color Palettes ({AVAILABLE_THEMES.length} Available)</h2>
          </div>
          <span className="text-xs text-subtext0">
            Active: <strong className="text-text capitalize">{theme.replace('-', ' ')}</strong>
          </span>
        </div>

        <p className="text-xs text-subtext0">
          Choose from custom tailored designer palettes with carefully balanced contrast and accent colors.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3.5 pt-2">
          {AVAILABLE_THEMES.map((opt) => {
            const isSelected = theme === opt.id;
            return (
              <button
                key={opt.id}
                onClick={() => setTheme(opt.id)}
                className={`flex flex-col justify-between p-4 rounded-xl border transition-all text-left cursor-pointer ${
                  isSelected
                    ? 'border-blue ring-2 ring-blue/30 shadow-md'
                    : 'border-surface1 hover:border-surface2'
                }`}
                style={{ backgroundColor: opt.previewBg }}
              >
                <div className="flex items-center justify-between w-full mb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{ backgroundColor: opt.accent }}
                    />
                    <span
                      className="text-xs font-bold"
                      style={{ color: opt.previewText }}
                    >
                      {opt.name}
                    </span>
                  </div>
                  {isSelected && (
                    <span className="p-0.5 rounded-full bg-blue text-crust">
                      <Check className="h-3 w-3" />
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between text-[11px] opacity-75">
                  <span style={{ color: opt.previewText }} className="capitalize font-mono">
                    {opt.type}
                  </span>
                  <div className="flex gap-1">
                    <span className="h-2 w-4 rounded-xs" style={{ backgroundColor: opt.accent }} />
                    <span className="h-2 w-2 rounded-xs" style={{ backgroundColor: opt.previewText }} />
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Section 3: Pagination & Display Settings */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-4">
        <h2 className="text-base font-semibold text-text pb-2 border-b border-surface1">
          Display & Pagination Standards
        </h2>
        <div className="space-y-3 text-xs text-subtext1">
          <div className="flex items-center justify-between py-2 border-b border-surface1/50">
            <div>
              <p className="font-semibold text-text">Standard Page Size</p>
              <p className="text-subtext0 text-[11px]">Enforced across all data views exceeding 10 entries</p>
            </div>
            <span className="font-mono font-bold text-blue px-2.5 py-1 rounded bg-mantle border border-surface1">
              10 entries / page
            </span>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-surface1/50">
            <div>
              <p className="font-semibold text-text">URL Filter Persistence</p>
              <p className="text-subtext0 text-[11px]">Retain competition, season, club and stage in query params</p>
            </div>
            <span className="font-semibold text-green">Enabled</span>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-semibold text-text">Color Token Architecture</p>
              <p className="text-subtext0 text-[11px]">CSS custom properties with Tailwind v4 runtime switching</p>
            </div>
            <span className="font-semibold text-teal">Active</span>
          </div>
        </div>
      </div>

      {/* Section 4: Backend API Diagnostics */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-surface1">
          <div className="flex items-center gap-2.5">
            <Server className="h-5 w-5 text-peach" />
            <h2 className="text-base font-semibold text-text">Backend API Diagnostics</h2>
          </div>
          <button
            onClick={() => {
              refetchHealth();
              testPing();
            }}
            disabled={isPinging}
            className="flex items-center gap-1.5 px-3 py-1 text-xs rounded bg-mantle border border-surface1 hover:border-surface2 text-text transition-colors cursor-pointer"
          >
            <RefreshCw className={`h-3 w-3 text-blue ${isPinging ? 'animate-spin' : ''}`} />
            <span>Test Connection</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-lg bg-mantle p-3.5 border border-surface1">
            <div className="flex items-center justify-between text-subtext0 text-xs">
              <span>Service Status</span>
              <span className={`h-2.5 w-2.5 rounded-full ${health?.status === 'ok' ? 'bg-green' : 'bg-red'}`} />
            </div>
            <p className="text-lg font-bold text-text mt-1 capitalize">{health?.status || 'Connecting…'}</p>
          </div>

          <div className="rounded-lg bg-mantle p-3.5 border border-surface1">
            <div className="flex items-center justify-between text-subtext0 text-xs">
              <span>Ping Latency</span>
              <Activity className="h-3.5 w-3.5 text-blue" />
            </div>
            <p className="text-lg font-bold text-text mt-1">
              {pingLatency !== null ? (pingLatency >= 0 ? `${pingLatency} ms` : 'Failed') : 'Untested'}
            </p>
          </div>

          <div className="rounded-lg bg-mantle p-3.5 border border-surface1">
            <div className="flex items-center justify-between text-subtext0 text-xs">
              <span>Database Access</span>
              <Database className="h-3.5 w-3.5 text-teal" />
            </div>
            <p className="text-sm font-semibold text-text mt-1 truncate" title={health?.database}>
              {health?.read_only ? 'DuckDB (Read-Only)' : 'DuckDB'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
