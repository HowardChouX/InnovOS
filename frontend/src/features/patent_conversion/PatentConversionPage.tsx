import { useState, useEffect } from 'react';
import { useTaskStore } from '../../store/useTaskStore';
import { tasksApi } from '../../api/tasks';
import { InlineConfirmModal } from '../../components/ui/InlineConfirmModal';
import { WorkflowArchiveDetail } from '../history_solutions/WorkflowArchiveDetail';
import type { Task } from '../../types/task';

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '待处理', color: 'var(--accent-yellow)', bg: 'rgba(251,191,36,0.12)' },
  analyzing: { label: '分析中', color: 'var(--accent-blue)', bg: 'rgba(59,130,246,0.12)' },
  completed: { label: '已完成', color: 'var(--accent-green)', bg: 'rgba(74,222,128,0.12)' },
  failed: { label: '失败', color: 'var(--accent-red)', bg: 'rgba(248,113,113,0.12)' },
};

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '';
  const d = new Date(dateStr.replace(' ', 'T') + 'Z');
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);
  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin}分钟前`;
  if (diffHour < 24) return `${diffHour}小时前`;
  if (diffDay < 7) return `${diffDay}天前`;
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

export function PatentConversionPage() {
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const selectTask = useTaskStore((s) => s.selectTask);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [confirmModal, setConfirmModal] = useState<{ open: boolean; title: string; message: string; onConfirm: () => void }>({ open: false, title: '', message: '', onConfirm: () => {} });

  // 加载任务列表
  useEffect(() => {
    setTasksLoading(true);
    tasksApi.list({ pageSize: 50 })
      .then((res) => setTasks(res.data))
      .catch(() => {})
      .finally(() => setTasksLoading(false));
  }, []);

  const handleSelectTask = (taskId: string) => {
    selectTask(taskId);
  };

  const handleBackToList = () => {
    selectTask('');
  };

  // ====== 任务列表视图 ======
  if (!selectedTaskId) {
    const filtered = tasks.filter((t) => {
      const matchSearch = !search || t.title.toLowerCase().includes(search.toLowerCase());
      const matchFilter = filter === 'all' || t.status === filter;
      return matchSearch && matchFilter;
    });
    const statusCounts = tasks.reduce((acc, t) => {
      acc[t.status] = (acc[t.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, minHeight: 0 }}>
        <div className="card-title">
          <i className="fa-solid fa-file-contract" style={{ marginRight: 8, color: 'var(--accent-red)' }} />
          历史方案库
          <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400 }}>({tasks.length})</span>
        </div>

        {/* 搜索 */}
        <div style={{ position: 'relative' }}>
          <i className="fa-solid fa-magnifying-glass" style={{
            position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)',
            fontSize: 10, color: 'var(--text-tertiary)',
          }} />
          <input
            value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索任务..."
            style={{
              width: '100%', padding: '6px 8px 6px 24px', borderRadius: 6,
              background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
              color: 'var(--text-primary)', fontSize: 11, outline: 'none', fontFamily: 'inherit',
            }}
          />
        </div>

        {/* 状态筛选 */}
        <div style={{ display: 'flex', gap: 4 }}>
          {[
            { key: 'all', label: '全部', count: tasks.length },
            { key: 'pending', label: '待处理', count: statusCounts.pending || 0 },
            { key: 'analyzing', label: '分析中', count: statusCounts.analyzing || 0 },
            { key: 'completed', label: '已完成', count: statusCounts.completed || 0 },
          ].map((item) => (
            <button key={item.key} onClick={() => setFilter(item.key)} style={{
              padding: '3px 8px', borderRadius: 4, fontSize: 10, cursor: 'pointer',
              background: filter === item.key ? 'rgba(59,130,246,0.15)' : 'transparent',
              border: filter === item.key ? '1px solid rgba(59,130,246,0.3)' : '1px solid transparent',
              color: filter === item.key ? 'var(--accent-blue)' : 'var(--text-tertiary)',
              fontFamily: 'inherit',
            }}>
              {item.label} {item.count > 0 && <span style={{ opacity: 0.6 }}>{item.count}</span>}
            </button>
          ))}
        </div>

        {/* 列表 */}
        {tasksLoading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
            <i className="fa-solid fa-circle-notch fa-spin" style={{ color: 'var(--accent-blue)', fontSize: 20 }} />
          </div>
        ) : tasks.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 12 }}>
            <i className="fa-solid fa-folder-open" style={{ fontSize: 24, color: 'var(--text-tertiary)', opacity: 0.4 }} />
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>暂无历史任务</span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>完成一个分析流程后，方案会自动出现在这里</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 400, overflow: 'auto' }}>
            {filtered.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 16, fontSize: 11, color: 'var(--text-tertiary)' }}>
                无匹配任务
              </div>
            ) : (
              filtered.map((task) => {
                const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
                return (
                  <div
                    key={task.id}
                    onClick={() => handleSelectTask(task.id)}
                    onMouseEnter={() => setHoveredId(task.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px',
                      borderRadius: 6, cursor: 'pointer', fontSize: 12,
                      background: 'transparent',
                      border: '1px solid transparent',
                      transition: 'all 0.1s ease',
                    }}
                  >
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0, marginTop: 5,
                      background: cfg.color,
                    }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        color: 'var(--text-primary)', fontWeight: 500, marginBottom: 2,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {task.title}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{
                          fontSize: 9, padding: '1px 5px', borderRadius: 3,
                          background: cfg.bg, color: cfg.color,
                        }}>
                          {cfg.label}
                        </span>
                        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                          {formatDate(task.createdAt)}
                        </span>
                      </div>
                    </div>
                    {hoveredId === task.id && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmModal({
                            open: true,
                            title: '确认删除',
                            message: `确认删除任务 "${task.title}"？`,
                            onConfirm: () => {
                              setConfirmModal(prev => ({ ...prev, open: false }));
                              tasksApi.remove(task.id).then(() => {
                                setTasks((prev) => prev.filter((t) => t.id !== task.id));
                              }).catch(() => alert('删除失败'));
                            },
                          });
                        }}
                        style={{
                          background: 'rgba(248,113,113,0.1)',
                          border: '1px solid rgba(248,113,113,0.2)',
                          color: 'var(--accent-red)',
                          cursor: 'pointer', fontSize: 10,
                          padding: '2px 6px', borderRadius: 4, fontFamily: 'inherit', flexShrink: 0,
                          transition: 'all 0.15s',
                        }}
                      >
                        <i className="fa-solid fa-trash-can" style={{ fontSize: 9 }} />
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
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

  // ====== 任务详情视图 ======
  return (
    <WorkflowArchiveDetail
      taskId={selectedTaskId}
      onBack={handleBackToList}
    />
  );
}
