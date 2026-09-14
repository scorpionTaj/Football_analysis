import type { Metadata } from 'next';
import { Navigation } from '@/components/navigation';
import Providers from './providers';
import './globals.css';

export const metadata: Metadata = {
  title: 'Football Analysis',
  description: 'Free-source European football analytics',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-base text-text antialiased">
        <Providers>
          <Navigation />
          <main className="min-h-screen lg:pl-60">
            <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
              {children}
            </div>
          </main>
        </Providers>
      </body>
    </html>
  );
}
