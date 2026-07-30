import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { tasksApi } from '../../api/tasks';
import { WorkflowArchiveDetail } from '../history_solutions/WorkflowArchiveDetail';
import type { Task, UpdateTaskInput } from '../../types/task';
import {
  Archive,
  Search,
  Trash2,
  ChevronRight,
  X,
  LoaderCircle,
  AlertCircle,
  Pencil,
  Play,
  Link as LinkIcon,
} from 'lucide-react';

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; bg: string; dotColor: string }
> = {
  pending: {
    label: '待处理',
    color: 'var(--accent-yellow)',
    bg: 'rgba(251,191,36,0.12)',
    dotColor: '#f59e0b',
  },
  analyzing: {
    label: '分析中',
    color: 'var(--accent-blue)',
    bg: 'rgba(59,130,246,0.12)',
    dotColor: '#3b82f6',
  },
  completed: {
    label: '已完成',
    color: 'var(--accent-green)',
    bg: 'rgba(74,222,128,0.12)',
    dotColor: '#10b981',
  },
  failed: {
    label: '失败',
    color: 'var(--accent-red)',
    bg: 'rgba(248,113,113,0.12)',
    dotColor: '#ef4444',
  },
};

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '';
  try {
    const d = dateStr.includes('T') ? new Date(dateStr) : new Date(dateStr.replace(' ', 'T') + 'Z');
    if (isNaN(d.getTime())) return '';
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);
    if (diffMin < 1) return '刚刚';
    if (diffMin < 60) return `${diffMin} 分钟前`;
    if (diffHour < 24) return `${diffHour} 小时前`;
    if (diffDay < 7) return `${diffDay} 天前`;
    if (diffDay < 30) return `${Math.floor(diffDay / 7)} 周前`;
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export function PatentConversionPage() {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ open: false, title: '', message: '', onConfirm: () => {} });

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
    if (editingId) return; // 编辑中不跳转
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

  const handleStartEdit = useCallback((task: Task) => {
    setEditingId(task.id);
    setEditingTitle(task.title);
  }, []);

  const handleSaveEdit = useCallback(
    async (taskId: string) => {
      if (!editingTitle.trim()) {
        setEditingId(null);
        return;
      }
      try {
        const task = await tasksApi.update(taskId, { title: editingTitle.trim() } as UpdateTaskInput);
        setTasks((prev) => prev.map((t) => (t.id === taskId ? task : t)));
      } catch {
        setError('编辑标题失败');
      }
      setEditingId(null);
      setEditingTitle('');
    },
    [editingTitle],
  );

  const handleCancelEdit = useCallback(() => {
    setEditingId(null);
    setEditingTitle('');
  }, []);

  // ====== 任务列表视图 ======
  if (!selectedTaskId) {
    const filtered = tasks.filter((t) => {
      const matchSearch =
        !search || t.title.toLowerCase().includes(search.toLowerCase()) || t.description.toLowerCase().includes(search.toLowerCase());
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'rgba(248,113,113,0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Archive size={16} style={{ color: 'var(--accent-red)' }} />
          </div>
          <div className="card-title" style={{ fontSize: 15, margin: 0 }}>
            历史方案库
          </div>
          <span
            style={{
              marginLeft: 2,
              fontSize: 11,
              color: 'var(--text-tertiary)',
              fontWeight: 400,
              padding: '1px 8px',
              borderRadius: 10,
              background: 'rgba(100,116,139,0.1)',
            }}
          >
            {tasks.length}
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

        {/* Search row */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1 }}>
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
                boxSizing: 'border-box',
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
                background:
                  filter === item.key ? 'rgba(59,130,246,0.2)' : 'rgba(100,116,139,0.1)',
                border:
                  filter === item.key
                    ? '1px solid rgba(59,130,246,0.35)'
                    : '1px solid transparent',
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
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 48,
              flex: 1,
            }}
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
                gap: 4,
                flex: 1,
                overflowY: 'auto',
                minHeight: 0,
                margin: '0 -2px',
                padding: '0 2px',
              }}
            >
              {filtered.length === 0 ? (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 40,
                    gap: 8,
                    flex: 1,
                  }}
                >
                  <Search size={20} style={{ color: 'var(--text-tertiary)', opacity: 0.3 }} />
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>无匹配任务</span>
                </div>
              ) : (
                filtered.map((task) => {
                  const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
                  const isEditing = editingId === task.id;

                  return (
                    <div
                      key={task.id}
                      onClick={() => handleSelectTask(task.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        padding: '12px 14px',
                        borderRadius: 10,
                        cursor: editingId ? 'default' : 'pointer',
                        border: '1px solid var(--border-light)',
                        background: 'rgba(255,255,255,0.02)',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (!editingId) {
                          e.currentTarget.style.borderColor = 'var(--border)';
                          e.currentTarget.style.background = 'rgba(59,130,246,0.04)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!editingId) {
                          e.currentTarget.style.borderColor = 'var(--border-light)';
                          e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                        }
                      }}
                    >
                      {/* Status dot */}
                      <div
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          flexShrink: 0,
                          background: cfg.dotColor,
                          boxShadow: `0 0 8px ${cfg.dotColor}50`,
                        }}
                      />

                      {/* Content */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {isEditing ? (
                          <input
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveEdit(task.id);
                              if (e.key === 'Escape') handleCancelEdit();
                            }}
                            onBlur={() => handleSaveEdit(task.id)}
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                            style={{
                              width: '100%',
                              padding: '4px 8px',
                              borderRadius: 4,
                              background: 'rgba(0,0,0,0.3)',
                              border: '1px solid var(--accent)',
                              color: 'var(--text-primary)',
                              fontSize: 13,
                              fontWeight: 500,
                              outline: 'none',
                              fontFamily: 'inherit',
                              boxSizing: 'border-box',
                            }}
                          />
                        ) : (
                          <div
                            style={{
                              fontSize: 13,
                              fontWeight: 500,
                              color: 'var(--text-primary)',
                              marginBottom: 3,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {task.title}
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
                            style={{
                              fontSize: 10,
                              color: 'var(--text-tertiary)',
                              opacity: 0.6,
                            }}
                          >
                            {formatDate(task.updatedAt || task.createdAt)}
                          </span>
                        </div>
                      </div>

                      {/* Action buttons */}
                      {!isEditing && (
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 2,
                            flexShrink: 0,
                            opacity: 0,
                            transition: 'opacity 0.15s',
                          }}
                          className="history-actions"
                          onMouseEnter={(e) => e.stopPropagation()}
                        >
                          {/* Edit */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleStartEdit(task);
                            }}
                            title="编辑标题"
                            style={{
                              width: 28,
                              height: 28,
                              borderRadius: 6,
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--text-tertiary)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              transition: 'all 0.15s',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
                              e.currentTarget.style.color = 'var(--text-primary)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'transparent';
                              e.currentTarget.style.color = 'var(--text-tertiary)';
                            }}
                          >
                            <Pencil size={12} />
                          </button>

                          {/* Continue */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectTask(task.id);
                            }}
                            title="继续"
                            style={{
                              width: 28,
                              height: 28,
                              borderRadius: 6,
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--text-tertiary)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              transition: 'all 0.15s',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = 'rgba(59,130,246,0.15)';
                              e.currentTarget.style.color = '#3b82f6';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'transparent';
                              e.currentTarget.style.color = 'var(--text-tertiary)';
                            }}
                          >
                            <Play size={12} />
                          </button>

                          {/* Share */}
                          <button
                            onClick={(e) => e.stopPropagation()}
                            title="分享"
                            style={{
                              width: 28,
                              height: 28,
                              borderRadius: 6,
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--text-tertiary)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              transition: 'all 0.15s',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = 'rgba(16,185,129,0.15)';
                              e.currentTarget.style.color = '#10b981';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'transparent';
                              e.currentTarget.style.color = 'var(--text-tertiary)';
                            }}
                          >
                            <LinkIcon size={12} />
                          </button>

                          {/* Delete */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteTask(task.id, task.title);
                            }}
                            title="删除"
                            style={{
                              width: 28,
                              height: 28,
                              borderRadius: 6,
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--text-tertiary)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              transition: 'all 0.15s',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = 'rgba(239,68,68,0.15)';
                              e.currentTarget.style.color = '#ef4444';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'transparent';
                              e.currentTarget.style.color = 'var(--text-tertiary)';
                            }}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      )}

                      {/* Arrow indicator */}
                      {!isEditing && (
                        <ChevronRight
                          size={14}
                          style={{
                            color: 'var(--text-tertiary)',
                            opacity: 0.2,
                            flexShrink: 0,
                            transition: 'opacity 0.15s',
                          }}
                        />
                      )}
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

        {/* Delete Confirmation Modal */}
        {confirmModal.open &&
          createPortal(
            <div
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                width: '100vw',
                height: '100vh',
                background: 'rgba(0,0,0,0.6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 99999,
              }}
              onClick={() => setConfirmModal((prev) => ({ ...prev, open: false }))}
            >
              <div
                style={{
                  width: 360,
                  maxWidth: '90vw',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 12,
                  padding: 24,
                  boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    marginBottom: 12,
                    fontSize: 15,
                    fontWeight: 600,
                    color: 'var(--accent-red)',
                  }}
                >
                  <AlertCircle size={20} />
                  {confirmModal.title}
                </div>
                <div
                  style={{
                    fontSize: 13,
                    color: 'var(--text-secondary)',
                    lineHeight: 1.6,
                    marginBottom: 20,
                  }}
                >
                  {confirmModal.message}
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                  <button
                    onClick={() => setConfirmModal((prev) => ({ ...prev, open: false }))}
                    style={{
                      padding: '6px 16px',
                      borderRadius: 6,
                      fontSize: 12,
                      background: 'rgba(100,116,139,0.1)',
                      border: '1px solid var(--border-light)',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      transition: 'all 0.15s',
                    }}
                  >
                    取消
                  </button>
                  <button
                    onClick={confirmModal.onConfirm}
                    style={{
                      padding: '6px 16px',
                      borderRadius: 6,
                      fontSize: 12,
                      background: '#ef4444',
                      border: 'none',
                      color: '#fff',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      transition: 'all 0.15s',
                    }}
                  >
                    确认
                  </button>
                </div>
              </div>
            </div>,
            document.body,
          )}

        {/* CSS for hover action visibility */}
        <style>{`
          .history-actions {
            opacity: 0 !important;
          }
          div:hover > .history-actions {
            opacity: 1 !important;
          }
        `}</style>
      </div>
    );
  }

  // ====== 任务详情视图 ======
  return <WorkflowArchiveDetail taskId={selectedTaskId} onBack={handleBackToList} />;
}
