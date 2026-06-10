import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface Props {
  title: string;
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string) => void;
  initialName?: string;
}

export default function KnowledgeEntityNameDialog({ title, open, onClose, onSubmit, initialName = '' }: Props) {
  const [name, setName] = useState(initialName);

  useEffect(() => {
    setName(initialName);
  }, [initialName, open]);

  if (!open) return null;

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        width: 'min(400px, 90vw)',
        background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          padding: '14px 16px', borderBottom: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 16 }}>✕</button>
        </div>
        <div style={{ padding: 16 }}>
          <input
            autoFocus
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && name.trim()) { onSubmit(name.trim()); onClose(); } }}
            placeholder="名称"
            style={{
              width: '100%', padding: '8px 12px', borderRadius: 6, fontSize: 13,
              background: 'var(--bg-panel)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', outline: 'none', fontFamily: 'inherit',
            }}
          />
        </div>
        <div style={{
          padding: '12px 16px', borderTop: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'flex-end', gap: 8,
        }}>
          <button onClick={onClose} style={{
            padding: '7px 16px', borderRadius: 6, fontSize: 12,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
          }}>取消</button>
          <button onClick={() => { if (name.trim()) { onSubmit(name.trim()); onClose(); } }}
            disabled={!name.trim()} style={{
              padding: '7px 20px', borderRadius: 6, fontSize: 13, fontWeight: 500, fontFamily: 'inherit',
              background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer',
              opacity: !name.trim() ? 0.5 : 1,
            }}>确定</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
