import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';

interface Props {
  open: boolean;
  onClose: () => void;
}

interface ToolbarItem {
  icon: string;
  command: string;
  value?: string;
  label: string;
}

const TOOLBAR_GROUPS: (ToolbarItem | 'sep')[][] = [
  [
    { icon: 'fa-bold', command: 'bold', label: '加粗' },
    { icon: 'fa-italic', command: 'italic', label: '斜体' },
    { icon: 'fa-underline', command: 'underline', label: '下划线' },
    { icon: 'fa-strikethrough', command: 'strikeThrough', label: '删除线' },
    { icon: 'fa-code', command: 'insertHTML', value: '<code>', label: '行内代码' },
  ],
  [
    { icon: 'fa-font', command: 'foreColor', value: '#e2e8f0', label: '文字颜色' },
  ],
  [
    { icon: 'fa-heading', command: 'formatBlock', value: 'H1', label: '标题1' },
    { icon: 'fa-heading', command: 'formatBlock', value: 'H2', label: '标题2' },
    { icon: 'fa-heading', command: 'formatBlock', value: 'H3', label: '标题3' },
  ],
  [
    { icon: 'fa-list-ul', command: 'insertUnorderedList', label: '无序列表' },
    { icon: 'fa-list-ol', command: 'insertOrderedList', label: '有序列表' },
  ],
  [
    { icon: 'fa-image', command: 'insertImage', label: '插入图片' },
    { icon: 'fa-quote-right', command: 'formatBlock', value: 'BLOCKQUOTE', label: '引用' },
    { icon: 'fa-square-check', command: 'insertHTML', value: '<div>☐ </div>', label: '任务列表' },
    { icon: 'fa-file-code', command: 'formatBlock', value: 'PRE', label: '代码块' },
  ],
  [
    { icon: 'fa-table', command: 'insertHTML', value: '<table><tr><td></td></tr></table>', label: '表格' },
  ],
  [
    { icon: 'fa-link', command: 'createLink', label: '链接' },
  ],
  [
    { icon: 'fa-rotate-left', command: 'undo', label: '撤销' },
    { icon: 'fa-rotate-right', command: 'redo', label: '重做' },
  ],
];

export default function NoteEditorDialog({ open, onClose }: Props) {
  const { addItem, selectedBaseId } = useKnowledgeStore();
  const editorRef = useRef<HTMLDivElement>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const execCommand = (item: ToolbarItem) => {
    editorRef.current?.focus();
    if (item.command === 'createLink') {
      const url = prompt('输入链接地址:');
      if (url) document.execCommand('createLink', false, url);
    } else if (item.command === 'insertImage') {
      const url = prompt('输入图片地址:');
      if (url) document.execCommand('insertImage', false, url);
    } else if (item.value) {
      document.execCommand(item.command, false, item.value);
    } else {
      document.execCommand(item.command, false, undefined);
    }
  };

  const handleSave = async () => {
    if (!selectedBaseId) return;
    const html = editorRef.current?.innerHTML || '';
    const text = editorRef.current?.textContent || '';
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      await addItem('note', {
        source: text.slice(0, 50) || '未命名笔记',
        content: html,
        title: text.slice(0, 50) || '未命名笔记',
      });
      if (editorRef.current) editorRef.current.innerHTML = '';
      onClose();
    } catch { /* */ } finally {
      setSubmitting(false);
    }
  };

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 20,
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
            background: 'none', border: 'none', color: 'var(--text-tertiary)',
            cursor: 'pointer', fontSize: 16, padding: 4,
          }}>✕</button>
        </div>

        {/* Toolbar */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 2, padding: '6px 12px',
          borderBottom: '1px solid var(--border-light)', flexShrink: 0,
          flexWrap: 'wrap',
        }}>
          {TOOLBAR_GROUPS.map((group, gi) => (
            <span key={gi} style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {group.map((item, ii) => {
                if (item === 'sep') {
                  return <span key={ii} style={{ width: 1, height: 20, background: 'var(--border-light)', margin: '0 4px', flexShrink: 0 }} />;
                }
                return (
                  <button
                    key={ii}
                    onClick={() => execCommand(item)}
                    title={item.label}
                    style={{
                      width: 28, height: 28, borderRadius: 4,
                      background: 'none', border: 'none',
                      color: 'var(--text-secondary)', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 13, padding: 0,
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.06)'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'none'; }}
                  >
                    {item.icon === 'fa-heading' ? (
                      <span style={{ fontSize: 12, fontWeight: 700 }}>{item.value}</span>
                    ) : item.icon === 'fa-font' ? (
                      <i className={`fa-solid ${item.icon}`} style={{ fontSize: 13, color: '#e2e8f0' }} />
                    ) : (
                      <i className={`fa-solid ${item.icon}`} style={{ fontSize: 13 }} />
                    )}
                  </button>
                );
              })}
            </span>
          ))}
        </div>

        {/* Editor */}
        <div style={{
          flex: 1, overflow: 'auto', padding: 0,
          border: '2px solid var(--accent-purple)', margin: 12, borderRadius: 8,
        }}>
          <div
            ref={editorRef}
            contentEditable
            suppressContentEditableWarning
            data-placeholder="输入'/'调用命令"
            style={{
              minHeight: '100%', padding: '16px 20px',
              fontSize: 14, lineHeight: 1.8,
              color: 'var(--text-primary)',
              outline: 'none',
              fontFamily: "'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif",
            }}
            onFocus={e => {
              const ph = e.currentTarget.getAttribute('data-placeholder');
              if (e.currentTarget.textContent === '' && ph) {
                e.currentTarget.textContent = '';
              }
            }}
            onBlur={e => {
              if (e.currentTarget.textContent === '') {
                e.currentTarget.innerHTML = '';
              }
            }}
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
          <button onClick={handleSave} disabled={submitting} style={{
            padding: '7px 20px', borderRadius: 6, fontSize: 13, fontWeight: 500,
            background: 'var(--accent-purple)', border: 'none', color: '#fff',
            cursor: 'pointer', fontFamily: 'inherit',
            opacity: submitting ? 0.7 : 1,
          }}>{submitting ? '保存中...' : '保 存'}</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
