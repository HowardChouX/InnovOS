import { useCallback, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import RichEditor from '../../components/rich-editor';
import type { RichEditorRef } from '../../components/rich-editor/types';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function NoteEditorDialog({ open, onClose }: Props) {
  const { addItem, selectedBaseId } = useKnowledgeStore();
  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState('');
  const editorRef = useRef<RichEditorRef>(null);

  const handleSave = useCallback(async () => {
    if (!editorRef.current || !selectedBaseId) return;
    const html = editorRef.current.getHtml();
    const text = editorRef.current.getContent();
    const noteTitle = title.trim() || text.trim().slice(0, 50) || '未命名笔记';
    if (!text.trim() && !title.trim()) return;
    setSubmitting(true);
    try {
      await addItem('note', {
        source: noteTitle,
        content: html || text,
        title: noteTitle,
      });
      editorRef.current.clear();
      setTitle('');
      onClose();
    } catch { /* */ } finally {
      setSubmitting(false);
    }
  }, [selectedBaseId, addItem, onClose, title]);

  if (!open) return null;

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
    }} onClick={onClose}>
      <div style={{
        width: '100%', maxWidth: 960, height: '90vh',
        background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{
          padding: '12px 20px', borderBottom: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>添加笔记</span>
          <button onClick={onClose} style={{
            background: 'none', border: 'none',
            color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 16, padding: 4,
          }}>✕</button>
        </div>

        {/* Title */}
        <div style={{ flexShrink: 0, padding: '12px 16px 0' }}>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="笔记标题（可选）"
            style={{
              width: '100%', padding: '8px 12px', fontSize: 14, fontFamily: 'inherit',
              background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)',
              borderRadius: 6, color: 'var(--text-primary)', outline: 'none',
            }}
          />
        </div>

        {/* RichEditor — flex:1 fills remaining space */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: '8px 16px 12px' }}>
          <RichEditor
            ref={editorRef}
            showToolbar
            editable
            initialContent=""
            placeholder="输入内容..."
            wrapperStyle={{ flex: 1, minHeight: 0 }}
          />
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 20px', borderTop: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'flex-end', gap: 8, flexShrink: 0,
        }}>
          <button onClick={onClose} style={{
            padding: '7px 20px', borderRadius: 6, fontSize: 13,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
          }}>取 消</button>
          <button onClick={handleSave} disabled={submitting || !editorRef.current} style={{
            padding: '7px 20px', borderRadius: 6, fontSize: 13, fontWeight: 500,
            background: 'var(--accent-purple)', border: 'none', color: '#fff',
            cursor: 'pointer', fontFamily: 'inherit', opacity: submitting ? 0.7 : 1,
          }}>{submitting ? '保存中...' : '保 存'}</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
