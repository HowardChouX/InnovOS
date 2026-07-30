import { createPortal } from 'react-dom';
import { AlertCircle } from 'lucide-react';

interface InlineConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: 'red' | 'blue' | 'yellow' | 'green';
  onConfirm: () => void;
  onCancel: () => void;
}

/** @deprecated kept for interface compat */
const colorClasses = { red: {} as const, blue: {} as const, yellow: {} as const, green: {} as const };
void colorClasses;

export function InlineConfirmModal({
  open,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  confirmColor: _confirmColor = 'red',
  onConfirm,
  onCancel,
}: InlineConfirmModalProps) {
  if (!open) return null;

  const modalContent = (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center"
      style={{
        background: 'rgba(0,0,0,0.6)',
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={onCancel}
    >
      <div
        style={{
          width: 360,
          maxWidth: '90vw',
          background: 'var(--bg-card, #1a202c)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: 24,
          boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
          zIndex: 301,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 12,
            fontSize: 15,
            fontWeight: 600,
            color: 'var(--accent-red)',
          }}
        >
          <AlertCircle size={20} />
          {title}
        </div>
        <div
          style={{
            fontSize: 13,
            color: 'var(--text-secondary)',
            lineHeight: 1.6,
            marginBottom: 20,
          }}
        >
          {message}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button
            onClick={onCancel}
            style={{
              padding: '6px 16px',
              borderRadius: 6,
              fontSize: 12,
              background: 'rgba(100,116,139,0.1)',
              border: '1px solid var(--border-light)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: '6px 16px',
              borderRadius: 6,
              fontSize: 12,
              background: '#ef4444',
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
