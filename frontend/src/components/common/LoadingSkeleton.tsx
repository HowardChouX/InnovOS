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
    <div className="flex items-center justify-center h-full min-h-[60vh]">
      <div className="flex flex-col items-center gap-8">
        {/* Hexagonal loading animation */}
        <HexLoader size={180} />
        <span className="text-xs text-[var(--text-tertiary)] animate-pulse font-medium tracking-wider">
          加载中
        </span>
      </div>
    </div>
  );
}

function HexLoader({ size = 180 }: { size?: number }) {
  const r = size * 0.32;
  const cx = size / 2;
  const cy = size / 2;
  const n = 6;
  const nodes = Array.from({ length: n }, (_, i) => {
    const a = (Math.PI * 2 / n) * i - Math.PI / 2;
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r };
  });

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-28 h-28">
      {/* Connecting lines */}
      {Array.from({ length: n }, (_, i) => {
        const j = (i + 1) % n;
        return (
          <line
            key={`ln-${i}`}
            x1={nodes[i].x}
            y1={nodes[i].y}
            x2={nodes[j].x}
            y2={nodes[j].y}
            stroke="var(--border)"
            strokeWidth="1"
            opacity="0.4"
          />
        );
      })}
      {/* Animated nodes */}
      {nodes.map((node, i) => (
        <circle
          key={`nd-${i}`}
          cx={node.x}
          cy={node.y}
          r="4"
          fill="var(--accent)"
          opacity="0"
        >
          <animate
            attributeName="opacity"
            values="0;1;0"
            dur="1.5s"
            begin={`${i * 0.15}s`}
            repeatCount="indefinite"
          />
          <animate
            attributeName="r"
            values="3;5;3"
            dur="1.5s"
            begin={`${i * 0.15}s`}
            repeatCount="indefinite"
          />
        </circle>
      ))}
    </svg>
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
