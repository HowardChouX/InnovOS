import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { providersApi, type Provider } from '../../api/admin/providers';
import { ModelServiceForm } from './ModelServiceForm';

const cardStyle: React.CSSProperties = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 10,
  padding: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
};

const healthColor = (h?: Provider['health']) => {
  if (h === 'unhealthy') return '#ef4444';
  if (h === 'degraded') return '#f59e0b';
  return '#22c55e';
};

const healthLabel = (h?: Provider['health']) => {
  if (h === 'unhealthy') return '不可用';
  if (h === 'degraded') return '降级';
  return '正常';
};

export function ModelServicePanel() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [formMode, setFormMode] = useState<'add' | 'edit' | null>(null);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await providersApi.list();
      setProviders(r.data);
    } catch (e) {
      console.error('load providers failed', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const filtered = providers.filter((p) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      p.name.toLowerCase().includes(q) ||
      p.providerId.toLowerCase().includes(q) ||
      p.notes.toLowerCase().includes(q) ||
      p.apiHost.toLowerCase().includes(q)
    );
  });

  const handleCheck = async (p: Provider) => {
    try {
      const r = await providersApi.check(p.providerId, p.apiModel);
      if (r.data.status !== 'ok') {
        alert(`测速失败: ${r.data.status} ${r.data.status_code ?? ''}`);
      } else {
        alert(`${p.name}: ${r.data.latency_ms}ms`);
      }
    } catch (e) {
      alert(`测速异常: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const handleDelete = async (p: Provider) => {
    if (!confirm(`确认删除 ${p.name}?`)) return;
    try {
      await providersApi.delete(p.providerId);
      load();
    } catch (e) {
      alert(`删除失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">模型服务</h1>
        <div className="flex items-center gap-2">
          <input
            placeholder="搜索名称 / ID / URL / 备注"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
              fontSize: 13,
              outline: 'none',
            }}
          />
          <button
            onClick={() => navigate('/admin/usage')}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              background: 'transparent',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            使用统计
          </button>
          <button
            onClick={() => {
              setEditingProvider(null);
              setFormMode('add');
            }}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              background: 'var(--accent)',
              color: '#fff',
              border: 'none',
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            + 添加
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-tertiary)' }}>加载中…</div>
      ) : filtered.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            color: 'var(--text-tertiary)',
            padding: '60px 0',
            background: 'var(--bg-card)',
            borderRadius: 10,
            border: '1px dashed var(--border)',
          }}
        >
          {search ? '没有匹配的模型服务' : '还没有任何模型服务，点右上角"添加"创建第一条'}
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 12,
          }}
        >
          {filtered.map((p) => (
            <div key={p.providerId} style={cardStyle}>
              <div className="flex items-center justify-between">
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{p.providerId}</div>
                </div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 11,
                    color: healthColor(p.health),
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: healthColor(p.health),
                    }}
                  />
                  {healthLabel(p.health)}
                </div>
              </div>
              {p.notes && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{p.notes}</div>
              )}
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{p.apiHost}</div>
              {p.apiModel && (
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: 'monospace',
                    background: 'rgba(0,0,0,0.2)',
                    padding: '2px 6px',
                    borderRadius: 4,
                    alignSelf: 'flex-start',
                  }}
                >
                  {p.apiModel}
                </div>
              )}
              <div className="flex items-center gap-2 mt-2">
                <button
                  onClick={() => handleCheck(p)}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                  }}
                >
                  测速
                </button>
                <button
                  onClick={() => {
                    setEditingProvider(p);
                    setFormMode('edit');
                  }}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                  }}
                >
                  编辑
                </button>
                <button
                  onClick={() => handleDelete(p)}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'transparent',
                    color: '#ef4444',
                    border: '1px solid rgba(239,68,68,0.4)',
                    cursor: 'pointer',
                  }}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ModelServiceForm
        open={formMode !== null}
        mode={formMode ?? 'add'}
        initial={editingProvider}
        onClose={() => setFormMode(null)}
        onSave={() => {
          setFormMode(null);
          load();
        }}
      />
    </div>
  );
}
