'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

export const NAV_ITEMS = [
  { href: '/', label: 'Overview', icon: '📊' },
  { href: '/tournaments', label: 'Tournaments', icon: '🏆' },
  { href: '/analysis', label: 'Analysis Lab', icon: '🔬' },
  { href: '/tables', label: 'League Tables', icon: '📋' },
  { href: '/clubs', label: 'Club Lab', icon: '⚽' },
  { href: '/matches', label: 'Match Explorer', icon: '📅' },
  { href: '/players', label: 'Players', icon: '👤' },
  { href: '/predictions', label: 'Predictions', icon: '🎯' },
  { href: '/quality', label: 'Data Quality', icon: '✅' },
] as const;

export function Sidebar({
  isOpen = false,
  onClose,
}: {
  isOpen?: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex w-60 flex-col bg-mantle border-r border-surface0 transition-transform duration-200 lg:translate-x-0 ${
        isOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'
      }`}
      aria-label="Sidebar navigation"
    >
      {/* Logo and close button on mobile */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-surface0">
        <div className="flex items-center gap-2">
          <span className="text-2xl" role="img" aria-hidden="true">⚽</span>
          <h1 className="text-lg font-bold text-text tracking-tight">
            Football<span className="text-blue">Analysis</span>
          </h1>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="rounded p-1 text-subtext0 hover:text-text lg:hidden cursor-pointer"
            aria-label="Close menu"
          >
            ✕
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2" aria-label="Main navigation">
        <ul className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === '/'
                ? pathname === '/'
                : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={() => onClose?.()}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                    active
                      ? 'bg-blue/15 text-blue'
                      : 'text-subtext1 hover:bg-surface0 hover:text-text'
                  }`}
                  aria-current={active ? 'page' : undefined}
                >
                  <span className="text-base" aria-hidden="true">
                    {item.icon}
                  </span>
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="border-t border-surface0 px-4 py-3">
        <p className="text-xs text-overlay0">
          v1.0 · FastAPI + DuckDB
        </p>
      </div>
    </aside>
  );
}

/** Mobile header with hamburger menu */
export function MobileHeader({
  onToggle,
  isOpen = false,
}: {
  onToggle?: () => void;
  isOpen?: boolean;
}) {
  const pathname = usePathname();
  const current = NAV_ITEMS.find(
    (item) =>
      item.href === '/' ? pathname === '/' : pathname.startsWith(item.href),
  );

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-surface0 bg-mantle/80 backdrop-blur px-4 lg:hidden">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggle}
          className="rounded-lg p-1.5 text-subtext1 hover:bg-surface0 hover:text-text focus:outline-none focus:ring-2 focus:ring-blue cursor-pointer"
          aria-label={isOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={isOpen}
        >
          <svg
            className="h-6 w-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            {isOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
        <span className="text-xl" role="img" aria-hidden="true">⚽</span>
        <span className="text-sm font-semibold text-text">
          {current?.label ?? 'Football Analysis'}
        </span>
      </div>
    </header>
  );
}

export function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <>
      <MobileHeader onToggle={() => setMobileOpen((prev) => !prev)} isOpen={mobileOpen} />
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-crust/60 backdrop-blur-xs lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}
      <Sidebar isOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
    </>
  );
}
