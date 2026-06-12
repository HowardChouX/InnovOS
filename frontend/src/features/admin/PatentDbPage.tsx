import { useState, useEffect, useCallback, useRef } from 'react';

interface Patent {
  id: string;
  title: string;
  abstract: string;
  applicants: string[];
  inventors: string[];
  filingDate: string;
  publicationDate: string;
  patentNumber: string;
  publicationNumber: string;
  priorityNumber: string;
  ipcCodes: string[];
  claims: string;
  description: string;
  created_at: string;
}

const EMPTY_PATENT: Patent = {
  id: '', title: '', abstract: '', applicants: [], inventors: [],
  filingDate: '', publicationDate: '', patentNumber: '',
  publicationNumber: '', priorityNumber: '', ipcCodes: [],
  claims: '', description: '', created_at: '',
};

async function api<T = unknown>(url: string, opts?: RequestInit): Promise<T> {
  const token = localStorage.getItem('token');
  const res = await fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts?.headers },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function PatentDbPage() {
  const [patents, setPatents] = useState<Patent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Patent | null>(null);
  const [form, setForm] = useState<Patent>({ ...EMPTY_PATENT });
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMode, setUploadMode] = useState<'pdfminer' | 'paddleocr' | 'deepseek'>('pdfminer');
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchPatents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: Patent[]; total: number }>(
        `/api/admin/patents?page=${page}&page_size=20&q=${encodeURIComponent(search)}`,
      );
      setPatents(res.data);
      setTotal(res.total);
    } catch { /* silent */ }
    setLoading(false);
  }, [page, search]);

  useEffect(() => { fetchPatents(); }, [fetchPatents]);

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) { const t = setTimeout(() => setToast(null), 4000); return () => clearTimeout(t); }
  }, [toast]);

  const openCreate = () => { setEditing(null); setForm({ ...EMPTY_PATENT }); setShowForm(true); };

  const openEdit = (p: Patent) => { setEditing(p); setForm({ ...p }); setShowForm(true); };

  const save = async () => {
    try {
      if (editing) {
        await api(`/api/admin/patents/${editing.id}`, { method: 'PUT', body: JSON.stringify(form) });
      } else {
        await api('/api/admin/patents', { method: 'POST', body: JSON.stringify(form) });
      }
      setShowForm(false);
      fetchPatents();
    } catch (e) { alert('保存失败: ' + e); }
  };

  const confirmDelete = async (id: string) => {
    try {
      await api(`/api/admin/patents/${id}`, { method: 'DELETE' });
      setDeleteId(null);
      fetchPatents();
    } catch { /* silent */ }
  };

  const handleArrayField = (field: 'applicants' | 'inventors' | 'ipcCodes', val: string) => {
    setForm((f) => ({ ...f, [field]: val.split('\n').map((s) => s.trim()).filter(Boolean) }));
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append('file', file);
      formData.append('mode', uploadMode);
      const res = await fetch('/api/admin/patents/upload', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
      if (!res.ok) {
        const errText = await res.text().catch(() => '无法读取错误信息');
        throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
      }
      await res.json();
      fetchPatents();
      setToast({ msg: '上传并提取成功', type: 'success' });
    } catch (e: any) {
      setToast({ msg: '上传失败: ' + (e?.message || e), type: 'error' });
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const modeLabel = { pdfminer: '快速提取', paddleocr: 'PaddleOCR', deepseek: 'DeepSeek-OCR' } as const;

  const pageTotal = Math.ceil(total / 20);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, height: '100%' }}>
      {/* Toast */}
      {toast && (
        <div style={{
          padding: '10px 16px', borderRadius: 8, fontSize: 13,
          background: toast.type === 'error' ? 'rgba(248,113,113,0.15)' : 'rgba(74,222,128,0.15)',
          border: `1px solid ${toast.type === 'error' ? 'rgba(248,113,113,0.3)' : 'rgba(74,222,128,0.3)'}`,
          color: toast.type === 'error' ? 'var(--accent-red)' : 'var(--accent-green)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <i className={`fa-solid ${toast.type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'}`} />
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>专利数据库管理</div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>共 {total} 条专利记录</div>
        </div>
        <button onClick={openCreate} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 13,
          background: 'var(--accent)', color: '#fff', border: 'none', cursor: 'pointer',
          fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <i className="fa-solid fa-plus" /> 添加专利
        </button>
      </div>

      {/* Upload */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input ref={fileRef} type="file" accept=".pdf" onChange={handleUpload} style={{ display: 'none' }} />
        <button onClick={() => fileRef.current?.click()} disabled={uploading}
          style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, border: '1px solid var(--border)',
            background: 'var(--bg-card)', color: 'var(--text-primary)', cursor: 'pointer', fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', gap: 6, opacity: uploading ? 0.5 : 1 }}>
          <i className="fa-solid fa-upload" />
          {uploading ? '处理中...' : '上传 PDF'}
        </button>
        {['pdfminer', 'paddleocr', 'deepseek'].map((m) => (
          <button key={m} onClick={() => setUploadMode(m as typeof uploadMode)}
            style={{ padding: '6px 12px', borderRadius: 6, fontSize: 11, border: '1px solid var(--border)',
              background: uploadMode === m ? 'var(--accent)' : 'transparent',
              color: uploadMode === m ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer', fontFamily: 'inherit' }}>
            {modeLabel[m as keyof typeof modeLabel]}
          </button>
        ))}
        {uploading && (
          <span style={{ fontSize: 12, color: 'var(--accent-blue)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <i className="fa-solid fa-circle-notch fa-spin" /> 正在处理，耗时较长请等待...
          </span>
        )}
      </div>

      {/* Search */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="搜索专利名称、专利号、申请人..."
          style={{
            flex: 1, padding: '8px 12px', borderRadius: 8, fontSize: 13,
            background: 'var(--bg-card)', border: '1px solid var(--border)',
            color: 'var(--text-primary)', fontFamily: 'inherit',
          }} />
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto', background: 'var(--bg-card)', borderRadius: 10, border: '1px solid var(--border)' }}>
        {patents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)', fontSize: 13 }}>
            <i className="fa-solid fa-database" style={{ fontSize: 28, marginBottom: 10, opacity: 0.3, display: 'block' }} />
            {search ? '未找到匹配专利' : '暂无专利数据，点击右上角添加'}
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--bg-panel)', color: 'var(--text-secondary)', fontWeight: 600 }}>
                <th style={{ padding: '10px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>专利名称</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>专利号</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>申请人</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>申请日</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>IPC</th>
                <th style={{ padding: '10px 12px', width: 80, textAlign: 'center', borderBottom: '1px solid var(--border)' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {patents.map((p) => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--border-light)', transition: 'background 0.1s' }}
                  onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-panel)'}
                  onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ padding: '10px 12px', color: 'var(--text-primary)', fontWeight: 500 }}>{p.title}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>{p.patentNumber || '-'}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-secondary)', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.applicants?.join('; ') || '-'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>{p.filingDate || '-'}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-secondary)', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.ipcCodes?.join('; ') || '-'}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                    <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                      <button onClick={() => openEdit(p)} title="编辑"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-blue)', fontSize: 12, fontFamily: 'inherit', padding: '2px 6px' }}>
                        <i className="fa-solid fa-pen" />
                      </button>
                      {deleteId === p.id ? (
                        <button onClick={() => confirmDelete(p.id)}
                          style={{ background: 'var(--accent-red)', border: 'none', cursor: 'pointer', color: '#fff', fontSize: 11, fontFamily: 'inherit', padding: '2px 8px', borderRadius: 4 }}>
                          确认?
                        </button>
                      ) : (
                        <button onClick={() => setDeleteId(p.id)} title="删除"
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-red)', fontSize: 12, fontFamily: 'inherit', padding: '2px 6px' }}>
                          <i className="fa-solid fa-trash-can" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {pageTotal > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
            style={{ padding: '6px 12px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: page > 1 ? 'pointer' : 'default', fontFamily: 'inherit' }}>
            <i className="fa-solid fa-chevron-left" />
          </button>
          {Array.from({ length: Math.min(pageTotal, 7) }, (_, i) => {
            const start = Math.max(1, Math.min(page - 3, pageTotal - 6));
            const n = start + i;
            if (n > pageTotal) return null;
            return (
              <button key={n} onClick={() => setPage(n)}
                style={{
                  padding: '6px 12px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)',
                  background: n === page ? 'var(--accent)' : 'var(--bg-card)',
                  color: n === page ? '#fff' : 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
                }}>
                {n}
              </button>
            );
          })}
          <button disabled={page >= pageTotal} onClick={() => setPage((p) => p + 1)}
            style={{ padding: '6px 12px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: page < pageTotal ? 'pointer' : 'default', fontFamily: 'inherit' }}>
            <i className="fa-solid fa-chevron-right" />
          </button>
        </div>
      )}

      {/* Add/Edit Dialog */}
      {showForm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}
          onClick={() => setShowForm(false)}>
          <div style={{ background: 'var(--bg-card)', borderRadius: 12, padding: 24, border: '1px solid var(--border)', width: 640, maxWidth: '90vw', maxHeight: '85vh', overflowY: 'auto' }}
            onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                {editing ? '编辑专利' : '添加专利'}
              </span>
              <button onClick={() => setShowForm(false)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 16, fontFamily: 'inherit' }}>
                <i className="fa-solid fa-xmark" />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <FormField label="发明名称" required>
                <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  style={inputStyle} placeholder="专利名称" />
              </FormField>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <FormField label="申请号">
                  <input value={form.patentNumber} onChange={(e) => setForm((f) => ({ ...f, patentNumber: e.target.value }))} style={inputStyle} placeholder="CN2024xxxxxx" />
                </FormField>
                <FormField label="申请日">
                  <input value={form.filingDate} onChange={(e) => setForm((f) => ({ ...f, filingDate: e.target.value }))} style={inputStyle} placeholder="2024-01-01" />
                </FormField>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <FormField label="公开（公告）号">
                  <input value={form.publicationNumber} onChange={(e) => setForm((f) => ({ ...f, publicationNumber: e.target.value }))} style={inputStyle} placeholder="CN122158040A" />
                </FormField>
                <FormField label="公开（公告）日">
                  <input value={form.publicationDate} onChange={(e) => setForm((f) => ({ ...f, publicationDate: e.target.value }))} style={inputStyle} placeholder="2024-06-01" />
                </FormField>
              </div>

              <FormField label="IPC分类号">
                <input value={form.ipcCodes.join('; ')} onChange={(e) => setForm((f) => ({ ...f, ipcCodes: e.target.value.split(';').map((s) => s.trim()).filter(Boolean) }))}
                  style={inputStyle} placeholder="G06F17/30; G06F16/00" />
              </FormField>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <FormField label="申请人">
                  <textarea rows={2} value={form.applicants.join('\n')} onChange={(e) => handleArrayField('applicants', e.target.value)}
                    style={{ ...inputStyle, resize: 'vertical' }} placeholder="每行一个" />
                </FormField>
                <FormField label="发明人">
                  <textarea rows={2} value={form.inventors.join('\n')} onChange={(e) => handleArrayField('inventors', e.target.value)}
                    style={{ ...inputStyle, resize: 'vertical' }} placeholder="每行一个" />
                </FormField>
              </div>

              <FormField label="优先权号">
                <input value={form.priorityNumber} onChange={(e) => setForm((f) => ({ ...f, priorityNumber: e.target.value }))} style={inputStyle} placeholder="优先权号" />
              </FormField>

              <FormField label="摘要">
                <textarea rows={3} value={form.abstract} onChange={(e) => setForm((f) => ({ ...f, abstract: e.target.value }))}
                  style={{ ...inputStyle, resize: 'vertical' }} placeholder="摘要内容" />
              </FormField>

              <FormField label="权利要求">
                <textarea rows={4} value={form.claims} onChange={(e) => setForm((f) => ({ ...f, claims: e.target.value }))}
                  style={{ ...inputStyle, resize: 'vertical', fontFamily: 'monospace' }} placeholder="权利要求书内容" />
              </FormField>

              <FormField label="说明书">
                <textarea rows={4} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  style={{ ...inputStyle, resize: 'vertical', fontFamily: 'monospace' }} placeholder="说明书内容" />
              </FormField>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
              <button onClick={() => setShowForm(false)}
                style={{ padding: '8px 20px', borderRadius: 8, fontSize: 13, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>
                取消
              </button>
              <button onClick={save} disabled={!form.title}
                style={{ padding: '8px 20px', borderRadius: 8, fontSize: 13, background: 'var(--accent)', color: '#fff', border: 'none', cursor: form.title ? 'pointer' : 'default', fontFamily: 'inherit', opacity: form.title ? 1 : 0.5 }}>
                {editing ? '保存' : '添加'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FormField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
        {label}{required && <span style={{ color: 'var(--accent-red)' }}> *</span>}
      </span>
      {children}
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '7px 10px', borderRadius: 6, fontSize: 12,
  background: 'var(--bg-panel)', border: '1px solid var(--border)',
  color: 'var(--text-primary)', fontFamily: 'inherit', outline: 'none',
  width: '100%', boxSizing: 'border-box',
};
