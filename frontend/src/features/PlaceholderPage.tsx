import { GlassPanel } from '../components/ui/GlassPanel';

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="p-6">
      <GlassPanel>
        <div className="flex items-center gap-2 mb-4">
          <i className="fa-solid fa-cube" style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
        </div>
        <div className="flex flex-col items-center justify-center py-16" style={{ color: 'var(--text-tertiary)' }}>
          <i className="fa-solid fa-cube text-4xl mb-4" style={{ color: 'var(--text-tertiary)', opacity: 0.5 }} />
          <p className="text-sm">该功能正在开发中...</p>
        </div>
      </GlassPanel>
    </div>
  );
}
