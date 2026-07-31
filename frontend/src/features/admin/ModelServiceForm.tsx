import { useState } from 'react';
import { createPortal } from 'react-dom';
import { providersApi, type Provider } from '../../api/admin/providers';

interface ModelServiceFormProps {
  open: boolean;
  mode: 'add' | 'edit';
  initial?: Provider | null;
  onClose: () => void;
  onSave: () => void;
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  borderRadius: 6,
  background: 'rgba(0,0,0,0.2)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
  fontSize: 13,
  fontFamily: 'inherit',
  outline: 'none',
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-secondary)',
  display: 'block',
  marginBottom: 4,
};

const primaryBtn: React.CSSProperties = {
  padding: '6px 14px',
  fontSize: 12,
  borderRadius: 6,
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  cursor: 'pointer',
  fontWeight: 500,
};

const secondaryBtn: React.CSSProperties = {
  padding: '6px 14px',
  fontSize: 12,
  borderRadius: 6,
  background: 'transparent',
  color: 'var(--text-secondary)',
  border: '1px solid var(--border)',
  cursor: 'pointer',
};

export function ModelServiceForm({ open, mode, initial, onClose, onSave }: ModelServiceFormProps) {
  const [providerId, setProviderId] = useState(initial?.providerId ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [apiHost, setApiHost] = useState(initial?.apiHost ?? '');
  const [apiKey, setApiKey] = useState('');
  const [apiModel, setApiModel] = useState(initial?.apiModel ?? '');
  const [showKey, setShowKey] = useState(false);
  const [detected, setDetected] = useState<Array<{ id: string; name: string }>>([]);
  const [detecting, setDetecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleDetect = async () => {
    if (!apiHost || !apiKey) {
      setError('请先填写 API 地址与 API Key');
      return;
    }
    setDetecting(true);
    setError(null);
    try {
      const r = await providersApi.detect(apiHost, apiKey);
      setDetected(r.data.models);
      if (r.data.models.length > 0 && !apiModel) {
        setApiModel(r.data.models[0].id);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '检测失败');
    } finally {
      setDetecting(false);
    }
  };

  const handleSave = async () => {
    if (!providerId.trim() || !name.trim() || !apiHost.trim() || !apiKey.trim()) {
      setError('供应商 ID、名称、API 地址、API Key 都是必填');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (mode === 'add') {
        await providersApi.add({
          provider_id: providerId.trim(),
          name: name.trim(),
          notes: notes.trim(),
          api_host: apiHost.trim(),
          api_key: apiKey,
          api_model: apiModel.trim(),
        });
      } else if (initial) {
        await providersApi.update(initial.providerId, {
          name: name.trim(),
          notes: notes.trim(),
          api_host: apiHost.trim(),
          api_key: apiKey,
          api_model: apiModel.trim(),
        });
      }
      onSave();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 480,
          maxWidth: '90vw',
          maxHeight: '90vh',
          overflowY: 'auto',
          background: 'var(--bg-card)',
          borderRadius: 12,
          padding: 20,
          border: '1px solid var(--border)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
          {mode === 'add' ? '添加模型服务' : `编辑 ${initial?.name ?? ''}`}
        </h2>

        {error && (
          <div
            style={{
              marginBottom: 12,
              padding: '8px 12px',
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.4)',
              borderRadius: 6,
              color: '#ef4444',
              fontSize: 12,
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <label style={labelStyle}>供应商 ID（不可重复，不可改）</label>
            <input
              style={inputStyle}
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
              placeholder="例如 my-deepseek"
              disabled={mode === 'edit'}
            />
          </div>
          <div>
            <label style={labelStyle}>名称</label>
            <input
              style={inputStyle}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="DeepSeek (生产)"
            />
          </div>
          <div>
            <label style={labelStyle}>备注</label>
            <input
              style={inputStyle}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="选填"
            />
          </div>
          <div>
            <label style={labelStyle}>API 请求地址 URL</label>
            <input
              style={inputStyle}
              value={apiHost}
              onChange={(e) => setApiHost(e.target.value)}
              placeholder="https://api.example.com/v1"
            />
          </div>
          <div>
            <label style={labelStyle}>API Key</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                style={inputStyle}
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={mode === 'add' ? 'sk-...' : '（留空保留旧 Key）'}
              />
              <button type="button" style={secondaryBtn} onClick={() => setShowKey(!showKey)}>
                {showKey ? '隐藏' : '显示'}
              </button>
            </div>
          </div>
          <div>
            <label style={labelStyle}>默认模型</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                style={inputStyle}
                value={apiModel}
                onChange={(e) => setApiModel(e.target.value)}
                list={`models-${providerId}`}
                placeholder="例如 gpt-4o-mini"
              />
              <button
                type="button"
                style={secondaryBtn}
                onClick={handleDetect}
                disabled={detecting || !apiHost || !apiKey}
              >
                {detecting ? '检测中…' : '检测模型'}
              </button>
            </div>
            {detected.length > 0 && (
              <datalist id={`models-${providerId}`}>
                {detected.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </datalist>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
          <button type="button" style={secondaryBtn} onClick={onClose}>
            取消
          </button>
          <button type="button" style={primaryBtn} onClick={handleSave} disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
