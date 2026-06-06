import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { keysApi } from '../../api/keys';
import type { ApiKey } from '../../api/keys';
import { GlassPanel } from '../../components/ui/GlassPanel';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { InlineConfirmModal } from '../../components/ui/InlineConfirmModal';

interface ModelInfo {
  id: string;
  owned_by?: string;
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', borderRadius: 6,
  background: 'var(--bg-card)', border: '1px solid var(--border)',
  color: 'var(--text-primary)', fontSize: 13, fontFamily: 'inherit',
};

export function KeyManagementPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [newKey, setNewKey] = useState({
    keyName: '',
    apiKey: '',
    apiBaseUrl: '',
    apiModel: '',
    priority: 0,
    maxRpm: 60,
  });
  const [toast, setToast] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
  const [confirmModal, setConfirmModal] = useState<{ open: boolean; title: string; message: string; onConfirm: () => void }>({ open: false, title: '', message: '', onConfirm: () => {} });

  const loadKeys = async () => {
    setLoading(true);
    try {
      const data = await keysApi.list();
      setKeys(data);
    } catch {
      console.error('加载Key列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadKeys();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);



  const fetchModels = async () => {
    if (!newKey.apiKey || !newKey.apiBaseUrl) {
      setToast({ msg: '请先填写 API Key 和 API Base URL', type: 'error' });
      return;
    }
    setModelsLoading(true);
    try {
      const baseUrl = newKey.apiBaseUrl.replace(/\/+$/, '');
      const res = await fetch(`${baseUrl}/v1/models`, {
        headers: { 'Authorization': `Bearer ${newKey.apiKey}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list: ModelInfo[] = data.data || data.models || [];
      setModels(list);
      setSelectedModels([]);
      setNewKey({ ...newKey, apiModel: '' });
    } catch (e) {
      setToast({ msg: `获取模型列表失败: ${e instanceof Error ? e.message : '未知错误'}`, type: 'error' });
      setModels([]);
    } finally {
      setModelsLoading(false);
    }
  };

  const toggleModel = (modelId: string) => {
    let updated: string[];
    if (selectedModels.includes(modelId)) {
      updated = selectedModels.filter((m) => m !== modelId);
    } else {
      updated = [...selectedModels, modelId];
    }
    setSelectedModels(updated);
    setNewKey({ ...newKey, apiModel: updated.join(',') });
  };

  const selectAllModels = () => {
    const all = models.map((m) => m.id);
    setSelectedModels(all);
    setNewKey({ ...newKey, apiModel: all.join(',') });
  };

  const [createError, setCreateError] = useState('');
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    setCreating(true);
    setCreateError('');
    try {
      await keysApi.create(newKey);
      setShowCreate(false);
      setNewKey({ keyName: '', apiKey: '', apiBaseUrl: '', apiModel: '', priority: 0, maxRpm: 60 });
      setModels([]);
      setSelectedModels([]);
      loadKeys();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : '创建失败');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = (id: number) => {
    setConfirmModal({
      open: true,
      title: '确认删除',
      message: '确认删除该 API Key？',
      onConfirm: async () => {
        setConfirmModal(prev => ({ ...prev, open: false }));
        try {
          await keysApi.delete(id);
          loadKeys();
        } catch (e) {
          console.error('删除失败:', e);
          setToast({ msg: '删除失败', type: 'error' });
        }
      },
    });
  };

  const handleTest = async (id: number) => {
    try {
      const result = await keysApi.test(id);
      setToast({ msg: result.message, type: 'success' });
    } catch {
      setToast({ msg: '测试失败', type: 'error' });
    }
  };

  const handleToggleActive = async (key: ApiKey) => {
    try {
      await keysApi.update(key.id, { ...key, isActive: !key.isActive });
      loadKeys();
    } catch (e) {
      console.error('更新失败:', e);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <GlassPanel style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <div className="card-title" style={{ justifyContent: 'space-between' }}>
          API Key 管理
          <button
            onClick={() => { setShowCreate(true); setModels([]); setSelectedModels([]); }}
            className="btn-primary"
            style={{ fontSize: 12, padding: '6px 12px' }}
          >
            + 添加 Key
          </button>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <LoadingSpinner />
          </div>
        ) : keys.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
            暂无API Key，请添加
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)' }}>名称</th>
                  <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)' }}>Key</th>
                  <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)' }}>模型</th>
                  <th style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-secondary)' }}>优先级</th>
                  <th style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-secondary)' }}>RPM</th>
                  <th style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-secondary)' }}>状态</th>
                  <th style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-secondary)' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr key={key.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                    <td style={{ padding: '8px 12px', fontWeight: 500 }}>{key.keyName}</td>
                    <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontSize: 11 }}>{key.apiKey}</td>
                    <td style={{ padding: '8px 12px' }}>{key.apiModel}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'center' }}>{key.priority}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                      <span style={key.currentRpm >= key.maxRpm ? { color: 'var(--accent-red)' } : {}}>
                        {key.currentRpm}/{key.maxRpm}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                      <span
                        onClick={() => handleToggleActive(key)}
                        style={{
                          padding: '2px 8px', borderRadius: 4, cursor: 'pointer',
                          background: key.isActive ? 'rgba(74,222,128,0.1)' : 'rgba(248,113,113,0.1)',
                          color: key.isActive ? 'var(--accent-green)' : 'var(--accent-red)',
                          fontSize: 11,
                        }}
                      >
                        {key.isActive ? '启用' : '禁用'}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                      <button
                        onClick={() => handleTest(key.id)}
                        style={{
                          marginRight: 6, padding: '4px 8px', borderRadius: 4,
                          background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                          color: 'var(--accent-blue)', cursor: 'pointer', fontSize: 11,
                        }}
                      >
                        测试
                      </button>
                      <button
                        onClick={() => handleDelete(key.id)}
                        style={{
                          padding: '4px 8px', borderRadius: 4,
                          background: 'rgba(248,113,113,0.1)',
                          border: '1px solid rgba(248,113,113,0.2)',
                          color: 'var(--accent-red)',
                          cursor: 'pointer', fontSize: 11,
                          transition: 'all 0.15s',
                        }}
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassPanel>

      {showCreate && createPortal(
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999,
        }}>
          <div className="card" style={{ width: 460, maxHeight: '85vh', overflow: 'auto' }}>
            <div className="card-title">添加 API Key</div>

            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                名称
              </label>
              <input
                value={newKey.keyName}
                onChange={(e) => setNewKey({ ...newKey, keyName: e.target.value })}
                placeholder="如：DeepSeek-1"
                style={inputStyle}
              />
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                API Key
              </label>
              <input
                type="password"
                value={newKey.apiKey}
                onChange={(e) => setNewKey({ ...newKey, apiKey: e.target.value })}
                placeholder="sk-xxxxxxxxxxxxxxxx"
                style={inputStyle}
              />
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                API Base URL
              </label>
              <input
                value={newKey.apiBaseUrl}
                onChange={(e) => setNewKey({ ...newKey, apiBaseUrl: e.target.value })}
                placeholder="https://api.deepseek.com"
                style={inputStyle}
              />
            </div>

            <div style={{ marginBottom: 12 }}>
              <button
                onClick={fetchModels}
                disabled={!newKey.apiKey || !newKey.apiBaseUrl || modelsLoading}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px',
                  borderRadius: 6, fontSize: 12, cursor: 'pointer',
                  background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)',
                  color: 'var(--accent-blue)', fontFamily: 'inherit',
                  opacity: (!newKey.apiKey || !newKey.apiBaseUrl || modelsLoading) ? 0.5 : 1,
                }}
              >
                {modelsLoading ? (
                  <><LoadingSpinner /> 获取中...</>
                ) : (
                  <><i className="fa-solid fa-download" style={{ fontSize: 11 }} /> 获取模型列表</>
                )}
              </button>
            </div>

            {models.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <label style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    选择模型 <span style={{ color: 'var(--accent-blue)' }}>({selectedModels.length}/{models.length})</span>
                  </label>
                  <span
                    onClick={selectAllModels}
                    style={{ fontSize: 11, color: 'var(--accent-blue)', cursor: 'pointer' }}
                  >
                    全选
                  </span>
                </div>
                <div style={{
                  border: '1px solid var(--border)', borderRadius: 6, maxHeight: 180, overflowY: 'auto',
                }}>
                  {models.map((m) => (
                    <div
                      key={m.id}
                      onClick={() => toggleModel(m.id)}
                      style={{
                        padding: '7px 12px', fontSize: 12, cursor: 'pointer',
                        background: selectedModels.includes(m.id) ? 'rgba(59,130,246,0.1)' : 'transparent',
                        borderBottom: '1px solid var(--border-light)',
                        display: 'flex', alignItems: 'center', gap: 8,
                        color: selectedModels.includes(m.id) ? 'var(--accent-blue)' : 'var(--text-primary)',
                      }}
                    >
                      <span style={{
                        width: 14, height: 14, borderRadius: 3, flexShrink: 0,
                        border: `1px solid ${selectedModels.includes(m.id) ? 'var(--accent-blue)' : 'var(--border)'}`,
                        background: selectedModels.includes(m.id) ? 'var(--accent-blue)' : 'transparent',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        {selectedModels.includes(m.id) && (
                          <i className="fa-solid fa-check" style={{ fontSize: 8, color: '#fff' }} />
                        )}
                      </span>
                      <span style={{ fontFamily: 'monospace' }}>{m.id}</span>
                      {m.owned_by && (
                        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-tertiary)' }}>{m.owned_by}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
              <div style={{ width: 80 }}>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  优先级
                </label>
                <input
                  type="number"
                  value={newKey.priority}
                  onChange={(e) => setNewKey({ ...newKey, priority: Number(e.target.value) })}
                  style={inputStyle}
                />
              </div>
              <div style={{ width: 80 }}>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                  RPM
                </label>
                <input
                  type="number"
                  value={newKey.maxRpm}
                  onChange={(e) => setNewKey({ ...newKey, maxRpm: Number(e.target.value) })}
                  style={inputStyle}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
              {createError && (
                <div style={{
                  flex: 1, padding: '6px 10px', borderRadius: 6, fontSize: 12,
                  background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)',
                  color: 'var(--accent-red)',
                }}>
                  {createError}
                </div>
              )}
              <button
                onClick={() => setShowCreate(false)}
                style={{ padding: '8px 16px', borderRadius: 6, background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: 13, cursor: 'pointer' }}
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newKey.keyName || !newKey.apiKey || !newKey.apiBaseUrl || selectedModels.length === 0}
                className="btn-primary"
                style={{ opacity: (creating || !newKey.keyName || !newKey.apiKey || !newKey.apiBaseUrl || selectedModels.length === 0) ? 0.5 : 1 }}
              >
                {creating ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
      <InlineConfirmModal
        open={confirmModal.open}
        title={confirmModal.title}
        message={confirmModal.message}
        onConfirm={confirmModal.onConfirm}
        onCancel={() => setConfirmModal(prev => ({ ...prev, open: false }))}
      />
    </div>
  );
}
