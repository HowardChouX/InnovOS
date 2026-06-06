import type { CSSProperties, ReactNode } from 'react';

interface GlassPanelProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  style?: CSSProperties;
}

export function GlassPanel({ children, className = '', hover, style }: GlassPanelProps) {
  return (
    <div
      className={`card ${className}`}
      style={{ ...(hover ? { cursor: 'pointer' } : {}), ...style }}
      onMouseEnter={hover ? (e) => { e.currentTarget.style.borderColor = 'var(--accent)'; } : undefined}
      onMouseLeave={hover ? (e) => { e.currentTarget.style.borderColor = 'var(--border-light)'; } : undefined}
    >
      {children}
    </div>
  );
}
