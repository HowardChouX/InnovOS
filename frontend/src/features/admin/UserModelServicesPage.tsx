import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  userModelServicesApi,
  type UserModelService,
  type AvailableModelService,
} from '../../api/admin/userModelServices';

const rowStyle = (dragging: boolean): React.CSSProperties => ({
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  padding: '10px 12px',
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  opacity: dragging ? 0.4 : 1,
  cursor: 'grab',
});

const healthDot = (h?: boolean) => (h === false ? '#ef4444' : '#22c55e');

export function UserModelServicesPage() {
  const { userId: userIdParam } = useParams<{ userId: string }>();
  const userId = Number(userIdParam);

  const [enabled, setEnabled] = useState<UserModelService[]>([]);
  const [available, setAvailable] = useState<AvailableModelService[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const dragNode = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    if (!userId) return;
    setError(null);
    try {
      const [a, b] = await Promise.all([
        userModelServicesApi.list(userId),
        userModelServicesApi.listAvailable(userId),
      ]);
      setEnabled(a.data);
      setAvailable(b.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setOverIndex(index);
  };

  const handleDrop = async (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === dropIndex) {
      setDragIndex(null);
      setOverIndex(null);
      return;
    }
    const next = [...enabled];
    const [moved] = next.splice(dragIndex, 1);
    next.splice(dropIndex, 0, moved);
    setEnabled(next);
    setDragIndex(null);
    setOverIndex(null);
    try {
      await userModelServicesApi.reorder(
        userId,
        next.map((e) => e.provider_id),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : '排序保存失败');
      load();
    }
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setOverIndex(null);
  };

  const handleAdd = async (providerId: string) => {
    try {
      await userModelServicesApi.add(userId, providerId);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '添加失败');
    }
  };

  const handleRemove = async (providerId: string) => {
    try {
      await userModelServicesApi.remove(userId, providerId);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '移除失败');
    }
  };

  const handleToggle = async (providerId: string, isEnabled: boolean) => {
    try {
      await userModelServicesApi.toggle(userId, providerId, isEnabled);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '切换失败');
    }
  };

  if (loading) return <div style={{ padding: 24 }}>加载中…</div>;

  const notEnabled = available.filter((a) => !a.already_enabled);

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 className="text-2xl font-bold">用户 #{userId} — AI 模型服务</h1>
          <Link
            to="/admin/users"
            style={{ color: 'var(--text-secondary)', fontSize: 12, textDecoration: 'underline' }}
          >
            ← 返回用户管理
          </Link>
        </div>
      </div>

      {error && (
        <div
          style={{
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

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>
          已开通（拖拽行可调整故障转移顺序）
        </h2>
        {enabled.length === 0 ? (
          <div
            style={{
              padding: 20,
              textAlign: 'center',
              color: 'var(--text-tertiary)',
              background: 'var(--bg-card)',
              border: '1px dashed var(--border)',
              borderRadius: 8,
            }}
          >
            暂未开通任何模型服务；从下方"未开通"里添加
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {enabled.map((e, i) => (
              <div
                key={e.provider_id}
                ref={i === dragIndex ? dragNode : null}
                draggable
                onDragStart={(ev) => handleDragStart(ev, i)}
                onDragOver={(ev) => handleDragOver(ev, i)}
                onDrop={(ev) => handleDrop(ev, i)}
                onDragEnd={handleDragEnd}
                style={{
                  ...rowStyle(i === dragIndex),
                  borderColor:
                    overIndex === i && dragIndex !== i ? 'var(--accent)' : 'var(--border)',
                  borderWidth: overIndex === i ? 2 : 1,
                }}
              >
                <span
                  style={{ cursor: 'grab', color: 'var(--text-tertiary)', fontSize: 16 }}
                  title="拖拽重排"
                >
                  ⋮⋮
                </span>
                <span
                  style={{
                    fontSize: 11,
                    color: 'var(--text-tertiary)',
                    minWidth: 24,
                  }}
                >
                  #{i + 1}
                </span>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: healthDot(e.is_healthy),
                  }}
                  title={e.is_healthy ? '健康' : '降级/不可用'}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{e.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {e.api_host} · {e.api_model || '（无默认模型）'}
                  </div>
                </div>
                <button
                  onClick={() => handleToggle(e.provider_id, !e.is_enabled)}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'transparent',
                    color: e.is_enabled ? '#22c55e' : 'var(--text-tertiary)',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                  }}
                >
                  {e.is_enabled ? '已启用' : '已停用'}
                </button>
                <button
                  onClick={() => handleRemove(e.provider_id)}
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
                  移除
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>未开通</h2>
        {notEnabled.length === 0 ? (
          <div
            style={{
              padding: 16,
              textAlign: 'center',
              color: 'var(--text-tertiary)',
              background: 'var(--bg-card)',
              border: '1px dashed var(--border)',
              borderRadius: 8,
            }}
          >
            目录里所有模型服务都已开通
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {notEnabled.map((a) => (
              <div key={a.provider_id} style={rowStyle(false)}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: healthDot(a.is_healthy),
                    marginLeft: 12,
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{a.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {a.api_host} · {a.api_model || '（无默认模型）'}
                  </div>
                </div>
                <button
                  onClick={() => handleAdd(a.provider_id)}
                  style={{
                    padding: '4px 12px',
                    fontSize: 11,
                    borderRadius: 4,
                    background: 'var(--accent)',
                    color: '#fff',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  + 开通
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
