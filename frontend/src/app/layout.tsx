import type { Metadata, Viewport } from 'next';
import { Navigation } from '@/components/navigation';
import Providers from './providers';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'Football Analysis',
    template: '%s · Football Analysis',
  },
  description: 'European football performance, match, player and model intelligence from transparent public data.',
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#1e1e2e' },
    { media: '(prefers-color-scheme: light)', color: '#eff1f5' },
  ],
  colorScheme: 'dark light',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body className="bg-base text-text antialiased">
        <Providers>
          <a href="#main-content" className="skip-link">Skip to content</a>
          <Navigation />
          <main id="main-content" className="min-h-screen pb-24 lg:pl-72 lg:pb-0">
            <div className="mx-auto max-w-[1600px] px-3 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8">
              {children}
            </div>
          </main>
        </Providers>
      </body>
    </html>
  );
}
