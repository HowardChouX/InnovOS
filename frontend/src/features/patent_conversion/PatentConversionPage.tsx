import { useState, useEffect } from 'react';
import { tasksApi } from '../../api/tasks';
import { InlineConfirmModal } from '../../components/ui/InlineConfirmModal';
import { WorkflowArchiveDetail } from '../history_solutions/WorkflowArchiveDetail';
import type { Task } from '../../types/task';
import { Archive, Search, Trash2, ChevronRight, X, LoaderCircle, AlertCircle } from 'lucide-react';

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

function getDescriptionPreview(task: Task): string {
  if (!task.description) return '';
  return task.description.split('\n')[0].slice(0, 80);
}

export function PatentConversionPage() {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true); // start as loading
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ open: false, title: '', message: '', onConfirm: () => {} });

  // 加载任务列表
  useEffect(() => {
    tasksApi
      .list({ pageSize: 50 })
      .then((res) => {
        setTasks(res.data);
        setPage(res.page || 1);
        setTotalPages(res.totalPages || 1);
      })
      .catch((err) => {
        setError(err?.message || '加载任务列表失败');
      })
      .finally(() => setTasksLoading(false));
  }, []);

  const handleLoadMore = () => {
    if (loadingMore || page >= totalPages) return;
    setLoadingMore(true);
    const nextPage = page + 1;
    tasksApi
      .list({ pageSize: 50, page: nextPage })
      .then((res) => {
        setTasks((prev) => [...prev, ...res.data]);
        setPage(res.page || nextPage);
        setTotalPages(res.totalPages || 1);
      })
      .catch((err) => {
        setError(err?.message || '加载更多失败');
      })
      .finally(() => setLoadingMore(false));
  };

  const handleSelectTask = (taskId: string) => {
    setSelectedTaskId(taskId);
  };

  const handleBackToList = () => {
    setSelectedTaskId(null);
  };

  const handleDeleteTask = (taskId: string, title: string) => {
    setConfirmModal({
      open: true,
      title: '确认删除',
      message: `确认删除任务 "${title}"？`,
      onConfirm: () => {
        setConfirmModal((prev) => ({ ...prev, open: false }));
        tasksApi
          .remove(taskId)
          .then(() => {
            setTasks((prev) => prev.filter((t) => t.id !== taskId));
          })
          .catch(() => setError('删除失败'));
      },
    });
  };

  // ====== 任务列表视图 ======
  if (!selectedTaskId) {
    const filtered = tasks.filter((t) => {
      const matchSearch = !search || t.title.toLowerCase().includes(search.toLowerCase());
      const matchFilter = filter === 'all' || t.status === filter;
      return matchSearch && matchFilter;
    });
    const statusCounts = tasks.reduce(
      (acc, t) => {
        acc[t.status] = (acc[t.status] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );

    const filterItems = [
      { key: 'all', label: '全部', count: tasks.length },
      { key: 'pending', label: '待处理', count: statusCounts.pending || 0 },
      { key: 'analyzing', label: '分析中', count: statusCounts.analyzing || 0 },
      { key: 'completed', label: '已完成', count: statusCounts.completed || 0 },
      { key: 'failed', label: '失败', count: statusCounts.failed || 0 },
    ];

    return (
      <div
        className="card"
        style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, minHeight: 0 }}
      >
        {/* Header */}
        <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Archive size={16} style={{ color: 'var(--accent-red)' }} />
          历史方案库
          <span
            style={{ marginLeft: 4, fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400 }}
          >
            ({tasks.length})
          </span>
        </div>

        {/* Error banner */}
        {error && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(248,113,113,0.12)',
              border: '1px solid rgba(248,113,113,0.25)',
              fontSize: 11,
              color: 'var(--accent-red)',
            }}
          >
            <AlertCircle size={14} />
            <span style={{ flex: 1 }}>{error}</span>
            <button
              onClick={() => setError(null)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent-red)',
                cursor: 'pointer',
                padding: 2,
                display: 'flex',
              }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Search */}
        <div style={{ position: 'relative' }}>
          <Search
            size={13}
            style={{
              position: 'absolute',
              left: 10,
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-tertiary)',
              pointerEvents: 'none',
            }}
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索任务..."
            style={{
              width: '100%',
              padding: '7px 28px 7px 32px',
              borderRadius: 8,
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border-light)',
              color: 'var(--text-primary)',
              fontSize: 12,
              outline: 'none',
              fontFamily: 'inherit',
            }}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{
                position: 'absolute',
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'rgba(100,116,139,0.2)',
                border: 'none',
                borderRadius: '50%',
                width: 18,
                height: 18,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                color: 'var(--text-tertiary)',
                padding: 0,
              }}
            >
              <X size={11} />
            </button>
          )}
        </div>

        {/* Status filter pills */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {filterItems.map((item) => (
            <button
              key={item.key}
              onClick={() => setFilter(item.key)}
              style={{
                padding: '4px 12px',
                borderRadius: 20,
                fontSize: 11,
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontWeight: filter === item.key ? 600 : 400,
                background: filter === item.key ? 'rgba(59,130,246,0.2)' : 'rgba(100,116,139,0.1)',
                border:
                  filter === item.key ? '1px solid rgba(59,130,246,0.35)' : '1px solid transparent',
                color: filter === item.key ? 'var(--accent-blue)' : 'var(--text-tertiary)',
                transition: 'all 0.15s',
              }}
            >
              {item.label}
              {item.count > 0 && (
                <span style={{ marginLeft: 4, opacity: 0.6, fontSize: 10 }}>{item.count}</span>
              )}
            </button>
          ))}
        </div>

        {/* Task list */}
        {tasksLoading ? (
          <div
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 48 }}
          >
            <LoaderCircle
              size={24}
              className="animate-spin"
              style={{ color: 'var(--accent-blue)' }}
            />
          </div>
        ) : tasks.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 48,
              gap: 16,
              flex: 1,
            }}
          >
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: 16,
                background: 'rgba(100,116,139,0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Archive size={28} style={{ color: 'var(--text-tertiary)', opacity: 0.4 }} />
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                暂无历史任务
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', opacity: 0.7 }}>
                完成一个分析流程后，方案会自动出现在这里
              </div>
            </div>
          </div>
        ) : (
          <>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                maxHeight: 400,
                overflow: 'auto',
              }}
            >
              {filtered.length === 0 ? (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 32,
                    gap: 8,
                  }}
                >
                  <Search size={18} style={{ color: 'var(--text-tertiary)', opacity: 0.3 }} />
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>无匹配任务</span>
                </div>
              ) : (
                filtered.map((task) => {
                  const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
                  const descPreview = getDescriptionPreview(task);
                  return (
                    <div
                      key={task.id}
                      onClick={() => handleSelectTask(task.id)}
                      onMouseEnter={() => setHoveredId(task.id)}
                      onMouseLeave={() => setHoveredId(null)}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 10,
                        padding: '10px 12px',
                        borderRadius: 8,
                        cursor: 'pointer',
                        fontSize: 12,
                        background: hoveredId === task.id ? 'rgba(59,130,246,0.04)' : 'transparent',
                        border: `1px solid ${hoveredId === task.id ? 'rgba(59,130,246,0.12)' : 'transparent'}`,
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {/* Status dot */}
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          flexShrink: 0,
                          marginTop: 5,
                          background: cfg.color,
                          boxShadow: `0 0 6px ${cfg.color}40`,
                        }}
                      />
                      {/* Content */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            color: 'var(--text-primary)',
                            fontWeight: 500,
                            marginBottom: 3,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {task.title}
                        </div>
                        {descPreview && (
                          <div
                            style={{
                              fontSize: 11,
                              color: 'var(--text-tertiary)',
                              marginBottom: 4,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              opacity: 0.7,
                            }}
                          >
                            {descPreview}
                          </div>
                        )}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span
                            style={{
                              fontSize: 10,
                              padding: '1px 7px',
                              borderRadius: 10,
                              background: cfg.bg,
                              color: cfg.color,
                              fontWeight: 500,
                            }}
                          >
                            {cfg.label}
                          </span>
                          <span
                            style={{ fontSize: 10, color: 'var(--text-tertiary)', opacity: 0.6 }}
                          >
                            {formatDate(task.createdAt)}
                          </span>
                        </div>
                      </div>
                      {/* Actions */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                        {hoveredId === task.id && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteTask(task.id, task.title);
                            }}
                            title="删除任务"
                            style={{
                              background: 'rgba(248,113,113,0.1)',
                              border: '1px solid rgba(248,113,113,0.2)',
                              color: 'var(--accent-red)',
                              cursor: 'pointer',
                              padding: '4px 5px',
                              borderRadius: 6,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              transition: 'all 0.15s',
                            }}
                          >
                            <Trash2 size={12} />
                          </button>
                        )}
                        <ChevronRight
                          size={14}
                          style={{
                            color: 'var(--text-tertiary)',
                            opacity: hoveredId === task.id ? 0.6 : 0.2,
                            transition: 'opacity 0.15s',
                          }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Load more */}
            {page < totalPages && (
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                style={{
                  padding: '8px 0',
                  borderRadius: 6,
                  fontSize: 11,
                  cursor: loadingMore ? 'default' : 'pointer',
                  background: 'rgba(59,130,246,0.06)',
                  border: '1px solid rgba(59,130,246,0.12)',
                  color: 'var(--accent-blue)',
                  fontFamily: 'inherit',
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  transition: 'background 0.15s',
                }}
              >
                {loadingMore ? (
                  <LoaderCircle size={12} className="animate-spin" />
                ) : (
                  <ChevronRight size={12} />
                )}
                {loadingMore ? '加载中...' : `加载更多 (${tasks.length}/${totalPages * 50})`}
              </button>
            )}
          </>
        )}

        <InlineConfirmModal
          open={confirmModal.open}
          title={confirmModal.title}
          message={confirmModal.message}
          onConfirm={confirmModal.onConfirm}
          onCancel={() => setConfirmModal((prev) => ({ ...prev, open: false }))}
        />
      </div>
    );
  }

  // ====== 任务详情视图 ======
  return <WorkflowArchiveDetail taskId={selectedTaskId} onBack={handleBackToList} />;
}
