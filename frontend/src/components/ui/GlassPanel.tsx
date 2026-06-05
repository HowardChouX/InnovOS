import type { ReactNode } from 'react';

interface GlassPanelProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}

export function GlassPanel({ children, className = '', hover }: GlassPanelProps) {
  return (
    <div
      className={`card ${className}`}
      style={hover ? { cursor: 'pointer' } : undefined}
      onMouseEnter={hover ? (e) => { e.currentTarget.style.borderColor = 'var(--accent)'; } : undefined}
      onMouseLeave={hover ? (e) => { e.currentTarget.style.borderColor = 'var(--border-light)'; } : undefined}
    >
      {children}
    </div>
  );
}
