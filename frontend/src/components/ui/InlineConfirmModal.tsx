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

export function InlineConfirmModal({
  open,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  confirmColor = 'red',
  onConfirm,
  onCancel,
}: InlineConfirmModalProps) {
  if (!open) return null;

  const colorMap = {
    red: { bg: 'rgba(248,113,113,0.15)', border: 'rgba(248,113,113,0.3)', text: 'var(--accent-red)', btn: 'var(--accent-red)' },
    blue: { bg: 'rgba(59,130,246,0.15)', border: 'rgba(59,130,246,0.3)', text: 'var(--accent-blue)', btn: 'var(--accent-blue)' },
    yellow: { bg: 'rgba(251,191,36,0.15)', border: 'rgba(251,191,36,0.3)', text: 'var(--accent-yellow)', btn: 'var(--accent-yellow)' },
    green: { bg: 'rgba(74,222,128,0.15)', border: 'rgba(74,222,128,0.3)', text: 'var(--accent-green)', btn: 'var(--accent-green)' },
  };

  const c = colorMap[confirmColor];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 300,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: 'var(--bg-card)',
          borderRadius: 12,
          border: `1px solid ${c.border}`,
          padding: 24,
          width: 360,
          maxWidth: '90vw',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: c.text,
            marginBottom: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <i className="fa-solid fa-circle-question" />
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
              padding: '6px 14px',
              borderRadius: 6,
              fontSize: 12,
              background: 'rgba(100,116,139,0.1)',
              border: '1px solid var(--border-light)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              fontSize: 12,
              background: c.btn,
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
