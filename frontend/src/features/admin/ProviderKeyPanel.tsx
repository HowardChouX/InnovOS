/**
 * ProviderKeyPanel — 在 KeyManagementPage 中显示某 Provider 下的所有 API Key,
 * 支持新增 / 替换 / 启停 / 删除。
 *
 * 设计:复用现有 KeyManagementPage 的视觉风格,内联实现 Key CRUD,
 * 不重写整个 1464 行的页面。完整的组件拆分是后续 TODO。
 */

import { useState, useEffect } from 'react';
import {
  apiKeysApi,
  type ApiKeyMetadata,
} from '../../api/admin/apiKeys';

interface Props {
  providerId: string;
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

const dangerBtn: React.CSSProperties = {
  ...secondaryBtn,
  color: '#ef4444',
  borderColor: 'rgba(239, 68, 68, 0.4)',
};

export function ProviderKeyPanel({ providerId }: Props) {
  const [keys, setKeys] = useState<ApiKeyMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 新增表单
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPlaintext, setNewPlaintext] = useState('');
  const [showPlaintext, setShowPlaintext] = useState(false);
  const [newPriority, setNewPriority] = useState(100);
  const [newMaxRpm, setNewMaxRpm] = useState<string>('');

  // 替换
  const [replaceKeyId, setReplaceKeyId] = useState<number | null>(null);
  const [replacePlaintext, setReplacePlaintext] = useState('');
  const [showReplacePlaintext, setShowReplacePlaintext] = useState(false);

  useEffect(() => {
    if (!providerId) return;
    refresh();
  }, [providerId]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiKeysApi.list(providerId);
      setKeys(resp.data);
    } catch (e: unknown) {
      setError(`加载 Key 列表失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!newName.trim() || !newPlaintext.trim()) {
      alert('名称和 Key 都不能为空');
      return;
    }
    try {
      await apiKeysApi.create(providerId, {
        name: newName.trim(),
        apiKey: newPlaintext,
        priority: newPriority,
        maxRpm: newMaxRpm.trim() ? parseInt(newMaxRpm, 10) : null,
      });
      setNewName('');
      setNewPlaintext('');
      setShowCreate(false);
      await refresh();
    } catch (e: unknown) {
      alert(`创建失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async function handleReplace() {
    if (!replaceKeyId || !replacePlaintext.trim()) {
      alert('新 Key 不能为空');
      return;
    }
    try {
      await apiKeysApi.replaceSecret(providerId, replaceKeyId, replacePlaintext);
      setReplaceKeyId(null);
      setReplacePlaintext('');
      await refresh();
    } catch (e: unknown) {
      alert(`替换失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async function handleToggle(key: ApiKeyMetadata) {
    try {
      if (key.isActive) {
        await apiKeysApi.deactivate(providerId, key.id);
      } else {
        await apiKeysApi.activate(providerId, key.id);
      }
      await refresh();
    } catch (e: unknown) {
      alert(`操作失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async function handleDelete(key: ApiKeyMetadata) {
    if (!confirm(`确认停用 Key「${key.name}」?`)) return;
    try {
      await apiKeysApi.delete(providerId, key.id);
      await refresh();
    } catch (e: unknown) {
      alert(`删除失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  if (!providerId) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}
      >
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
          API Keys(共 {keys.length} 把)
        </h3>
        <button
          type="button"
          onClick={() => setShowCreate(!showCreate)}
          style={primaryBtn}
        >
          {showCreate ? '取消' : '+ 新增 Key'}
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: '8px 12px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: 6,
            color: '#ef4444',
            fontSize: 12,
            marginBottom: 12,
          }}
        >
          {error}
        </div>
      )}

      {showCreate && (
        <div
          style={{
            padding: 14,
            background: 'rgba(255,255,255,0.03)',
            borderRadius: 8,
            border: '1px solid var(--border)',
            marginBottom: 14,
          }}
        >
          <div style={{ marginBottom: 8 }}>
            <label style={labelStyle}>名称</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="例如 production-primary"
              style={inputStyle}
            />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={labelStyle}>API Key</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type={showPlaintext ? 'text' : 'password'}
                value={newPlaintext}
                onChange={(e) => setNewPlaintext(e.target.value)}
                placeholder="sk-..."
                style={{ ...inputStyle, flex: 1 }}
              />
              <button
                type="button"
                onClick={() => setShowPlaintext(!showPlaintext)}
                style={secondaryBtn}
              >
                {showPlaintext ? '隐藏' : '显示'}
              </button>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>优先级</label>
              <input
                type="number"
                value={newPriority}
                onChange={(e) => setNewPriority(parseInt(e.target.value, 10) || 100)}
                style={inputStyle}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Key 级 RPM(可选)</label>
              <input
                type="number"
                value={newMaxRpm}
                onChange={(e) => setNewMaxRpm(e.target.value)}
                placeholder="继承 Provider"
                style={inputStyle}
              />
            </div>
          </div>
          <button type="button" onClick={handleCreate} style={primaryBtn}>
            保存
          </button>
          <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--text-secondary)' }}>
            提交后服务端加密存储(AES-256-GCM),前端永不返回已保存的明文。
          </span>
        </div>
      )}

      {loading ? (
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>加载中…</div>
      ) : keys.length === 0 ? (
        <div
          style={{
            padding: 20,
            textAlign: 'center',
            fontSize: 13,
            color: 'var(--text-secondary)',
            background: 'rgba(255,255,255,0.02)',
            borderRadius: 8,
          }}
        >
          还没有 API Key,点击右上角"+ 新增 Key"开始添加。
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {keys.map((k) => (
            <div
              key={k.id}
              style={{
                padding: '10px 12px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                opacity: k.isActive ? 1 : 0.6,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                    {k.name}{' '}
                    <span
                      style={{
                        fontSize: 10,
                        marginLeft: 6,
                        padding: '1px 6px',
                        borderRadius: 3,
                        background: k.isActive
                          ? 'rgba(34, 197, 94, 0.2)'
                          : 'rgba(120, 120, 120, 0.2)',
                        color: k.isActive ? '#22c55e' : '#999',
                      }}
                    >
                      {k.isActive ? 'Active' : 'Inactive'}
                    </span>
                    {k.cooldownUntil && new Date(k.cooldownUntil) > new Date() && (
                      <span
                        style={{
                          fontSize: 10,
                          marginLeft: 6,
                          padding: '1px 6px',
                          borderRadius: 3,
                          background: 'rgba(251, 146, 60, 0.2)',
                          color: '#fb923c',
                        }}
                      >
                        Cooldown
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                    {k.masked} · 指纹 {k.fingerprint} · 优先 {k.priority} · 调用{' '}
                    {k.requestCount}(成功 {k.successCount}/失败 {k.failureCount})
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button type="button" onClick={() => handleToggle(k)} style={secondaryBtn}>
                    {k.isActive ? '停用' : '启用'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setReplaceKeyId(k.id);
                      setReplacePlaintext('');
                    }}
                    style={secondaryBtn}
                  >
                    替换
                  </button>
                  <button type="button" onClick={() => handleDelete(k)} style={dangerBtn}>
                    删除
                  </button>
                </div>
              </div>

              {replaceKeyId === k.id && (
                <div
                  style={{
                    marginTop: 8,
                    paddingTop: 8,
                    borderTop: '1px dashed var(--border)',
                  }}
                >
                  <label style={labelStyle}>新 API Key(替换后旧值立即失效)</label>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <input
                      type={showReplacePlaintext ? 'text' : 'password'}
                      value={replacePlaintext}
                      onChange={(e) => setReplacePlaintext(e.target.value)}
                      placeholder="sk-..."
                      style={{ ...inputStyle, flex: 1 }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowReplacePlaintext(!showReplacePlaintext)}
                      style={secondaryBtn}
                    >
                      {showReplacePlaintext ? '隐藏' : '显示'}
                    </button>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <button type="button" onClick={handleReplace} style={primaryBtn}>
                      确认替换
                    </button>
                    <button
                      type="button"
                      onClick={() => setReplaceKeyId(null)}
                      style={{ ...secondaryBtn, marginLeft: 6 }}
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}