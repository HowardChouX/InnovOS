interface TableSkeletonProps {
  rows?: number;
}

interface ListSkeletonProps {
  items?: number;
}

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-slate-800/60 ${className ?? ''}`} />;
}

export function PageSkeleton() {
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <SkeletonBlock className="h-6 w-48" />
          <SkeletonBlock className="h-4 w-72" />
        </div>
        <SkeletonBlock className="h-10 w-28 rounded-lg" />
      </div>

      {/* Content cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 space-y-3">
            <SkeletonBlock className="h-4 w-24" />
            <SkeletonBlock className="h-8 w-16" />
            <SkeletonBlock className="h-3 w-full" />
            <SkeletonBlock className="h-3 w-3/4" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-3">
        <SkeletonBlock className="h-10 w-10 rounded-lg" />
        <div className="space-y-2 flex-1">
          <SkeletonBlock className="h-4 w-32" />
          <SkeletonBlock className="h-3 w-20" />
        </div>
      </div>
      <SkeletonBlock className="h-3 w-full" />
      <SkeletonBlock className="h-3 w-5/6" />
      <div className="flex items-center gap-2 pt-2">
        <SkeletonBlock className="h-8 w-20 rounded-md" />
        <SkeletonBlock className="h-8 w-20 rounded-md" />
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: TableSkeletonProps) {
  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center gap-4 px-4 py-3 bg-slate-900/30 rounded-lg">
        <SkeletonBlock className="h-4 w-1/4" />
        <SkeletonBlock className="h-4 w-1/4" />
        <SkeletonBlock className="h-4 w-1/6" />
        <SkeletonBlock className="h-4 w-1/6" />
        <SkeletonBlock className="h-4 w-16" />
      </div>

      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 px-4 py-4 bg-slate-900/20 border border-slate-800/50 rounded-lg"
        >
          <SkeletonBlock className="h-4 w-1/4" />
          <SkeletonBlock className="h-4 w-1/4" />
          <SkeletonBlock className="h-4 w-1/6" />
          <SkeletonBlock className="h-4 w-1/6" />
          <SkeletonBlock className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

export function ListSkeleton({ items = 4 }: ListSkeletonProps) {
  return (
    <div className="space-y-3">
      {Array.from({ length: items }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 p-4 bg-slate-900/20 border border-slate-800/50 rounded-lg"
        >
          <SkeletonBlock className="h-8 w-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <SkeletonBlock className="h-4 w-3/5" />
            <SkeletonBlock className="h-3 w-2/5" />
          </div>
          <SkeletonBlock className="h-6 w-16 rounded-md" />
        </div>
      ))}
    </div>
  );
}
