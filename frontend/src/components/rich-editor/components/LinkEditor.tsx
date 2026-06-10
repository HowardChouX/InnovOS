import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface LinkEditorProps {
  /** Whether the editor is visible */
  visible: boolean
  /** Position for the popup */
  position: { x: number; y: number } | null
  /** Link attributes */
  link: { href: string; text: string }
  /** Callback when the user saves the link */
  onSave: (href: string, text: string) => void
  /** Callback when the user removes the link */
  onRemove: () => void
  /** Callback when the editor is closed without saving */
  onCancel: () => void
  /** Whether to show remove button */
  showRemove?: boolean
}

/**
 * Inline link editor that appears on hover over links
 * Provides input fields for editing link URL and title
 */
const LinkEditor: React.FC<LinkEditorProps> = ({
  visible,
  position,
  link,
  onSave,
  onRemove,
  onCancel,
  showRemove = true
}) => {
  const { t } = useTranslation()
  const [href, setHref] = useState<string>(link.href || '')
  const [text, setText] = useState<string>(link.text || '')
  const containerRef = useRef<HTMLDivElement>(null)
  const hrefInputRef = useRef<HTMLInputElement>(null)

  // Reset values when link changes
  useEffect(() => {
    if (visible) {
      setHref(link.href || '')
      setText(link.text || '')
    }
  }, [visible, link.href, link.text])

  // Auto-focus href input when dialog opens
  useEffect(() => {
    if (visible && hrefInputRef.current) {
      setTimeout(() => {
        hrefInputRef.current?.focus()
      }, 100)
    }
  }, [visible])

  // Handle clicks outside to close
  useEffect(() => {
    if (!visible) return

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement

      if (containerRef.current?.contains(target) || target.closest('a[href]') || target.closest('[data-link-editor]')) {
        return
      }

      onCancel()
    }

    setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside)
    }, 100)

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [visible, onCancel])

  const handleSave = useCallback(() => {
    const trimmedHref = href.trim()
    const trimmedText = text.trim()
    if (trimmedHref && trimmedText) {
      onSave(trimmedHref, trimmedText)
    }
  }, [href, text, onSave])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        handleSave()
      } else if (e.key === 'Escape') {
        e.preventDefault()
        onCancel()
      }
    },
    [handleSave, onCancel]
  )

  if (!visible || !position) return null

  const styles: React.CSSProperties = {
    position: 'fixed',
    left: position.x,
    top: position.y + 25,
    zIndex: 1000,
    background: 'var(--color-background, #ffffff)',
    border: '1px solid var(--color-border, #d9d9d9)',
    borderRadius: 8,
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    padding: 12,
    width: 320,
    maxWidth: '90vw'
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '4px 8px',
    fontSize: 13,
    border: '1px solid var(--color-border, #d9d9d9)',
    borderRadius: 4,
    background: 'var(--color-background, #fff)',
    color: 'var(--color-foreground, #333)',
    outline: 'none',
    boxSizing: 'border-box',
    height: 32,
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 600,
    display: 'block',
    marginBottom: 4,
  }

  const btnStyle: React.CSSProperties = {
    padding: '6px 12px',
    fontSize: 13,
    border: '1px solid var(--color-border, #d9d9d9)',
    borderRadius: 4,
    cursor: 'pointer',
    background: 'transparent',
    color: 'var(--color-foreground, #333)',
  }

  const primaryBtnStyle: React.CSSProperties = {
    ...btnStyle,
    background: 'var(--color-primary, #7c3aed)',
    color: '#fff',
    border: 'none',
  }

  const dangerBtnStyle: React.CSSProperties = {
    ...btnStyle,
    color: 'var(--color-danger, #e53e3e)',
    borderColor: 'var(--color-danger, #e53e3e)',
  }

  return (
    <div style={styles} ref={containerRef} data-link-editor onKeyDown={handleKeyDown}>
      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>
          {t('richEditor.link.text')}
        </label>
        <input
          ref={hrefInputRef}
          style={inputStyle}
          value={text}
          placeholder={t('richEditor.link.textPlaceholder')}
          onChange={(e) => setText(e.target.value)}
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={labelStyle}>
          {t('richEditor.link.url')}
        </label>
        <input
          style={inputStyle}
          value={href}
          placeholder="https://example.com"
          onChange={(e) => setHref(e.target.value)}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          {showRemove && (
            <button type="button" style={dangerBtnStyle} onClick={onRemove}>
              {t('richEditor.link.remove')}
            </button>
          )}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button type="button" style={btnStyle} onClick={onCancel}>
            {t('common.cancel')}
          </button>
          <button
            type="button"
            style={primaryBtnStyle}
            onClick={handleSave}
            disabled={!href.trim() || !text.trim()}
          >
            {t('common.save')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default LinkEditor
