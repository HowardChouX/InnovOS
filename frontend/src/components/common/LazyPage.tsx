import React, { Suspense } from 'react';
import { PageSkeleton } from './LoadingSkeleton';

/**
 * Creates a lazy-loaded page component that works with both default
 * and named exports from page modules.
 *
 * Usage:
 *   const DashboardPage = lazyPage(() => import('./DashboardPage'));
 *
 * The import function returns the module; lazyPage extracts the first
 * React component export (either default or named) and wraps it with
 * Suspense and a loading skeleton.
 */
export function lazyPage(
  importFn: () => Promise<Record<string, unknown>>,
  fallback?: React.ReactNode,
): React.ComponentType<Record<string, unknown>> {
  const LazyComponent = React.lazy(() =>
    importFn().then((mod) => {
      // Prefer default export
      if (mod.default && typeof mod.default === 'function') {
        return { default: mod.default as React.ComponentType<unknown> };
      }
      // Fallback: find the first function export (the component itself)
      for (const value of Object.values(mod)) {
        if (typeof value === 'function') {
          return { default: value as React.ComponentType<unknown> };
        }
      }
      throw new Error(
        `lazyPage: No component found. Available exports: ${Object.keys(mod).join(', ')}`,
      );
    }),
  );

  const LazyPageWrapper = (props: Record<string, unknown>) => (
    <Suspense fallback={fallback ?? <PageSkeleton />}>
      <LazyComponent {...props} />
    </Suspense>
  );

  LazyPageWrapper.displayName = 'LazyPage';

  return LazyPageWrapper;
}
