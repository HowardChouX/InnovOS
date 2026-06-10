import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import NoteEditorDialog from './NoteEditorDialog';

const SOURCE_TABS = [
  { key: 'file', label: '文件', icon: 'fa-file-lines' },
  { key: 'note', label: '笔记', icon: 'fa-note-sticky' },
  { key: 'url', label: '网址', icon: 'fa-link' },
  { key: 'directory', label: '文件夹', icon: 'fa-folder' },
];

const SUPPORTED_EXTS = ['.pdf', '.docx', '.doc', '.txt', '.md', '.csv'];
const MAX_DIRECTORY_FILES = 1000;

interface Props {
  open: boolean;
  onClose: () => void;
}

export function AddKnowledgeItemDialog({ open, onClose }: Props) {
  const [activeTab, setActiveTab] = useState('file');
  const [files, setFiles] = useState<File[]>([]);
  const [url, setUrl] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [noteEditorOpen, setNoteEditorOpen] = useState(false);
  const [bannerWarning, setBannerWarning] = useState<{
    type: 'unsupported';
    count: number;
  } | null>(null);
  const [infoDialog, setInfoDialog] = useState<{
    type: 'unsupported' | 'limit';
    count: number;
    total: number;
    supported: File[];
  } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const dirRef = useRef<HTMLInputElement>(null);
  const { uploadFile, addItem, importDirectory } = useKnowledgeStore();

  if (!open) return null;

  const isSupported = (name: string) => {
    const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
    return SUPPORTED_EXTS.includes(ext);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files);
    const supported = dropped.filter(f => isSupported(f.name));
    const unsupportedCount = dropped.length - supported.length;
    if (unsupportedCount > 0) {
      setBannerWarning({ type: 'unsupported', count: unsupportedCount });
    } else {
      setBannerWarning(null);
    }
    setFiles(prev => [...prev, ...supported]);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    if (list) {
      const arr = Array.from(list);
      const supported = arr.filter(f => isSupported(f.name));
      const unsupportedCount = arr.length - supported.length;
      if (unsupportedCount > 0) {
        setBannerWarning({ type: 'unsupported', count: unsupportedCount });
      } else {
        setBannerWarning(null);
      }
      setFiles(prev => [...prev, ...supported]);
    }
    e.target.value = '';
  };

  const handleDirSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    if (list) {
      const arr = Array.from(list);
      const supported = arr.filter(f => isSupported(f.name));
      const unsupported = arr.filter(f => !isSupported(f.name));
      const limited = supported.slice(0, MAX_DIRECTORY_FILES);
      const skipped = supported.length - limited.length;

      if (unsupported.length > 0) {
        setInfoDialog({
          type: 'unsupported',
          count: unsupported.length,
          total: arr.length,
          supported: limited,
        });
      } else if (skipped > 0) {
        setInfoDialog({
          type: 'limit',
          count: skipped,
          total: arr.length,
          supported: limited,
        });
      } else {
        setFiles(limited);
      }
    }
    e.target.value = '';
  };

  const removeFile = (i: number) => setFiles(prev => prev.filter((_, j) => j !== i));
  const clearAll = () => {
    setFiles([]);
    setUrl('');
    setError('');
    setBannerWarning(null);
  };

  const handleTabClick = (tabKey: string) => {
    if (tabKey === 'note') {
      setNoteEditorOpen(true);
      return;
    }
    setActiveTab(tabKey);
    clearAll();
  };

  const handleSubmit = async () => {
    setError('');
    setUploading(true);
    try {
      if (activeTab === 'file' && files.length > 0) {
        for (const file of files) await uploadFile(file);
        clearAll();
        onClose();
      } else if (activeTab === 'url' && url.trim()) {
        await addItem('url', { source: url, url });
        clearAll();
        onClose();
      } else if (activeTab === 'directory' && files.length > 0) {
        await importDirectory(files);
        clearAll();
        onClose();
      }
    } catch (e: any) {
      setError(e?.message || '导入失败，请重试');
    } finally {
      setUploading(false);
    }
  };

  const canSubmit = (
    (activeTab === 'file' && files.length > 0) ||
    (activeTab === 'url' && url.trim().length > 0) ||
    (activeTab === 'directory' && files.length > 0)
  );

  const supportedCount = files.filter(f => isSupported(f.name)).length;

  // ─── Styles ─────────────────────────────────────────
  const overlayStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 9999,
    background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  };

  const dialogStyle: React.CSSProperties = {
    width: 'min(520px, 90vw)',
    maxHeight: '70vh',
    background: 'var(--bg-card)',
    borderRadius: 12,
    border: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: '0 20px 60px var(--shadow)',
  };

  const headerStyle: React.CSSProperties = {
    padding: '14px 16px',
    borderBottom: '1px solid var(--border-light)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexShrink: 0,
  };

  const tabsContainerStyle: React.CSSProperties = {
    display: 'flex',
    borderBottom: '1px solid var(--border-light)',
    flexShrink: 0,
  };

  const getTabStyle = (isActive: boolean): React.CSSProperties => ({
    flex: 1,
    padding: '10px 0',
    fontSize: 13,
    cursor: 'pointer',
    fontFamily: 'inherit',
    background: 'transparent',
    border: 'none',
    borderBottom: isActive ? '2px solid var(--accent-green)' : '2px solid transparent',
    color: isActive ? 'var(--accent-green)' : 'var(--text-secondary)',
    fontWeight: isActive ? 600 : 400,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    transition: 'color 0.15s, border-color 0.15s',
  });

  const contentStyle: React.CSSProperties = {
    flex: 1,
    overflow: 'auto',
    padding: 16,
    minHeight: 0,
  };

  const dropzoneStyle = (isDragOver: boolean): React.CSSProperties => ({
    border: `2px dashed ${isDragOver ? 'var(--accent-green)' : 'var(--border)'}`,
    borderRadius: 8,
    padding: '36px 24px',
    textAlign: 'center',
    cursor: 'pointer',
    background: isDragOver ? 'color-mix(in srgb, var(--accent-green) 4%, transparent)' : 'transparent',
    transition: 'all 0.15s',
    marginBottom: files.length > 0 ? 12 : 0,
  });

  const dropzoneHoverStyle: React.CSSProperties = {
    borderColor: 'var(--accent-green)',
    background: 'color-mix(in srgb, var(--accent-green) 4%, transparent)',
  };

  const fileRowStyle = (supported: boolean): React.CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'auto minmax(0, 1fr) auto auto',
    alignItems: 'center',
    gap: 8,
    padding: '7px 10px',
    borderRadius: 6,
    background: 'var(--bg-card)',
    fontSize: 12,
    color: 'var(--text-primary)',
    opacity: supported ? 1 : 0.5,
    marginBottom: 4,
  });

  const footerStyle: React.CSSProperties = {
    padding: '12px 16px',
    borderTop: '1px solid var(--border-light)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexShrink: 0,
  };

  const cancelBtnStyle: React.CSSProperties = {
    padding: '7px 16px',
    borderRadius: 6,
    fontSize: 13,
    background: 'transparent',
    border: '1px solid var(--border)',
    color: 'var(--text-secondary)',
    cursor: 'pointer',
    fontFamily: 'inherit',
  };

  const submitBtnStyle = (enabled: boolean): React.CSSProperties => ({
    padding: '7px 20px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 500,
    fontFamily: 'inherit',
    background: enabled ? 'var(--accent-blue)' : 'var(--border)',
    border: 'none',
    color: '#fff',
    cursor: enabled ? 'pointer' : 'not-allowed',
    opacity: uploading ? 0.7 : 1,
    transition: 'opacity 0.15s',
  });

  const errorBannerStyle: React.CSSProperties = {
    padding: '8px 12px',
    borderRadius: 6,
    border: '1px solid var(--accent-red)',
    background: 'color-mix(in srgb, var(--accent-red) 8%, transparent)',
    color: 'var(--accent-red)',
    fontSize: 12,
    marginBottom: 12,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  };

  const warningBannerStyle: React.CSSProperties = {
    padding: '8px 12px',
    borderRadius: 6,
    border: '1px solid var(--accent-yellow)',
    background: 'color-mix(in srgb, var(--accent-yellow) 8%, transparent)',
    color: 'var(--accent-yellow)',
    fontSize: 12,
    marginBottom: 12,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 12px',
    borderRadius: 6,
    fontSize: 13,
    background: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    color: 'var(--text-primary)',
    outline: 'none',
    fontFamily: 'inherit',
    boxSizing: 'border-box',
  };

  // ─── InfoDialog ─────────────────────────────────────
  const renderInfoDialog = () => {
    if (!infoDialog) return null;
    const { type, count, total, supported } = infoDialog;
    return createPortal(
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 10000, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        onClick={() => { setInfoDialog(null); setFiles(supported); }}
      >
        <div
          style={{ background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)', padding: 24, maxWidth: 420, width: '90vw' }}
          onClick={e => e.stopPropagation()}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <i
              className={`fa-solid ${type === 'unsupported' ? 'fa-triangle-exclamation' : 'fa-circle-info'}`}
              style={{ color: type === 'unsupported' ? 'var(--accent-yellow)' : 'var(--accent-blue)', fontSize: 18 }}
            />
            <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14 }}>
              {type === 'unsupported' ? '不支持的格式' : '导入提示'}
            </span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
            {type === 'unsupported'
              ? `检测到 ${count} 个不支持的文件格式，已自动过滤。仅支持 ${SUPPORTED_EXTS.join(', ')} 格式。`
              : `文件夹共包含 ${total} 个文件，已自动限制导入前 ${MAX_DIRECTORY_FILES} 个。`}
          </p>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={() => { setInfoDialog(null); setFiles(supported); }}
              style={{
                padding: '7px 20px', borderRadius: 6, fontSize: 13,
                background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit',
              }}
            >
              知道了
            </button>
          </div>
        </div>
      </div>,
      document.body
    );
  };

  // ─── Render ─────────────────────────────────────────
  return createPortal(
    <div style={overlayStyle} onClick={onClose}>
      <div style={dialogStyle} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={headerStyle}>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>添加知识</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 18, lineHeight: 1 }}>×</button>
        </div>

        {/* Tabs */}
        <div style={tabsContainerStyle}>
          {SOURCE_TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => handleTabClick(tab.key)}
              style={getTabStyle(activeTab === tab.key)}
              onMouseEnter={e => {
                if (activeTab !== tab.key) {
                  (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-primary)';
                }
              }}
              onMouseLeave={e => {
                if (activeTab !== tab.key) {
                  (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-secondary)';
                }
              }}
            >
              <i className={`fa-solid ${tab.icon}`} style={{ fontSize: 11 }} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={contentStyle}>
          {/* Error Banner */}
          {error && (
            <div style={errorBannerStyle}>
              <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: 11 }} />
              <span>{error}</span>
            </div>
          )}

          {/* ── File Tab ── */}
          {activeTab === 'file' && (
            <div>
              {/* Warning Banner for unsupported files */}
              {bannerWarning && (
                <div style={warningBannerStyle}>
                  <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: 11 }} />
                  <span>{bannerWarning.count} 个不支持的文件格式已自动过滤</span>
                </div>
              )}

              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                style={dropzoneStyle(dragOver)}
                onMouseEnter={e => Object.assign(e.currentTarget.style, dropzoneHoverStyle)}
                onMouseLeave={e => Object.assign(e.currentTarget.style, dropzoneStyle(false))}
              >
                <i className="fa-solid fa-cloud-arrow-up" style={{ fontSize: 28, color: 'var(--text-tertiary)', marginBottom: 10, display: 'block' }} />
                <div style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 6, fontWeight: 500 }}>拖拽或点击上传文件</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>支持 .txt .md .pdf .docx .csv</div>
                <input ref={fileRef} type="file" multiple style={{ display: 'none' }} onChange={handleFileSelect} />
              </div>

              {files.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
                  {files.map((f, i) => (
                    <div key={i} style={fileRowStyle(true)}>
                      <i className="fa-regular fa-file" style={{ color: 'var(--accent-blue)', fontSize: 13 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                      <span style={{ color: 'var(--text-tertiary)', fontSize: 11, whiteSpace: 'nowrap' }}>{(f.size / 1024).toFixed(1)} KB</span>
                      <button
                        onClick={() => removeFile(i)}
                        style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 12, padding: '2px 4px' }}
                      >
                        <i className="fa-solid fa-xmark" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── URL Tab ── */}
          {activeTab === 'url' && (
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>输入网页 URL，系统将自动抓取内容</div>
              <input
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://example.com/document"
                style={inputStyle}
              />
            </div>
          )}

          {/* ── Directory Tab ── */}
          {activeTab === 'directory' && (
            <div>
              <div
                onClick={() => dirRef.current?.click()}
                style={{
                  ...dropzoneStyle(false),
                  marginBottom: files.length > 0 ? 12 : 0,
                }}
                onMouseEnter={e => Object.assign(e.currentTarget.style, dropzoneHoverStyle)}
                onMouseLeave={e => Object.assign(e.currentTarget.style, dropzoneStyle(false))}
              >
                <i className="fa-solid fa-folder-open" style={{ fontSize: 28, color: 'var(--text-tertiary)', marginBottom: 10, display: 'block' }} />
                <div style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 6, fontWeight: 500 }}>点击选择文件夹</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>将上传文件夹内所有支持的文件</div>
                <input ref={dirRef} type="file" {...{ webkitdirectory: '' } as React.InputHTMLAttributes<HTMLInputElement>} multiple style={{ display: 'none' }} onChange={handleDirSelect} />
              </div>

              {files.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>
                      已选择 <strong style={{ color: 'var(--text-primary)' }}>{supportedCount}</strong> 个支持格式的文件
                      {files.length > supportedCount && (
                        <span style={{ color: 'var(--text-tertiary)', marginLeft: 4 }}>(共 {files.length} 个，已过滤不支持的格式)</span>
                      )}
                    </span>
                    <button
                      onClick={clearAll}
                      style={{ background: 'none', border: 'none', color: 'var(--accent-red)', cursor: 'pointer', fontSize: 11 }}
                    >
                      清空
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 220, overflow: 'auto' }}>
                    {files.filter(f => isSupported(f.name)).map((f, i) => (
                      <div key={i} style={fileRowStyle(true)}>
                        <i className="fa-regular fa-file" style={{ color: 'var(--accent-green)', fontSize: 13 }} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.webkitRelativePath || f.name}</span>
                        <span style={{ color: 'var(--text-tertiary)', fontSize: 11, whiteSpace: 'nowrap' }}>{(f.size / 1024).toFixed(1)} KB</span>
                        <button
                          onClick={() => removeFile(files.indexOf(f))}
                          style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 12, padding: '2px 4px' }}
                        >
                          <i className="fa-solid fa-xmark" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={footerStyle}>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
            {activeTab === 'file' && files.length > 0 && `已选择 ${files.length} 个文件`}
            {activeTab === 'directory' && files.length > 0 && `已选择 ${supportedCount} 个文件`}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} style={cancelBtnStyle}>取消</button>
            <button onClick={handleSubmit} disabled={!canSubmit || uploading} style={submitBtnStyle(canSubmit && !uploading)}>
              {uploading ? '添加中...' : '添加'}
            </button>
          </div>
        </div>
      </div>

      <NoteEditorDialog open={noteEditorOpen} onClose={() => { setNoteEditorOpen(false); onClose(); }} />
      {renderInfoDialog()}
    </div>,
    document.body
  );
}
