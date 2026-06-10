import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function AddUrlDialog({ open, onClose }: Props) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { addItem } = useKnowledgeStore();

  // Focus textarea on open
  useEffect(() => {
    if (open) {
      // 延迟聚焦，确保 dialog 已渲染
      requestAnimationFrame(() => textareaRef.current?.focus());
    }
  }, [open]);

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setText('');
      setError('');
      setSubmitting(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    const urls = text
      .split('\n')
      .map(u => u.trim())
      .filter(u => u.length > 0);

    if (urls.length === 0) {
      setError('请输入至少一个网址');
      return;
    }

    // Validate URLs
    const invalid = urls.filter(u => {
      try {
        new URL(u);
        return false;
      } catch {
        return true;
      }
    });
    if (invalid.length > 0) {
      setError(`无效的网址:\n${invalid.slice(0, 3).join('\n')}${invalid.length > 3 ? `\n... 还有 ${invalid.length - 3} 个` : ''}`);
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      // 逐个添加
      for (const url of urls) {
        await addItem('url', { source: url, url });
      }
      onClose();
    } catch (e: any) {
      setError(e?.message || '添加失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Ctrl/Cmd + Enter → 提交
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
    // Escape → 关闭
    if (e.key === 'Escape' && !submitting) {
      onClose();
    }
  };

  if (!open) return null;

  const count = text.split('\n').filter(u => u.trim()).length;

  return createPortal(
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 'min(520px, 90vw)',
          background: 'var(--bg-card)',
          borderRadius: 12,
          border: '1px solid var(--border)',
          boxShadow: '0 20px 60px var(--shadow)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '14px 16px', borderBottom: '1px solid var(--border-light)',
        }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
            添加网址
          </span>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: 'var(--text-tertiary)',
              cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: 0,
            }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 16 }}>
          <textarea
            ref={textareaRef}
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="请输入网址，多个网址用回车分隔"
            style={{
              width: '100%',
              height: 200,
              padding: 12,
              borderRadius: 8,
              fontSize: 13,
              lineHeight: 1.6,
              fontFamily: 'inherit',
              background: 'var(--bg-panel)',
              border: `1px solid ${error ? 'var(--accent-red)' : 'var(--border)'}`,
              color: 'var(--text-primary)',
              outline: 'none',
              resize: 'vertical',
              boxSizing: 'border-box',
            }}
          />

          {/* Helper row */}
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginTop: 8, minHeight: 22,
          }}>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
              {count > 0 ? `已识别 ${count} 个网址` : ''}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              Ctrl+Enter 快速提交
            </span>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              marginTop: 8, padding: '8px 12px', borderRadius: 6,
              border: '1px solid var(--accent-red)',
              background: 'color-mix(in srgb, var(--accent-red) 8%, transparent)',
              color: 'var(--accent-red)',
              fontSize: 12, whiteSpace: 'pre-line', lineHeight: 1.4,
            }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', justifyContent: 'flex-end', gap: 8,
          padding: '12px 16px', borderTop: '1px solid var(--border-light)',
        }}>
          <button
            onClick={onClose}
            disabled={submitting}
            style={{
              padding: '7px 20px', borderRadius: 6, fontSize: 13, fontFamily: 'inherit',
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--text-secondary)', cursor: submitting ? 'not-allowed' : 'pointer',
              opacity: submitting ? 0.5 : 1,
            }}
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || count === 0}
            style={{
              padding: '7px 24px', borderRadius: 6, fontSize: 13, fontWeight: 500,
              fontFamily: 'inherit',
              background: submitting || count === 0 ? 'var(--border)' : 'var(--accent-blue)',
              border: 'none', color: '#fff',
              cursor: submitting || count === 0 ? 'not-allowed' : 'pointer',
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? '添加中...' : '确定'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
