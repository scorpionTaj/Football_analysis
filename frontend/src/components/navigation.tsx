'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Button } from '@heroui/react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  BarChart3,
  CalendarDays,
  Crosshair,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Menu,
  Moon,
  RefreshCw,
  Settings,
  Shield,
  Sun,
  Table2,
  Target,
  Trophy,
  UsersRound,
  X,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { useTheme } from './theme-provider';

type NavItem = {
  href: string;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  group: 'Explore' | 'Intelligence' | 'System';
};

export const NAV_ITEMS: readonly NavItem[] = [
  { href: '/', label: 'Overview', shortLabel: 'Home', icon: LayoutDashboard, group: 'Explore' },
  { href: '/matches', label: 'Match Centre', shortLabel: 'Matches', icon: CalendarDays, group: 'Explore' },
  { href: '/tables', label: 'League Tables', shortLabel: 'Tables', icon: Table2, group: 'Explore' },
  { href: '/clubs', label: 'Club Lab', shortLabel: 'Clubs', icon: Shield, group: 'Explore' },
  { href: '/players', label: 'Players', shortLabel: 'Players', icon: UsersRound, group: 'Explore' },
  { href: '/tournaments', label: 'Tournaments', shortLabel: 'Cups', icon: Trophy, group: 'Intelligence' },
  { href: '/analysis', label: 'Analysis Lab', shortLabel: 'Analysis', icon: FlaskConical, group: 'Intelligence' },
  { href: '/shots', label: 'Shot Intelligence', shortLabel: 'Shots', icon: Crosshair, group: 'Intelligence' },
  { href: '/predictions', label: 'Predictions', shortLabel: 'Forecasts', icon: Target, group: 'Intelligence' },
  { href: '/quality', label: 'Data Quality', shortLabel: 'Quality', icon: Gauge, group: 'System' },
  { href: '/settings', label: 'Settings', shortLabel: 'Settings', icon: Settings, group: 'System' },
] as const;

const GROUPS = ['Explore', 'Intelligence', 'System'] as const;
const MOBILE_ITEMS = NAV_ITEMS.filter((item) => ['/', '/matches', '/analysis', '/players'].includes(item.href));

function isActive(pathname: string, href: string) {
  return href === '/' ? pathname === '/' : pathname.startsWith(href);
}

function Brand() {
  return (
    <Link href="/" className="group flex min-w-0 items-center gap-3" aria-label="Football Analysis home">
      <span className="relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-2xl bg-gradient-to-br from-blue via-sapphire to-teal text-crust shadow-lg shadow-blue/20">
        <Zap className="size-5 fill-current" aria-hidden="true" />
        <span className="absolute inset-x-2 bottom-1 h-px bg-crust/30" />
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block truncate text-[15px] font-black tracking-[-0.03em] text-text">Football Analysis</span>
        <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] text-sapphire">Match intelligence</span>
      </span>
    </Link>
  );
}

export function Sidebar({ isOpen = false, onClose }: { isOpen?: boolean; onClose?: () => void }) {
  const pathname = usePathname();
  const { theme, isDark, setMode } = useTheme();
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries();
    window.setTimeout(() => setIsRefreshing(false), 700);
  };

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-surface1/60 bg-mantle/95 shadow-2xl shadow-crust/30 backdrop-blur-xl transition-transform duration-300 lg:translate-x-0 ${
        isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      }`}
      aria-label="Primary navigation"
    >
      <div className="flex h-20 items-center justify-between border-b border-surface1/60 px-5">
        <Brand />
        {onClose ? (
          <Button isIconOnly size="sm" variant="ghost" onPress={onClose} className="lg:hidden" aria-label="Close menu">
            <X className="size-5" aria-hidden="true" />
          </Button>
        ) : null}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Dashboard sections">
        {GROUPS.map((group) => (
          <div key={group} className="mb-5 last:mb-0">
            <p className="mb-2 px-3 text-[11px] font-bold uppercase tracking-[0.16em] text-overlay0">{group}</p>
            <ul className="space-y-1">
              {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => onClose?.()}
                      className={`group relative flex min-h-11 items-center gap-3 overflow-hidden rounded-xl px-3 text-sm font-semibold transition-all duration-200 ${
                        active
                          ? 'bg-blue/15 text-blue ring-1 ring-inset ring-blue/20'
                          : 'text-subtext1 hover:bg-surface0 hover:text-text'
                      }`}
                      aria-current={active ? 'page' : undefined}
                    >
                      {active ? <span className="absolute inset-y-2 left-0 w-0.5 rounded-r-full bg-blue" /> : null}
                      <span className={`grid size-8 shrink-0 place-items-center rounded-lg ${active ? 'bg-blue/15' : 'bg-surface0/70 group-hover:bg-surface1/70'}`}>
                        <Icon className="size-[17px]" aria-hidden="true" />
                      </span>
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-surface1/60 p-3">
        <div className="rounded-2xl border border-surface1/70 bg-base/60 p-2 shadow-inner">
          <div className="mb-2 flex items-center gap-2 px-2 py-1 text-[11px] font-semibold text-subtext0">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-green opacity-50 motion-reduce:animate-none" />
              <span className="relative inline-flex size-2 rounded-full bg-green" />
            </span>
            Read-only API workspace
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button size="sm" variant="ghost" onPress={handleRefresh} isDisabled={isRefreshing} aria-label="Refresh dashboard data">
              <RefreshCw className={`size-4 ${isRefreshing ? 'animate-spin' : ''}`} aria-hidden="true" />
              Refresh
            </Button>
            <Button size="sm" variant="ghost" onPress={() => setMode(isDark ? 'light' : 'dark')} aria-label="Toggle color mode">
              {isDark ? <Moon className="size-4" aria-hidden="true" /> : <Sun className="size-4" aria-hidden="true" />}
              <span className="truncate capitalize">{theme.replace('-', ' ')}</span>
            </Button>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function MobileHeader({ onToggle, isOpen = false }: { onToggle: () => void; isOpen?: boolean }) {
  const pathname = usePathname();
  const current = NAV_ITEMS.find((item) => isActive(pathname, item.href));

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-surface1/60 bg-base/90 px-4 backdrop-blur-xl lg:hidden">
      <div className="flex min-w-0 items-center gap-3">
        <Button isIconOnly size="sm" variant="ghost" onPress={onToggle} aria-label={isOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={isOpen}>
          {isOpen ? <X className="size-5" aria-hidden="true" /> : <Menu className="size-5" aria-hidden="true" />}
        </Button>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-text">{current?.label ?? 'Football Analysis'}</p>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-sapphire">Live workspace</p>
        </div>
      </div>
      <span className="grid size-9 place-items-center rounded-xl bg-blue/15 text-blue">
        <Activity className="size-[18px]" aria-hidden="true" />
      </span>
    </header>
  );
}

function MobileDock({ onMore }: { onMore: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="fixed inset-x-3 bottom-3 z-30 grid grid-cols-5 rounded-2xl border border-surface1/80 bg-mantle/95 p-1.5 shadow-2xl shadow-crust/40 backdrop-blur-xl lg:hidden" aria-label="Quick navigation">
      {MOBILE_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        const Icon = item.icon;
        return (
          <Link key={item.href} href={item.href} className={`flex min-h-12 flex-col items-center justify-center gap-0.5 rounded-xl text-[10px] font-semibold transition-colors ${active ? 'bg-blue/15 text-blue' : 'text-subtext0 hover:bg-surface0 hover:text-text'}`} aria-current={active ? 'page' : undefined}>
            <Icon className="size-[17px]" aria-hidden="true" />
            <span>{item.shortLabel}</span>
          </Link>
        );
      })}
      <button type="button" onClick={onMore} className="flex min-h-12 flex-col items-center justify-center gap-0.5 rounded-xl text-[10px] font-semibold text-subtext0 hover:bg-surface0 hover:text-text" aria-label="Open all navigation">
        <BarChart3 className="size-[17px]" aria-hidden="true" />
        <span>More</span>
      </button>
    </nav>
  );
}

export function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <>
      <MobileHeader onToggle={() => setMobileOpen((open) => !open)} isOpen={mobileOpen} />
      {mobileOpen ? <button type="button" className="fixed inset-0 z-40 bg-crust/70 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation overlay" /> : null}
      <Sidebar isOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <MobileDock onMore={() => setMobileOpen(true)} />
    </>
  );
}
