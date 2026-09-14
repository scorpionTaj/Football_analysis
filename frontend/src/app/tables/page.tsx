import { FilterBar } from '@/components/filters';
import { Suspense } from 'react';

export default function TablesPage() {
  return (
    <>
      <h1 className="text-2xl font-bold text-text mb-4">League Tables</h1>
      <Suspense><FilterBar /></Suspense>
      <div className="mt-6 rounded-xl bg-surface0 border border-surface1 p-8 text-center">
        <p className="text-subtext0">League standings will be migrated here.</p>
      </div>
    </>
  );
}
