import React, { useEffect, useRef, useState } from 'react';

interface MathInputDialogProps {
  /** Whether the dialog is visible */
  visible: boolean;
  /** Callback when the user confirms the formula */
  onSubmit: (formula: string) => void;
  /** Callback when the dialog is closed without submitting */
  onCancel: () => void;
  /** Initial LaTeX value */
  defaultValue?: string;
  /** Callback for real-time formula updates */
  onFormulaChange?: (formula: string) => void;
  /** Position relative to target element */
  position?: { x: number; y: number; top?: number };
  /** Scroll container reference to prevent scrolling */
  scrollContainer?: React.RefObject<HTMLDivElement | null>;
}

/**
 * Simple inline dialog for entering LaTeX formula.
 * Renders a small floating box with a multi-line input and confirm/cancel buttons.
 */
const MathInputDialog: React.FC<MathInputDialogProps> = ({
  visible,
  onSubmit,
  onCancel,
  defaultValue = '',
  onFormulaChange,
  position,
  scrollContainer,
}) => {
  const [value, setValue] = useState<string>(defaultValue);
  const containerRef = useRef<HTMLDivElement>(null);

  // Reset local state when dialog opens or defaultValue changes
  // This runs during render (not in an effect) to avoid cascading renders
  const [prevKey, setPrevKey] = useState('');
  const snapshotKey = visible ? defaultValue : '';
  if (snapshotKey !== prevKey) {
    setPrevKey(snapshotKey);
    if (visible) {
      setValue(defaultValue);
    }
  }

  // Prevent scroll container scrolling when dialog is open
  useEffect(() => {
    if (!visible) return;
    const el = scrollContainer?.current;
    if (!el) return;

    const originalOverflow = el.style.overflow;
    const originalScrollbarGutter = el.style.scrollbarGutter;

    // eslint-disable-next-line react-hooks/immutability
    el.style.overflow = 'hidden';
    el.style.scrollbarGutter = 'stable';

    return () => {
      el.style.overflow = originalOverflow;
      el.style.scrollbarGutter = originalScrollbarGutter;
    };
  }, [visible, scrollContainer]);

  useEffect(() => {
    if (visible && containerRef.current) {
      const textarea = containerRef.current.querySelector('textarea');
      if (textarea) {
        textarea.focus();
        const length = textarea.value.length;
        textarea.setSelectionRange(length, length);
      }
    }
  }, [visible]);

  if (!visible) return null;

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (trimmed) {
      onSubmit(trimmed);
    }
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  const getPositionStyles = (): React.CSSProperties => {
    if (position) {
      const dialogHeight = 200;
      const spaceBelow = window.innerHeight - position.y;
      const spaceAbove = position.y;

      const showAbove = spaceBelow < dialogHeight + 20 && spaceAbove > dialogHeight + 20;

      return {
        position: 'fixed',
        top: showAbove ? 'auto' : position.y + 10,
        bottom: showAbove ? window.innerHeight - (position.top || position.y) + 10 : 'auto',
        left: position.x,
        transform: 'translateX(-50%)',
        zIndex: 1000,
      };
    }

    return {
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      zIndex: 1000,
    };
  };

  const styles: React.CSSProperties = {
    ...getPositionStyles(),
    background: 'var(--bg-card, #ffffff)',
    border: '1px solid var(--border, #d9d9d9)',
    borderRadius: 8,
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    padding: 16,
    width: 360,
    maxWidth: '90vw',
  };

  const textareaStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 10px',
    fontSize: 13,
    fontFamily: 'monospace',
    border: '1px solid var(--border, #d9d9d9)',
    borderRadius: 4,
    background: 'var(--bg-input, #fff)',
    color: 'var(--color-foreground, #333)',
    outline: 'none',
    resize: 'vertical',
    boxSizing: 'border-box',
    marginBottom: 12,
  };

  const btnStyle: React.CSSProperties = {
    padding: '6px 14px',
    fontSize: 13,
    border: '1px solid var(--border, #d9d9d9)',
    borderRadius: 4,
    cursor: 'pointer',
    background: 'transparent',
    color: 'var(--color-foreground, #333)',
  };

  const primaryBtnStyle: React.CSSProperties = {
    ...btnStyle,
    background: 'var(--color-primary, #7c3aed)',
    color: '#fff',
    border: 'none',
  };

  return (
    <div style={styles} ref={containerRef}>
      <textarea
        value={value}
        rows={4}
        placeholder="输入 LaTeX 公式，如: \frac{a}{b}"
        onChange={(e) => {
          setValue(e.target.value);
          onFormulaChange?.(e.target.value);
        }}
        onKeyDown={handleKeyDown}
        style={textareaStyle}
      />
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button type="button" style={btnStyle} onClick={onCancel}>
          取消
        </button>
        <button type="button" style={primaryBtnStyle} onClick={handleSubmit}>
          确认
        </button>
      </div>
    </div>
  );
};

export default MathInputDialog;
