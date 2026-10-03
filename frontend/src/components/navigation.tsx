'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Button } from '@heroui/react';
import { useQueryClient } from '@tanstack/react-query';
import {
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
import { GlobalSearch } from './global-search';

type NavGroup = 'Explore' | 'Analyze' | 'Model' | 'Data';
type NavItem = {
  href: string;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  group: NavGroup;
};

export const NAV_ITEMS: readonly NavItem[] = [
  { href: '/', label: 'Overview', shortLabel: 'Home', icon: LayoutDashboard, group: 'Explore' },
  { href: '/matches', label: 'Match Centre', shortLabel: 'Matches', icon: CalendarDays, group: 'Explore' },
  { href: '/tables', label: 'League Tables', shortLabel: 'Tables', icon: Table2, group: 'Explore' },
  { href: '/tournaments', label: 'Tournaments', shortLabel: 'Cups', icon: Trophy, group: 'Explore' },
  { href: '/clubs', label: 'Club Lab', shortLabel: 'Clubs', icon: Shield, group: 'Analyze' },
  { href: '/players', label: 'Players', shortLabel: 'Players', icon: UsersRound, group: 'Analyze' },
  { href: '/analysis', label: 'Analysis Lab', shortLabel: 'Analysis', icon: BarChart3, group: 'Analyze' },
  { href: '/shots', label: 'Shot Intelligence', shortLabel: 'Shots', icon: Crosshair, group: 'Analyze' },
  { href: '/predictions', label: 'Predictions', shortLabel: 'Forecasts', icon: Target, group: 'Model' },
  { href: '/models', label: 'Model Lab', shortLabel: 'Models', icon: FlaskConical, group: 'Model' },
  { href: '/quality', label: 'Data Quality', shortLabel: 'Quality', icon: Gauge, group: 'Data' },
  { href: '/settings', label: 'Settings', shortLabel: 'Settings', icon: Settings, group: 'Data' },
] as const;

const GROUPS: readonly NavGroup[] = ['Explore', 'Analyze', 'Model', 'Data'];
const MOBILE_ITEMS = NAV_ITEMS.filter((item) => ['/', '/matches', '/predictions', '/models'].includes(item.href));

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

function RefreshDataButton({ compact = false }: { compact?: boolean }) {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await queryClient.refetchQueries({ type: 'active' });
    } finally {
      setIsRefreshing(false);
    }
  };
  return (
    <Button isIconOnly={compact} size="sm" variant="ghost" onPress={handleRefresh} isDisabled={isRefreshing} aria-label="Refresh visible data">
      <RefreshCw className={`size-4 ${isRefreshing ? 'animate-spin motion-reduce:animate-none' : ''}`} aria-hidden="true" />
      {compact ? null : 'Refresh'}
    </Button>
  );
}

export function Sidebar({ isOpen = false, onClose }: { isOpen?: boolean; onClose?: () => void }) {
  const pathname = usePathname();
  const { theme, isDark, setMode } = useTheme();
  return (
    <aside
      id="primary-navigation-panel"
      className={`fixed inset-y-0 left-0 z-50 w-72 flex-col border-r border-surface1/60 bg-mantle/95 shadow-2xl shadow-crust/30 backdrop-blur-xl lg:flex ${isOpen ? 'flex' : 'hidden'}`}
      aria-label="Primary navigation"
      role={isOpen ? 'dialog' : undefined}
      aria-modal={isOpen ? true : undefined}
    >
      <div className="flex h-20 items-center justify-between border-b border-surface1/60 px-5">
        <Brand />
        {onClose ? (
          <Button isIconOnly size="sm" variant="ghost" onPress={onClose} className="lg:hidden" aria-label="Close menu">
            <X className="size-5" aria-hidden="true" />
          </Button>
        ) : null}
      </div>
      <GlobalSearch onNavigate={onClose} />

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
            Versioned API + guided refresh
          </div>
          <div className="grid grid-cols-2 gap-2">
            <RefreshDataButton />
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
    <header id="mobile-navigation-header" className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-surface1/60 bg-base/90 px-4 backdrop-blur-xl lg:hidden">
      <div className="flex min-w-0 items-center gap-3">
        <Button id="mobile-menu-trigger" isIconOnly size="sm" variant="ghost" onPress={onToggle} aria-label={isOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={isOpen} aria-controls="primary-navigation-panel">
          {isOpen ? <X className="size-5" aria-hidden="true" /> : <Menu className="size-5" aria-hidden="true" />}
        </Button>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-text">{current?.label ?? 'Football Analysis'}</p>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-sapphire">Live workspace</p>
        </div>
      </div>
      <RefreshDataButton compact />
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
    if (!mobileOpen) return;
    const panel = document.getElementById('primary-navigation-panel');
    const main = document.getElementById('main-content');
    const dock = document.querySelector<HTMLElement>('[aria-label="Quick navigation"]');
    const header = document.getElementById('mobile-navigation-header');
    const focusable = () => Array.from(panel?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])') || []);
    main?.setAttribute('inert', '');
    dock?.setAttribute('inert', '');
    header?.setAttribute('inert', '');
    focusable()[0]?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setMobileOpen(false);
      }
      if (event.key !== 'Tab') return;
      const items = focusable();
      const first = items[0];
      const last = items.at(-1);
      if (!first || !last) return;
      if (!panel?.contains(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return;
      }
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    const desktop = window.matchMedia('(min-width: 1024px)');
    const closeOnDesktop = () => {
      if (desktop.matches) setMobileOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    desktop.addEventListener('change', closeOnDesktop);
    closeOnDesktop();
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      desktop.removeEventListener('change', closeOnDesktop);
      main?.removeAttribute('inert');
      dock?.removeAttribute('inert');
      header?.removeAttribute('inert');
      if (!desktop.matches) document.getElementById('mobile-menu-trigger')?.focus();
    };
  }, [mobileOpen]);

  return (
    <>
      <MobileHeader onToggle={() => setMobileOpen((open) => !open)} isOpen={mobileOpen} />
      {mobileOpen ? <button type="button" className="fixed inset-0 z-40 bg-crust/70 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation overlay" /> : null}
      <Sidebar isOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <MobileDock onMore={() => setMobileOpen(true)} />
    </>
  );
}
