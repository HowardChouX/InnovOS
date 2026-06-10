import React from 'react'

interface PlaceholderBlockProps {
  /** Icon element to display */
  icon: React.ReactNode
  /** Localised message */
  message: string
  /** Click handler */
  onClick: () => void
}

/**
 * Reusable placeholder block for TipTap NodeViews (math / image etc.)
 * Uses CSS variables for theming (no i18n, no useTheme dependency).
 */
const PlaceholderBlock: React.FC<PlaceholderBlockProps> = ({ icon, message, onClick }) => {
  return (
    <div
      onClick={onClick}
      style={{
        border: '2px dashed var(--border)',
        borderRadius: 6,
        padding: 24,
        margin: '8px 0',
        textAlign: 'center',
        cursor: 'pointer',
        background: 'var(--bg-card)',
        transition: 'all 0.2s ease',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        minHeight: 80
      }}
      onMouseEnter={(e) => {
        const target = e.currentTarget as HTMLElement
        target.style.borderColor = 'var(--accent)'
        target.style.backgroundColor = 'rgba(59, 130, 246, 0.15)'
      }}
      onMouseLeave={(e) => {
        const target = e.currentTarget as HTMLElement
        target.style.borderColor = 'var(--border)'
        target.style.backgroundColor = 'var(--bg-card)'
      }}>
      {icon}
      <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>{message}</span>
    </div>
  )
}

export default PlaceholderBlock
