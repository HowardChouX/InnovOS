import { useAnalysisStore } from '../../store/useAnalysisStore';
import { LoadingSpinner } from '../ui/LoadingSpinner';

const posStyles: Record<string, string> = {
  top: 'top-0 left-1/2 -translate-x-1/2',
  right: 'top-1/2 right-0 -translate-y-1/2',
  bottom: 'bottom-0 left-1/2 -translate-x-1/2',
  left: 'top-1/2 left-0 -translate-y-1/2',
};

export function ConflictDiagram() {
  const analysis = useAnalysisStore((s) => s.analysis);
  const loading = useAnalysisStore((s) => s.loading);

  if (loading) return <LoadingSpinner />;
  if (!analysis) return null;

  return (
    <div className="relative w-[200px] h-[200px] shrink-0">
      <svg className="absolute inset-0 w-full h-full">
        <circle cx="100" cy="100" r="70" stroke="#2a3b5c" strokeWidth="1" fill="none" strokeDasharray="4 4" />
      </svg>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60px] h-[60px] bg-slate-800 border-2 border-blue-400 rounded-full flex items-center justify-center text-center text-[11px] z-10">
        核心<br />冲突
      </div>
      {analysis.satelliteNodes.map((node) => (
        <div key={node.id} className={`absolute ${posStyles[node.position ?? 'top']} text-center text-[11px]`} style={{ color: node.color }}>
          {node.label}<br /><span className="text-[9px] opacity-60">{node.sublabel}</span>
        </div>
      ))}
    </div>
  );
}
