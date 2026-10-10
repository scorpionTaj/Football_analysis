import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import { Navigation } from '@/components/navigation';
import Providers from './providers';
import './globals.css';

const inter = Inter({ subsets: ['latin', 'latin-ext'], variable: '--font-inter', display: 'swap' });

export const metadata: Metadata = {
  title: {
    default: 'Football Analysis',
    template: '%s · Football Analysis',
  },
  description: 'European football performance, match, player and model intelligence from transparent public data.',
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#0b0d12' },
    { media: '(prefers-color-scheme: light)', color: '#f7f8fa' },
  ],
  colorScheme: 'dark light',
};

// Applies the saved/system mode before first paint (same rule as ThemeProvider), so light-mode
// users never see the dark default flash.
const themeScript = `(function(){try{var m=localStorage.getItem('fa_theme_mode')||'auto',d=m==='dark'||(m!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches),r=document.documentElement;r.classList.toggle('dark',d);r.classList.toggle('light',!d)}catch(e){}})()`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${inter.variable}`} data-scroll-behavior="smooth" suppressHydrationWarning>
      <head>
        {/* The app ships its own light/dark themes; stop Dark Reader re-colouring it (its injected
            attributes also break React hydration). */}
        <meta name="darkreader-lock" />
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="bg-base text-text antialiased">
        <Providers>
          <a href="#main-content" className="skip-link">Skip to content</a>
          <Navigation />
          <main id="main-content" className="min-h-screen pb-20 lg:pl-60 lg:pb-0">
            <div className="mx-auto max-w-[1440px] px-3 py-4 sm:px-6 sm:py-6 lg:px-8">
              {children}
            </div>
          </main>
        </Providers>
      </body>
    </html>
  );
}
