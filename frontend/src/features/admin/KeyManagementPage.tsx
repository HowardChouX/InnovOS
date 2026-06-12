import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { providersApi, getModelId, type Provider, type ModelEntry } from '../../api/admin/providers';
import { settingsApi, type AvailableModel, type AvailableModelsByCapability } from '../../api/admin/settings';
import { InlineConfirmModal } from '../../components/ui/InlineConfirmModal';
import { ModelSelector } from '../../components/ui/ModelSelector';
import { ModelEditDrawer } from '../../components/ui/ModelEditDrawer';


const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', borderRadius: 6,
  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
  color: 'var(--text-primary)', fontSize: 13, fontFamily: 'inherit', outline: 'none',
};

const labelStyle: React.CSSProperties = {
  fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4,
};

export function KeyManagementPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
  const [checking, setChecking] = useState(false);
  const [showCheckModelPicker, setShowCheckModelPicker] = useState(false);
  const [_checkModel] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [editKey, setEditKey] = useState('');
  const [editModels, setEditModels] = useState<string[]>([]);
  const [editMaxRpm, setEditMaxRpm] = useState(60);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [detectedModels, setDetectedModels] = useState<ModelEntry[]>([]);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [editDrawerModel, setEditDrawerModel] = useState<ModelEntry | null>(null);
  const [batchChecking, setBatchChecking] = useState(false);
  const [batchResults, setBatchResults] = useState<Array<{ modelId: string; status: string; latency?: number; error?: string | null }> | null>(null);

  // ─── 全局模型分配 ───
  const [availableModels, setAvailableModels] = useState<AvailableModelsByCapability | null>(null);
  const [assignedModels, setAssignedModels] = useState<{ chat: string; embedding: string; rerank: string; vision: string }>({ chat: '', embedding: '', rerank: '', vision: '' });
  const [savingAssignment, setSavingAssignment] = useState(false);

  /** 从 provider.models 中查找对应 model ID 的完整条目 */
  function getModelEntry(provider: Provider | undefined, modelId: string): ModelEntry | null {
    if (!provider) return null;
    for (const m of provider.models || []) {
      if (getModelId(m) === modelId) return typeof m === 'object' ? m : { id: m };
    }
    return { id: modelId };
  }

  const load = async () => {
    setLoading(true);
    try {
      const res = await providersApi.listBuiltin();
      setProviders(res.data);
      if (!selectedId && res.data.length > 0) {
        const first = res.data.find(p => p.isConfigured) || res.data[0];
        setSelectedId(first.providerId);
      }
    } catch { /* */ } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 3000); return () => clearTimeout(t); } }, [toast]);

  // 加载模型分配数据
  useEffect(() => {
    settingsApi.getAvailable().then(r => setAvailableModels(r.data)).catch(() => {});
    settingsApi.getAssigned().then(r => {
      const a = r.data;
      setAssignedModels({
        chat: a.chat_model || '',
        embedding: a.embedding_model || '',
        rerank: a.rerank_model || '',
        vision: a.ocr_model || '',
      });
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const p = providers.find(x => x.providerId === selectedId);
    if (p) {
      setEditKey('');
      // models 可能为 string[]（旧）或 ModelEntry[]（新），统一提取 ID
      setEditModels((p.models || []).map(getModelId));
      setEditMaxRpm(60);
      setDetectedModels([]);
    }
  }, [selectedId, providers]);

  const selected = providers.find(x => x.providerId === selectedId);

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const data: any = { max_rpm: editMaxRpm, models: editModels };
      if (editKey) data.api_key = editKey;
      if (selected.isConfigured) {
        await providersApi.update(selected.providerId, data);
      } else {
        await providersApi.add({ provider_id: selected.providerId, name: selected.name, api_host: selected.apiHost, ...data });
      }
      setToast({ msg: '保存成功', type: 'success' });
      await load();
    } catch (e) { setToast({ msg: e instanceof Error ? e.message : '保存失败', type: 'error' }); }
    finally { setSaving(false); }
  };

  const handleCheck = (model?: string) => {
    if (!selected) return;
    setShowCheckModelPicker(false);
    setChecking(true);
    const testModel = model || (editModels.length > 0 ? editModels[0] : '');
    if (!testModel) { setShowCheckModelPicker(true); setChecking(false); return; }
    providersApi.check(selected.providerId, testModel).then(r => {
      setToast(r.data.status === 'ok'
        ? { msg: `${testModel} ✅ ${r.data.latency_ms}ms`, type: 'success' }
        : { msg: r.data.message || `${testModel} ❌ 连接失败`, type: 'error' });
    }).catch(() => setToast({ msg: `${testModel} ❌ 连接失败`, type: 'error' }))
    .finally(() => setChecking(false));
  };

  const handleCheckClick = () => {
    if (!selected) return;
    if (editModels.length === 0) { setShowCheckModelPicker(true); return; }
    if (editModels.length === 1) { handleCheck(editModels[0]); return; }
    setShowCheckModelPicker(true);
  };

  const handleToggle = async () => {
    if (!selected) return;
    try { await providersApi.update(selected.providerId, { is_enabled: !selected.isEnabled }); await load(); } catch { /* */ }
  };

  const handleDelete = async () => {
    if (!selected) return;
    setConfirmDelete(false);
    try { await providersApi.delete(selected.providerId); setSelectedId(null); await load(); }
    catch { setToast({ msg: '删除失败', type: 'error' }); }
  };

  const handleDetectModels = async () => {
    if (!selected) return;
    setDetecting(true);
    setDetectedModels([]);
    try {
      const res = await providersApi.detectModels(selected.providerId, editKey || undefined);
      const models = res.data?.models || [];
      setDetectedModels(models);
      if (models.length > 0) setShowModelSelector(true);
      else setToast({ msg: '未检测到模型', type: 'error' });
    } catch { setToast({ msg: '检测失败', type: 'error' }); }
    finally { setDetecting(false); }
  };

  const handleBatchCheck = async () => {
    if (!selected || editModels.length === 0) return;
    setBatchChecking(true);
    setBatchResults(null);
    try {
      const res = await providersApi.batchCheckModels(selected.providerId, editModels);
      setBatchResults(res.data.models);
      const failed = res.data.models.filter(m => m.status !== 'ok');
      if (failed.length === 0) setToast({ msg: `全部 ${res.data.models.length} 个模型检查通过 ✅`, type: 'success' });
      else setToast({ msg: `${failed.length}/${res.data.models.length} 个模型连接失败`, type: 'error' });
    } catch { setToast({ msg: '批量检查失败', type: 'error' }); }
    finally { setBatchChecking(false); }
  };

  const handleModelsConfirm = (models: string[]) => {
    setEditModels(models);
    setShowModelSelector(false);
    setToast({ msg: `已选择 ${models.length} 个模型`, type: 'success' });
  };

  const handleSaveAssignment = async () => {
    setSavingAssignment(true);
    try {
      await settingsApi.setAssigned({
        chat_model: assignedModels.chat || null,
        embedding_model: assignedModels.embedding || null,
        rerank_model: assignedModels.rerank || null,
        ocr_model: assignedModels.vision || null,
      });
      setToast({ msg: '模型分配已保存', type: 'success' });
    } catch { setToast({ msg: '保存模型分配失败', type: 'error' }); }
    finally { setSavingAssignment(false); }
  };

  const [newP, setNewP] = useState({ provider_id: '', name: '', api_host: '', api_key: '' });
  const [adding, setAdding] = useState(false);
  const handleAdd = async () => {
    setAdding(true);
    try {
      await providersApi.add({ ...newP, api_model: '', priority: 0, max_rpm: 60 });
      setShowAdd(false); setNewP({ provider_id: '', name: '', api_host: '', api_key: '' }); await load();
    } catch (e) { setToast({ msg: e instanceof Error ? e.message : '添加失败', type: 'error' }); }
    finally { setAdding(false); }
  };

  return (
    <div style={{ display: 'flex', flex: 1, minHeight: 0, gap: 0, height: '100%' }}>
      {/* Left Sidebar */}
      <div style={{ width: 260, flexShrink: 0, background: 'var(--bg-panel)', borderRight: '1px solid var(--border-light)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>模型服务</span>
          <button onClick={() => setShowAdd(true)} style={{ width: 24, height: 24, borderRadius: 6, background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: 'var(--accent-blue)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>+</button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '6px 0' }}>
          {providers.map(p => {
            const active = p.providerId === selectedId;
            return (
              <div key={p.providerId} onClick={() => setSelectedId(p.providerId)} style={{
                padding: '9px 14px', cursor: 'pointer',
                background: active ? 'rgba(59,130,246,0.12)' : 'transparent',
                borderLeft: active ? '3px solid var(--accent-blue)' : '3px solid transparent',
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                <div style={{ width: 28, height: 28, borderRadius: 6, background: p.isConfigured ? 'rgba(74,222,128,0.12)' : 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: p.isConfigured ? 'var(--accent-green)' : 'var(--text-tertiary)' }}>{p.name[0]}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: active ? 600 : 400, color: active ? 'var(--text-primary)' : 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 1 }}>{p.isConfigured ? (p.apiKeyMasked || '已配置') : '未配置'}{p.models?.length > 0 ? ` · ${p.models.length}个模型` : ''}</div>
                </div>
                {p.isConfigured && !p.isEnabled && <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(248,113,113,0.15)', color: 'var(--accent-red)' }}>禁用</span>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Panel */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
        {!selected ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-tertiary)', fontSize: 13 }}>选择一个供应商进行配置</div>
        ) : (
          <div style={{ maxWidth: 520 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: selected.isConfigured ? 'rgba(74,222,128,0.12)' : 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 700, color: selected.isConfigured ? 'var(--accent-green)' : 'var(--text-tertiary)' }}>{selected.name[0]}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>{selected.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{selected.apiHost}</div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {selected.isConfigured && (
                  <button onClick={handleCheckClick} disabled={checking} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', color: 'var(--accent-blue)', cursor: 'pointer', fontFamily: 'inherit', opacity: checking ? 0.5 : 1 }}>{checking ? '检查中...' : '检查连接'}</button>
                )}
                {selected.isConfigured && editModels.length > 1 && (
                  <button onClick={handleBatchCheck} disabled={batchChecking} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: 'rgba(168,85,247,0.1)', border: '1px solid rgba(168,85,247,0.3)', color: 'var(--accent-purple)', cursor: 'pointer', fontFamily: 'inherit', opacity: batchChecking ? 0.5 : 1 }}>{batchChecking ? '检查中...' : '批量检查'}</button>
                )}
                <button onClick={handleToggle} style={{ padding: '6px 14px', borderRadius: 6, fontSize: 12, background: selected.isEnabled ? 'rgba(74,222,128,0.1)' : 'rgba(248,113,113,0.1)', border: `1px solid ${selected.isEnabled ? 'rgba(74,222,128,0.3)' : 'rgba(248,113,113,0.3)'}`, color: selected.isEnabled ? 'var(--accent-green)' : 'var(--accent-red)', cursor: 'pointer', fontFamily: 'inherit' }}>{selected.isEnabled ? '已启用' : '已禁用'}</button>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={labelStyle}>API Key</label>
                <input type="password" value={editKey} onChange={e => setEditKey(e.target.value)} placeholder={selected.hasApiKey ? '已设置（留空保持不变）' : '请输入 API Key'} style={inputStyle} />
                {selected.hasApiKey && <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>当前: {selected.apiKeyMasked}</div>}
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <label style={{ ...labelStyle, marginBottom: 0 }}>模型 ({editModels.length})</label>
                  <button onClick={handleDetectModels} disabled={detecting || !selected.isConfigured} style={{ padding: '3px 10px', borderRadius: 4, fontSize: 11, cursor: 'pointer', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', color: 'var(--accent-blue)', fontFamily: 'inherit', opacity: (detecting || !selected.isConfigured) ? 0.5 : 1 }}>{detecting ? '检测中...' : '模型检测'}</button>
                </div>
                {editModels.length > 0 ? (
                  <div style={{ padding: '8px 12px', borderRadius: 6, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', maxHeight: 200, overflowY: 'auto' }}>
                    {editModels.map(mId => {
                      const entry = getModelEntry(selected, mId);
                      const caps: string[] = (typeof entry === 'object' && entry?.capabilities) || [];
                      const capColor = (c: string) => {
                        const map: Record<string,string> = { embedding: 'rgba(74,222,128,0.2)', rerank: 'rgba(250,204,21,0.2)', reasoning: 'rgba(168,85,247,0.2)', 'function-call': 'rgba(236,72,153,0.2)', 'image-recognition': 'rgba(251,146,60,0.2)' };
                        return map[c] || 'rgba(255,255,255,0.06)';
                      };
                      const capLabel = (c: string) => ({ embedding:'嵌入', rerank:'重排', reasoning:'推理', 'function-call':'工具', 'image-recognition':'视觉' })[c] || c;
                      return (
                        <div key={mId} onClick={() => setEditDrawerModel(entry)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '5px 0', fontSize: 12, color: 'var(--text-primary)', borderBottom: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mId}</span>
                            {caps.filter(c => c !== 'chat').slice(0, 3).map(c => (
                              <span key={c} style={{ padding: '1px 5px', borderRadius: 3, fontSize: 9, background: capColor(c), color: 'var(--text-muted)', flexShrink: 0 }}>{capLabel(c)}</span>
                            ))}
                          </div>
                          <button onClick={e => { e.stopPropagation(); setEditModels(prev => prev.filter(x => x !== mId)); }} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 14, flexShrink: 0, marginLeft: 6 }}>×</button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div style={{ padding: '12px', borderRadius: 6, textAlign: 'center', background: 'rgba(0,0,0,0.1)', border: '1px dashed var(--border)', color: 'var(--text-tertiary)', fontSize: 12, cursor: 'pointer' }} onClick={handleDetectModels}>点击「模型检测」获取可用模型</div>
                )}
              </div>

              <div>
                <label style={labelStyle}>RPM 限制</label>
                <input type="number" value={editMaxRpm} onChange={e => setEditMaxRpm(Number(e.target.value))} style={inputStyle} />
              </div>

              <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                <button onClick={handleSave} disabled={saving} style={{ padding: '8px 24px', borderRadius: 6, fontSize: 13, fontWeight: 500, background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit', opacity: saving ? 0.5 : 1 }}>{saving ? '保存中...' : '保存'}</button>
                {selected.isConfigured && <button onClick={() => setConfirmDelete(true)} style={{ padding: '8px 18px', borderRadius: 6, fontSize: 13, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--accent-red)', cursor: 'pointer', fontFamily: 'inherit' }}>移除</button>}
              </div>
            </div>

            {/* ─── 全局模型分配 ──────── */}
            <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>全局模型分配</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {(['chat', 'embedding', 'rerank', 'vision'] as const).map(cap => {
                  const label = { chat: '对话模型（首页分析）', embedding: '嵌入模型（知识库）', rerank: '重排模型（知识库）', vision: 'OCR 模型（专利处理）' }[cap];
                  const list = availableModels?.[cap] || [];
                  return (
                    <div key={cap}>
                      <label style={labelStyle}>{label}</label>
                      <select value={assignedModels[cap]} onChange={e => setAssignedModels(p => ({ ...p, [cap]: e.target.value }))} style={{
                        ...inputStyle, appearance: 'auto', cursor: 'pointer',
                      }}>
                        <option value="">— 未分配 —</option>
                        {list.map(m => (
                          <option key={`${m.providerId}:${m.modelId}`} value={`${m.providerId}:${m.modelId}`}>
                            {m.providerId}/{m.modelId}
                          </option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>
              <button onClick={handleSaveAssignment} disabled={savingAssignment} style={{ marginTop: 10, padding: '7px 20px', borderRadius: 6, fontSize: 12, fontWeight: 500, background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit', opacity: savingAssignment ? 0.5 : 1 }}>
                {savingAssignment ? '保存中...' : '保存分配'}
              </button>
            </div>

            {/* ─── 全局 RAG 默认配置 ──────── */}
            <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>全局 RAG 默认配置</div>
              <RagGlobalConfig />
            </div>

            {(selected.website || selected.keyUrl) && (
              <div style={{ marginTop: 24, padding: '10px 14px', borderRadius: 8, background: 'rgba(0,0,0,0.1)', fontSize: 11, color: 'var(--text-tertiary)' }}>
                {selected.website && <span style={{ marginRight: 16 }}>官网: <a href={selected.website} target="_blank" rel="noopener" style={{ color: 'var(--accent-blue)' }}>{selected.website}</a></span>}
                {selected.keyUrl && <span>获取 Key: <a href={selected.keyUrl} target="_blank" rel="noopener" style={{ color: 'var(--accent-blue)' }}>{selected.keyUrl}</a></span>}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Add Custom Provider Modal */}
      {showAdd && createPortal(
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div style={{ background: 'var(--bg-card)', borderRadius: 12, padding: 24, border: '1px solid var(--border)', width: 420 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>添加自定义供应商</div>
            {[
              { label: 'ID', key: 'provider_id', placeholder: '如 my-api' },
              { label: '名称', key: 'name', placeholder: '如 My API' },
              { label: 'API Host', key: 'api_host', placeholder: 'https://api.example.com' },
              { label: 'API Key', key: 'api_key', placeholder: 'sk-xxx', type: 'password' },
            ].map(f => (
              <div key={f.key} style={{ marginBottom: 12 }}>
                <label style={labelStyle}>{f.label}</label>
                <input type={(f as any).type || 'text'} value={(newP as any)[f.key]} onChange={e => setNewP({ ...newP, [f.key]: e.target.value })} placeholder={f.placeholder} style={inputStyle} />
              </div>
            ))}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 16 }}>
              <button onClick={() => setShowAdd(false)} style={{ padding: '7px 16px', borderRadius: 6, fontSize: 13, background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>取消</button>
              <button onClick={handleAdd} disabled={adding || !newP.provider_id || !newP.name || !newP.api_host} style={{ padding: '7px 16px', borderRadius: 6, fontSize: 13, background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit', opacity: (adding || !newP.provider_id || !newP.name || !newP.api_host) ? 0.5 : 1 }}>{adding ? '添加中...' : '添加'}</button>
            </div>
          </div>
        </div>, document.body
      )}

      {/* Model Selector */}
      <ModelSelector open={showModelSelector} onClose={() => setShowModelSelector(false)} selectedModels={editModels} availableModels={detectedModels} onConfirm={handleModelsConfirm} title={`${selected?.name || ''} 模型`} />

      {/* Model Edit Drawer */}
      <ModelEditDrawer open={editDrawerModel !== null} onClose={() => setEditDrawerModel(null)} providerId={selected?.providerId || ''} model={editDrawerModel} onSave={() => load()} />

      {/* Batch Check Results */}
      {batchResults && createPortal(
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }} onClick={() => setBatchResults(null)}>
          <div onClick={e => e.stopPropagation()} style={{ background: 'var(--bg-card)', borderRadius: 12, padding: 20, border: '1px solid var(--border)', width: 520, maxWidth: '90vw', maxHeight: '80vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>批量检查结果</div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {batchResults.map(r => {
                const ok = r.status === 'ok';
                return (
                  <div key={r.modelId} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 6, marginBottom: 4, background: ok ? 'rgba(74,222,128,0.06)' : 'rgba(248,113,113,0.06)', border: `1px solid ${ok ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)'}` }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: ok ? 'var(--accent-green)' : 'var(--accent-red)' }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.modelId}</div>
                      {r.error && <div style={{ fontSize: 11, color: 'var(--accent-red)', marginTop: 2, wordBreak: 'break-word' }}>{r.error}</div>}
                    </div>
                    {r.latency != null && <span style={{ fontSize: 11, color: 'var(--text-tertiary)', flexShrink: 0, fontFamily: 'monospace' }}>{r.latency.toFixed(0)}ms</span>}
                  </div>
                );
              })}
            </div>
            <button onClick={() => setBatchResults(null)} style={{ marginTop: 12, padding: '7px 16px', borderRadius: 6, fontSize: 13, width: '100%', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>关闭</button>
          </div>
        </div>, document.body
      )}

      {/* Check Model Picker */}
      {showCheckModelPicker && createPortal(
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div style={{ background: 'var(--bg-card)', borderRadius: 12, padding: 24, border: '1px solid var(--border)', width: 400 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>选择一个模型进行测试</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 300, overflowY: 'auto', marginBottom: 16 }}>
              {(editModels.length > 0 ? editModels : (selected?.models || []).map(getModelId)).map(m => (
                <div key={m} onClick={() => handleCheck(m)} style={{ padding: '9px 12px', borderRadius: 6, cursor: 'pointer', background: 'transparent', border: '1px solid var(--border-light)', color: 'var(--text-primary)', fontSize: 13, fontFamily: 'monospace' }}>{m}</div>
              ))}
            </div>
            <button onClick={() => setShowCheckModelPicker(false)} style={{ padding: '7px 16px', borderRadius: 6, fontSize: 13, width: '100%', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>取消</button>
          </div>
        </div>, document.body
      )}

      <InlineConfirmModal open={confirmDelete} title="移除供应商" message={`确认移除 ${selected?.name}？`} onConfirm={handleDelete} onCancel={() => setConfirmDelete(false)} />



      {toast && (
        <div style={{ position: 'fixed', bottom: 20, right: 20, padding: '10px 16px', borderRadius: 8, fontSize: 13, zIndex: 9999, background: toast.type === 'success' ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)', border: `1px solid ${toast.type === 'success' ? 'rgba(74,222,128,0.3)' : 'rgba(248,113,113,0.3)'}`, color: toast.type === 'success' ? 'var(--accent-green)' : 'var(--accent-red)', backdropFilter: 'blur(10px)' }}>{toast.msg}</div>
      )}
    </div>
  );
}

// ─── 全局 RAG 默认配置（内联、非弹窗） ─────────────────

const ragFieldStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8,
};

const ragLabelStyle: React.CSSProperties = {
  fontSize: 12, color: 'var(--text-secondary)', minWidth: 100, flexShrink: 0,
};

const ragInputStyle: React.CSSProperties = {
  width: 120, padding: '6px 10px', borderRadius: 6,
  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
  color: 'var(--text-primary)', fontSize: 12, fontFamily: 'inherit', outline: 'none',
};

const ragSelectStyle: React.CSSProperties = {
  width: 200, padding: '6px 10px', borderRadius: 6,
  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
  color: 'var(--text-primary)', fontSize: 12, fontFamily: 'inherit',
  appearance: 'auto', cursor: 'pointer',
};

function RagGlobalConfig() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    import('../../api/admin/settings').then(({ settingsApi }) => {
      settingsApi.getRagConfig().then(res => {
        const v: Record<string, string> = {};
        const raw = res.data || {};
        for (const key of ['chunk_size', 'chunk_overlap', 'search_mode', 'hybrid_alpha',
                           'threshold', 'document_count', 'file_processor']) {
          v[key] = (raw as any)[key] ?? '';
        }
        setValues(v);
        setLoaded(true);
      });
    });
  }, []);

  const set = (key: string, val: string) => setValues(prev => ({ ...prev, [key]: val }));

  const handleSave = async () => {
    setSaving(true);
    try {
      const { settingsApi } = await import('../../api/admin/settings');
      const payload: Record<string, string | null> = {};
      for (const [key, val] of Object.entries(values)) {
        payload[key] = val || null;
      }
      await settingsApi.setRagConfig(payload as any);
    } finally {
      setSaving(false);
    }
  };

  if (!loaded) return <div style={{ fontSize: 12, color: 'var(--text-tertiary)', padding: 8 }}>加载中...</div>;

  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={ragFieldStyle}>
          <span style={ragLabelStyle}>分块大小</span>
          <input style={ragInputStyle} value={values.chunk_size ?? ''} onChange={e => set('chunk_size', e.target.value)} placeholder="1024" />
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>tokens</span>
        </div>
        <div style={ragFieldStyle}>
          <span style={ragLabelStyle}>重叠大小</span>
          <input style={ragInputStyle} value={values.chunk_overlap ?? ''} onChange={e => set('chunk_overlap', e.target.value)} placeholder="200" />
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>tokens</span>
        </div>
        <div style={ragFieldStyle}>
          <span style={ragLabelStyle}>搜索模式</span>
          <select style={ragSelectStyle} value={values.search_mode ?? ''} onChange={e => set('search_mode', e.target.value)}>
            <option value="">默认</option>
            <option value="hybrid">混合检索</option>
            <option value="vector">纯向量检索</option>
            <option value="bm25">关键词检索</option>
          </select>
        </div>
        <div style={ragFieldStyle}>
          <span style={ragLabelStyle}>混合权重</span>
          <input style={ragInputStyle} value={values.hybrid_alpha ?? ''} onChange={e => set('hybrid_alpha', e.target.value)} placeholder="0.3" />
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>0-1</span>
        </div>
        <div style={ragFieldStyle}>
          <span style={ragLabelStyle}>相关阈值</span>
          <input style={ragInputStyle} value={values.threshold ?? ''} onChange={e => set('threshold', e.target.value)} placeholder="0.0" />
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>0-1</span>
        </div>
        <div style={ragFieldStyle}>
          <span style={ragLabelStyle}>返回结果数</span>
          <input style={ragInputStyle} value={values.document_count ?? ''} onChange={e => set('document_count', e.target.value)} placeholder="10" />
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>条</span>
        </div>
        <div style={ragFieldStyle}>
          <span style={ragLabelStyle}>文件处理器</span>
          <select style={ragSelectStyle} value={values.file_processor ?? ''} onChange={e => set('file_processor', e.target.value)}>
            <option value="">默认</option>
            <option value="default">DefaultFileProcessor</option>
          </select>
        </div>
      </div>
      <button onClick={handleSave} disabled={saving} style={{ marginTop: 8, padding: '6px 20px', borderRadius: 6, fontSize: 12, fontWeight: 500, background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit', opacity: saving ? 0.5 : 1 }}>
        {saving ? '保存中...' : '保存 RAG 配置'}
      </button>
    </div>
  );
}
