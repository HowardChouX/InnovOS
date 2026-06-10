import React from 'react'

// Simple cn utility (replaces @renderer/utils)
function cn(...classes: (string | false | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ')
}

// Styled components using inline styles pattern
export const ToolbarWrapper = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  (props, ref) => (
    <div
      ref={ref}
      {...props}
      className={cn('rich-editor-toolbar-wrapper', props.className)}
      style={{
        display: 'flex', alignItems: 'center', gap: '2px',
        padding: '6px 12px', borderBottom: '1px solid var(--border)',
        flexShrink: 0, flexWrap: 'wrap', overflow: 'hidden',
        ...props.style,
      }}
    />
  )
)
ToolbarWrapper.displayName = 'ToolbarWrapper'

export const ToolbarButton = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { $active?: boolean }>(
  ({ $active, ...props }, ref) => (
    <button
      ref={ref}
      {...props}
      style={{
        width: 28, height: 28, borderRadius: 4,
        background: $active ? 'rgba(139,92,246,0.15)' : 'transparent',
        border: 'none',
        color: $active ? 'var(--accent-purple)' : 'var(--text-secondary)',
        cursor: props.disabled ? 'not-allowed' : 'pointer',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 13, padding: 0, opacity: props.disabled ? 0.4 : 1,
        ...props.style,
      } as React.CSSProperties}
    />
  )
)
ToolbarButton.displayName = 'ToolbarButton'

export const ToolbarDivider: React.FC = () => (
  <span style={{ width: 1, height: 22, background: 'var(--border-light)', margin: '0 4px', flexShrink: 0 }} />
)

// Content area wrapper
export const EditorContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  (props, ref) => (
    <div
      ref={ref}
      {...props}
      className={cn('rich-editor-content', props.className)}
      style={{
        flex: 1, display: 'flex', minHeight: 0,
        ...props.style,
      }}
    />
  )
)
EditorContent.displayName = 'StyledEditorContent'

// Main wrapper
export const RichEditorWrapper = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & {
  $minHeight?: number; $maxHeight?: number; $isFullWidth?: boolean;
  $fontFamily?: string; $fontSize?: number;
}>(
  ({ $minHeight, $maxHeight, $isFullWidth, $fontFamily, $fontSize, ...props }, ref) => (
    <div
      ref={ref}
      {...props}
      className={cn('rich-editor-wrapper', props.className)}
      style={{
        display: 'flex', flexDirection: 'column', minHeight: 0,
        maxHeight: $maxHeight || 'none',
        fontFamily: $fontFamily === 'default' ? '"PingFang SC","Microsoft YaHei","Inter",sans-serif' : $fontFamily,
        fontSize: $fontSize || 16,
        border: '1px solid var(--border)',
        borderRadius: 8,
        background: 'var(--bg-panel)',
        color: 'var(--text-primary)',
        ...props.style,
      } as React.CSSProperties}
    />
  )
)
RichEditorWrapper.displayName = 'RichEditorWrapper'
