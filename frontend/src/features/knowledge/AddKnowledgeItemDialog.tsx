import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import NoteEditorDialog from './NoteEditorDialog';

const SOURCE_TABS = [
  { key: 'file', label: '文件', icon: 'fa-file-lines' },
  { key: 'note', label: '笔记', icon: 'fa-note-sticky' },
  { key: 'url', label: '网址', icon: 'fa-link' },
  { key: 'directory', label: '目录', icon: 'fa-folder' },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function AddKnowledgeItemDialog({ open, onClose }: Props) {
  const [activeTab, setActiveTab] = useState('file');
  const [files, setFiles] = useState<File[]>([]);
  const [url, setUrl] = useState('');
  const [directory, setDirectory] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [noteEditorOpen, setNoteEditorOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { uploadFile, addItem } = useKnowledgeStore();

  if (!open) return null;

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    setFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const filesList = e.target.files;
    if (filesList) setFiles(prev => [...prev, ...Array.from(filesList as Iterable<File>)]);
    e.target.value = '';
  };

  const handleSubmit = async () => {
    setUploading(true);
    try {
      if (activeTab === 'file' && files.length > 0) {
        for (const file of files) await uploadFile(file);
        setFiles([]);
        onClose();
      } else if (activeTab === 'url' && url.trim()) {
        await addItem('url', { source: url, url });
        setUrl('');
        onClose();
      } else if (activeTab === 'directory' && directory.trim()) {
        await addItem('directory', { source: directory, path: directory });
        setDirectory('');
        onClose();
      }
    } catch { /* */ } finally { setUploading(false); }
  };

  const canSubmit = (
    (activeTab === 'file' && files.length > 0) ||
    (activeTab === 'url' && url.trim().length > 0) ||
    (activeTab === 'directory' && directory.trim().length > 0)
  );

  const handleTabClick = (tabKey: string) => {
    if (tabKey === 'note') {
      setNoteEditorOpen(true);
      return;
    }
    setActiveTab(tabKey);
  };

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        width: 'min(520px, 90vw)', maxHeight: '80vh',
        background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{
          padding: '14px 16px', borderBottom: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>添加知识</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 16 }}>✕</button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-light)' }}>
          {SOURCE_TABS.map(tab => (
            <button key={tab.key} onClick={() => handleTabClick(tab.key)} style={{
              flex: 1, padding: '10px', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit',
              background: activeTab === tab.key ? 'rgba(139,92,246,0.08)' : 'transparent',
              border: 'none', borderBottom: activeTab === tab.key ? '2px solid var(--accent-purple)' : '2px solid transparent',
              color: activeTab === tab.key ? 'var(--accent-purple)' : 'var(--text-secondary)',
              fontWeight: activeTab === tab.key ? 600 : 400,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
              <i className={`fa-solid ${tab.icon}`} style={{ fontSize: 11 }} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {activeTab === 'file' && (
            <div>
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                style={{
                  border: `2px dashed ${dragOver ? 'var(--accent-purple)' : 'var(--border)'}`,
                  borderRadius: 8, padding: 40, textAlign: 'center', cursor: 'pointer',
                  background: dragOver ? 'rgba(139,92,246,0.04)' : 'transparent',
                  transition: 'all 0.15s', marginBottom: files.length > 0 ? 12 : 0,
                }}
              >
                <i className="fa-solid fa-cloud-arrow-up" style={{ fontSize: 28, color: 'var(--text-tertiary)', marginBottom: 8, display: 'block' }} />
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>拖拽或点击上传文件</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>支持 .txt .md .pdf .docx .csv</div>
                <input ref={fileRef} type="file" multiple style={{ display: 'none' }} onChange={handleFileSelect} />
              </div>
              {files.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {files.map((f, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                      borderRadius: 6, background: 'rgba(0,0,0,0.15)', fontSize: 12, color: 'var(--text-primary)',
                    }}>
                      <i className="fa-regular fa-file" />
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                      <span style={{ color: 'var(--text-tertiary)' }}>{(f.size / 1024).toFixed(1)}KB</span>
                      <button onClick={() => setFiles(p => p.filter((_, j) => j !== i))}
                        style={{ background: 'none', border: 'none', color: 'var(--accent-red)', cursor: 'pointer' }}>✕</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'url' && (
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>输入网页 URL，系统将自动抓取内容</div>
              <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://example.com/document"
                style={{
                  width: '100%', padding: '8px 12px', borderRadius: 6, fontSize: 13,
                  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', outline: 'none', fontFamily: 'inherit',
                }} />
            </div>
          )}

          {activeTab === 'directory' && (
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>输入本地目录路径</div>
              <input value={directory} onChange={e => setDirectory(e.target.value)} placeholder="/path/to/documents"
                style={{
                  width: '100%', padding: '8px 12px', borderRadius: 6, fontSize: 13,
                  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', outline: 'none', fontFamily: 'inherit',
                }} />
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 16px', borderTop: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'flex-end', gap: 8,
        }}>
          <button onClick={onClose} style={{
            padding: '7px 16px', borderRadius: 6, fontSize: 13,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
          }}>取消</button>
          <button onClick={handleSubmit} disabled={!canSubmit || uploading} style={{
            padding: '7px 20px', borderRadius: 6, fontSize: 13, fontWeight: 500, fontFamily: 'inherit',
            background: canSubmit ? 'var(--accent-purple)' : 'var(--border)',
            border: 'none', color: '#fff', cursor: 'pointer',
            opacity: uploading ? 0.7 : 1,
          }}>{uploading ? '添加中...' : '添加'}</button>
        </div>
      </div>

      <NoteEditorDialog open={noteEditorOpen} onClose={() => setNoteEditorOpen(false)} />
    </div>,
    document.body
  );
}
