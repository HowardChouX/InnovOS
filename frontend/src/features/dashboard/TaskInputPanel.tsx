import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTaskStore } from '../../store/useTaskStore';
import { useAnalysisStore } from '../../store/useAnalysisStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { tasksApi } from '../../api/tasks';
import { knowledgeApi } from '../../api/knowledge';
import type { KnowledgeBaseListItem } from '../../types/knowledge';
import type { Task } from '../../types/task';
import {
  Search,
  X,
  Pencil,
  Play,
  Link as LinkIcon,
  Trash2,
  LoaderCircle,
  AlertCircle,
  Clock,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; bg: string; dotColor: string; icon: React.ReactNode }
> = {
  pending: {
    label: '待处理',
    color: 'var(--accent-yellow)',
    bg: 'rgba(251,191,36,0.12)',
    dotColor: '#f59e0b',
    icon: <Clock size={12} />,
  },
  analyzing: {
    label: '分析中',
    color: 'var(--accent-blue)',
    bg: 'rgba(59,130,246,0.12)',
    dotColor: '#3b82f6',
    icon: <LoaderCircle size={12} className="animate-spin" />,
  },
  completed: {
    label: '已完成',
    color: 'var(--accent-green)',
    bg: 'rgba(74,222,128,0.12)',
    dotColor: '#10b981',
    icon: <CheckCircle2 size={12} />,
  },
  failed: {
    label: '失败',
    color: 'var(--accent-red)',
    bg: 'rgba(248,113,113,0.12)',
    dotColor: '#ef4444',
    icon: <AlertTriangle size={12} />,
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

export function TaskInputPanel() {
  const [description, setDescription] = useState('');
  const [bases, setBases] = useState<KnowledgeBaseListItem[]>([]);
  const [selectedBaseIds, setSelectedBaseIds] = useState<Set<string>>(new Set());
  const [showKbSelector, setShowKbSelector] = useState(false);
  const [loadingBases, setLoadingBases] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const selectorRef = useRef<HTMLDivElement>(null);

  const createTask = useTaskStore((s) => s.createTask);
  const selectTask = useTaskStore((s) => s.selectTask);
  const triggerAnalysis = useAnalysisStore((s) => s.triggerAnalysis);
  const isRunning = useWorkflowStore((s) => s.isRunning);
  const cancelAnalysis = useWorkflowStore((s) => s.cancelAnalysis);
  const clearWorkflow = useWorkflowStore((s) => s.clearWorkflow);

  // History modal state
  const [showHistory, setShowHistory] = useState(false);
  const [historyTasks, setHistoryTasks] = useState<Task[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historySearch, setHistorySearch] = useState('');
  const [historyFilter, setHistoryFilter] = useState('all');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [deleteModal, setDeleteModal] = useState<{
    open: boolean;
    taskId: string;
    title: string;
  }>({ open: false, taskId: '', title: '' });
  const [historyError, setHistoryError] = useState('');

  useEffect(() => {
    knowledgeApi
      .listBases(1, 100)
      .then((res) => {
        const items = res.data?.items ?? [];
        setBases(items);
        if (items.length === 0) {
          setLoadError('暂无知识库，请先在知识库页面创建');
        }
      })
      .catch((err) => {
        console.error('Failed to load knowledge bases:', err);
        setBases([]);
        setLoadError('加载知识库失败');
      })
      .finally(() => setLoadingBases(false));
  }, []);

  useEffect(() => {
    if (!showKbSelector) return;
    const handler = (e: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setShowKbSelector(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showKbSelector]);

  // Load history tasks when modal opens
  useEffect(() => {
    if (showHistory) {
      setHistoryLoading(true);
      tasksApi
        .list({ pageSize: 50 })
        .then((res) => setHistoryTasks(res.data))
        .catch(() => setHistoryTasks([]))
        .finally(() => setHistoryLoading(false));
    }
  }, [showHistory]);

  const toggleBase = (id: string) => {
    setSelectedBaseIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectedBases = bases.filter((b) => selectedBaseIds.has(b.id));

  const handleSubmit = async () => {
    if (!description.trim() || submitting) return;
    setSubmitError('');
    setSubmitting(true);
    try {
      const task = await createTask({ title: description.slice(0, 50), description, tags: [] });
      if (!task) {
        setSubmitError('创建任务失败，请检查登录状态或重试');
        return;
      }
      setDescription('');
      const kbIds = Array.from(selectedBaseIds);
      await triggerAnalysis(task.id, kbIds.length > 0 ? kbIds : undefined);
    } catch (error) {
      console.error('Failed to start analysis:', error);
      setSubmitError(error instanceof Error ? error.message : '启动分析失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleNewTask = () => {
    if (isRunning) {
      cancelAnalysis();
    }
    selectTask('');
    clearWorkflow();
    setDescription('');
    setSubmitError('');
  };

  const handleSelectHistoryTask = async (task: Task) => {
    selectTask(task.id);
    setShowHistory(false);

    // 如果任务失败，尝试从失败的步骤继续执行
    if (task.status === 'failed') {
      try {
        // 获取 workflow 信息，找到失败的步骤
        const workflowRes = await fetch(`/api/workflow/${task.id}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
          },
        });

        if (workflowRes.ok) {
          const workflowData = await workflowRes.json();
          const steps = workflowData.data?.steps || [];

          // 找到最后一个失败的步骤
          const failedStep = [...steps].reverse().find((s: any) => s.status === 'failed');

          if (failedStep) {
            // 从失败的步骤继续执行
            await triggerAnalysis(task.id, undefined, failedStep.agent_id);
          } else {
            // 如果没有找到失败的步骤，从头开始
            await triggerAnalysis(task.id);
          }

          // 刷新工作流状态并启动轮询，让 UI 更新
          await fetchWorkflow(task.id);
        }
      } catch (error) {
        console.error('继续执行失败:', error);
      }
    }
  };

  const handleStartEdit = (task: Task) => {
    setEditingId(task.id);
    setEditingTitle(task.title);
  };

  const handleSaveEdit = async (taskId: string) => {
    if (!editingTitle.trim()) {
      setEditingId(null);
      return;
    }
    try {
      const updated = await tasksApi.update(taskId, { title: editingTitle.trim() });
      setHistoryTasks((prev) => prev.map((t) => (t.id === taskId ? updated : t)));
    } catch {
      console.error('编辑标题失败');
    }
    setEditingId(null);
    setEditingTitle('');
  };

  const handleConfirmDelete = (taskId: string, title: string) => {
    setDeleteModal({ open: true, taskId, title });
  };

  const handleDeleteConfirmed = async () => {
    const { taskId } = deleteModal;
    setDeleteModal({ open: false, taskId: '', title: '' });
    try {
      await tasksApi.remove(taskId);
      setHistoryTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (error) {
      console.error('删除任务失败:', error);
      const msg = error instanceof Error ? error.message : '删除失败，请稍后重试';
      setHistoryError(msg);
      setTimeout(() => setHistoryError(''), 4000);
    }
  };

  // Filter and sort history tasks
  const filteredHistory = historyTasks
    .filter((t) => {
      const matchSearch =
        !historySearch ||
        t.title.toLowerCase().includes(historySearch.toLowerCase()) ||
        t.description.toLowerCase().includes(historySearch.toLowerCase());
      const matchFilter = historyFilter === 'all' || t.status === historyFilter;
      return matchSearch && matchFilter;
    })
    .sort((a, b) => {
      const dateA = a.updatedAt || a.createdAt || '';
      const dateB = b.updatedAt || b.createdAt || '';
      return dateB.localeCompare(dateA);
    });

  const statusCounts = historyTasks.reduce(
    (acc, t) => {
      acc[t.status] = (acc[t.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div className="card">
      {/* History Modal */}
      {showHistory &&
        createPortal(
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              width: '100vw',
              height: '100vh',
              background: 'rgba(0,0,0,0.65)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 99999,
            }}
            onClick={() => setShowHistory(false)}
          >
            <div
              style={{
                width: 560,
                maxHeight: '85vh',
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 16,
                boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div
                style={{
                  padding: '18px 20px 14px',
                  borderBottom: '1px solid var(--border)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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
                    <Clock size={16} style={{ color: 'var(--accent-red)' }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
                      历史方案
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                      {historyTasks.length} 个方案
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setShowHistory(false)}
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
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
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <X size={18} />
                </button>
              </div>

              {/* Search */}
              <div style={{ padding: '12px 20px' }}>
                <div
                  style={{
                    position: 'relative',
                  }}
                >
                  <Search
                    size={14}
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
                    value={historySearch}
                    onChange={(e) => setHistorySearch(e.target.value)}
                    placeholder="搜索历史方案..."
                    style={{
                      width: '100%',
                      padding: '8px 32px 8px 34px',
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
                  {historySearch && (
                    <button
                      onClick={() => setHistorySearch('')}
                      style={{
                        position: 'absolute',
                        right: 8,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'rgba(100,116,139,0.2)',
                        border: 'none',
                        borderRadius: '50%',
                        width: 20,
                        height: 20,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        color: 'var(--text-tertiary)',
                        padding: 0,
                      }}
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* Filter pills */}
              <div style={{ padding: '0 20px 12px', display: 'flex', gap: 6 }}>
                {[
                  { key: 'all', label: '全部', count: historyTasks.length },
                  { key: 'pending', label: '待处理', count: statusCounts.pending || 0 },
                  { key: 'analyzing', label: '分析中', count: statusCounts.analyzing || 0 },
                  { key: 'completed', label: '已完成', count: statusCounts.completed || 0 },
                  { key: 'failed', label: '失败', count: statusCounts.failed || 0 },
                ].map((item) => (
                  <button
                    key={item.key}
                    onClick={() => setHistoryFilter(item.key)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 16,
                      fontSize: 11,
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      fontWeight: historyFilter === item.key ? 600 : 400,
                      background:
                        historyFilter === item.key
                          ? 'rgba(59,130,246,0.2)'
                          : 'rgba(100,116,139,0.1)',
                      border:
                        historyFilter === item.key
                          ? '1px solid rgba(59,130,246,0.35)'
                          : '1px solid transparent',
                      color:
                        historyFilter === item.key ? 'var(--accent-blue)' : 'var(--text-tertiary)',
                      transition: 'all 0.15s',
                    }}
                  >
                    {item.label}
                    {item.count > 0 && (
                      <span style={{ marginLeft: 3, opacity: 0.6, fontSize: 10 }}>{item.count}</span>
                    )}
                  </button>
                ))}
              </div>

              {/* Task list */}
              <div
                className="history-list"
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  minHeight: 0,
                  borderTop: '1px solid var(--border)',
                }}
              >
                {historyLoading ? (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: 48,
                    }}
                  >
                    <LoaderCircle
                      size={24}
                      className="animate-spin"
                      style={{ color: 'var(--accent-blue)' }}
                    />
                  </div>
                ) : filteredHistory.length === 0 ? (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: 48,
                      gap: 8,
                    }}
                  >
                    <Search size={20} style={{ color: 'var(--text-tertiary)', opacity: 0.3 }} />
                    <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                      {historyTasks.length === 0 ? '暂无历史方案' : '无匹配方案'}
                    </span>
                  </div>
                ) : (
                  filteredHistory.map((task) => {
                    const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
                    const isEditing = editingId === task.id;

                    return (
                      <div
                        key={task.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 12,
                          padding: '12px 20px',
                          borderBottom: '1px solid rgba(255,255,255,0.04)',
                          cursor: isEditing ? 'default' : 'pointer',
                          transition: 'background 0.1s',
                        }}
                        onClick={() => !isEditing && handleSelectHistoryTask(task)}
                        onMouseEnter={(e) => {
                          if (!isEditing)
                            e.currentTarget.style.background = 'rgba(59,130,246,0.05)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = 'transparent';
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
                                if (e.key === 'Escape') setEditingId(null);
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
                                padding: '1px 6px',
                                borderRadius: 8,
                                background: cfg.bg,
                                color: cfg.color,
                                fontWeight: 500,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 3,
                              }}
                            >
                              {cfg.icon}
                              {cfg.label}
                            </span>
                            <span style={{ fontSize: 10, color: 'var(--text-tertiary)', opacity: 0.6 }}>
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
                              gap: 4,
                              flexShrink: 0,
                              opacity: 0,
                              transition: 'opacity 0.15s',
                            }}
                            className="task-actions"
                            onMouseEnter={(e) => e.stopPropagation()}
                          >
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleStartEdit(task);
                              }}
                              title="编辑"
                              style={{
                                width: 32,
                                height: 32,
                                borderRadius: 6,
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--text-tertiary)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                transition: 'all 0.15s',
                                fontSize: 0,
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
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSelectHistoryTask(task);
                              }}
                              title="继续"
                              style={{
                                width: 32,
                                height: 32,
                                borderRadius: 6,
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--text-tertiary)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                transition: 'all 0.15s',
                                fontSize: 0,
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
                              <Play size={14} />
                            </button>
                            <button
                              onClick={(e) => e.stopPropagation()}
                              title="分享"
                              style={{
                                width: 32,
                                height: 32,
                                borderRadius: 6,
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--text-tertiary)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                transition: 'all 0.15s',
                                fontSize: 0,
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
                              <LinkIcon size={14} />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleConfirmDelete(task.id, task.title);
                              }}
                              title="删除"
                              style={{
                                width: 32,
                                height: 32,
                                borderRadius: 6,
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--text-tertiary)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                transition: 'all 0.15s',
                                fontSize: 0,
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
                              <Trash2 size={14} />
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

              {/* Footer */}
              <div
                style={{
                  padding: '10px 20px',
                  borderTop: '1px solid var(--border)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: 11,
                  color: 'var(--text-tertiary)',
                }}
              >
                <span>
                  {filteredHistory.length} / {historyTasks.length} 个方案
                </span>
                <span style={{ opacity: 0.6 }}>按 ESC 关闭</span>
              </div>
            </div>

            {/* CSS for hover actions */}
            <style>{`
              .task-actions { opacity: 0 !important; }
              div:hover > .task-actions { opacity: 1 !important; }
              .history-list::-webkit-scrollbar { width: 6px; }
              .history-list::-webkit-scrollbar-track { background: transparent; }
              .history-list::-webkit-scrollbar-thumb { background: rgba(100,116,139,0.3); border-radius: 3px; }
              .history-list::-webkit-scrollbar-thumb:hover { background: rgba(100,116,139,0.5); }
            `}</style>
          </div>,
          document.body,
        )}

      {/* Delete Confirmation Modal */}
      {deleteModal.open &&
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
            onClick={() => setDeleteModal({ open: false, taskId: '', title: '' })}
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
                确认删除
              </div>
              <div
                style={{
                  fontSize: 13,
                  color: 'var(--text-secondary)',
                  lineHeight: 1.6,
                  marginBottom: 20,
                }}
              >
                确认删除任务 "{deleteModal.title}"?
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  onClick={() => setDeleteModal({ open: false, taskId: '', title: '' })}
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
                  onClick={handleDeleteConfirmed}
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

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="card-title">创新分析</div>

        <div style={{ position: 'relative' }} ref={selectorRef}>
          <button
            onClick={() => setShowKbSelector(!showKbSelector)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              fontSize: 11,
              padding: '5px 12px',
              background: selectedBaseIds.size > 0 ? 'rgba(59,130,246,0.12)' : 'transparent',
              color: selectedBaseIds.size > 0 ? 'var(--accent)' : 'var(--text-secondary)',
              border: `1px solid ${selectedBaseIds.size > 0 ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 6,
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
          >
            <i className="fa-solid fa-database" style={{ fontSize: 11 }} />
            导入知识库
            {selectedBaseIds.size > 0 && (
              <span
                style={{
                  background: 'var(--accent)',
                  color: '#fff',
                  borderRadius: 10,
                  padding: '0 6px',
                  fontSize: 10,
                  lineHeight: '16px',
                }}
              >
                {selectedBaseIds.size}
              </span>
            )}
            <i
              className="fa-solid fa-chevron-down"
              style={{
                fontSize: 8,
                marginLeft: 2,
                transform: showKbSelector ? 'rotate(180deg)' : 'none',
                transition: 'transform 0.15s',
              }}
            />
          </button>

          {showKbSelector && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: 4,
                width: 280,
                maxHeight: 300,
                overflowY: 'auto',
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                zIndex: 100,
                padding: 4,
              }}
            >
              {loadingBases ? (
                <div
                  style={{
                    padding: 20,
                    textAlign: 'center',
                    color: 'var(--text-tertiary)',
                    fontSize: 12,
                  }}
                >
                  <i
                    className="fa-solid fa-circle-notch fa-spin"
                    style={{ display: 'block', fontSize: 20, marginBottom: 8 }}
                  />
                  加载知识库...
                </div>
              ) : bases.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center' }}>
                  <i
                    className="fa-solid fa-database"
                    style={{
                      display: 'block',
                      fontSize: 24,
                      color: 'var(--text-tertiary)',
                      marginBottom: 8,
                    }}
                  />
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    {loadError || '暂无知识库'}
                  </div>
                  <a href="/knowledge" style={{ fontSize: 11, color: 'var(--accent)' }}>
                    前往创建{' '}
                    <i className="fa-solid fa-arrow-right" style={{ fontSize: 9 }} />
                  </a>
                </div>
              ) : (
                <>
                  <div style={{ padding: '6px 10px', fontSize: 11, color: 'var(--text-tertiary)' }}>
                    选择知识库作为分析参考
                  </div>
                  {bases.map((base) => {
                    const active = selectedBaseIds.has(base.id);
                    return (
                      <div
                        key={base.id}
                        onClick={() => toggleBase(base.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '8px 10px',
                          borderRadius: 6,
                          cursor: 'pointer',
                          background: active ? 'rgba(59,130,246,0.1)' : 'transparent',
                          color: active ? 'var(--accent)' : 'var(--text-primary)',
                          fontSize: 13,
                          transition: 'all 0.1s',
                        }}
                      >
                        <i
                          className={`fa-solid ${active ? 'fa-check-circle' : 'fa-circle'}`}
                          style={{
                            fontSize: 14,
                            color: active ? 'var(--accent)' : 'var(--text-tertiary)',
                          }}
                        />
                        <span style={{ flex: 1 }}>{base.name}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                          {base.itemCount ?? base.documentCount ?? 0}
                        </span>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Selected bases tags */}
      {selectedBases.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {selectedBases.map((base) => (
            <span
              key={base.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '3px 10px 3px 8px',
                borderRadius: 14,
                fontSize: 12,
                background: 'var(--accent)',
                color: '#fff',
                userSelect: 'none',
              }}
            >
              <i className="fa-solid fa-check" style={{ fontSize: 10 }} />
              {base.name}
              <span style={{ fontSize: 10, opacity: 0.7 }}>
                ({base.itemCount ?? base.documentCount ?? 0})
              </span>
              <i
                className="fa-solid fa-xmark"
                style={{ fontSize: 11, cursor: 'pointer', opacity: 0.7, marginLeft: 2 }}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleBase(base.id);
                }}
              />
            </span>
          ))}
        </div>
      )}

      {/* Submit error */}
      {submitError && (
        <div
          className="card-enter"
          style={{
            background: 'rgba(248,113,113,0.08)',
            border: '1px solid rgba(248,113,113,0.25)',
            borderRadius: 8,
            padding: '8px 12px',
            marginBottom: 12,
            fontSize: 13,
            color: 'var(--accent-red)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <i className="fa-solid fa-circle-exclamation" style={{ fontSize: 14 }} />
          {submitError}
          <span
            style={{ marginLeft: 'auto', cursor: 'pointer', opacity: 0.6 }}
            onClick={() => setSubmitError('')}
          >
            <i className="fa-solid fa-xmark" style={{ fontSize: 12 }} />
          </span>
        </div>
      )}

      {/* Description textarea */}
      <textarea
        value={description}
        onChange={(e) => {
          setDescription(e.target.value);
          setSubmitError('');
        }}
        placeholder="输入文字，点击开始进行分析"
        style={{
          width: '100%',
          background: 'rgba(0,0,0,0.3)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: 12,
          marginBottom: 12,
          minHeight: 60,
          fontSize: 14,
          color: 'var(--text-primary)',
          resize: 'vertical',
          outline: 'none',
          fontFamily: 'inherit',
          opacity: isRunning || submitting ? 0.6 : 1,
        }}
        disabled={isRunning || submitting}
      />

      {/* Bottom actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={handleNewTask}
            title="新建任务"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 36,
              height: 36,
              borderRadius: 8,
              background: 'transparent',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <i className="fa-solid fa-plus" style={{ fontSize: 14 }} />
          </button>

          <button
            onClick={() => setShowHistory(true)}
            title="历史方案"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 36,
              height: 36,
              borderRadius: 8,
              background: 'transparent',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <i className="fa-solid fa-clock-rotate-left" style={{ fontSize: 14 }} />
          </button>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!description.trim() || submitting || isRunning}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 20px',
            borderRadius: 8,
            background: 'var(--accent)',
            color: '#fff',
            fontSize: 14,
            fontWeight: 500,
            border: 'none',
            cursor: description.trim() && !submitting && !isRunning ? 'pointer' : 'not-allowed',
            opacity: !description.trim() || submitting || isRunning ? 0.5 : 1,
            transition: 'all 0.15s',
            fontFamily: 'inherit',
          }}
        >
          {submitting ? (
            <>
              <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 14 }} />
              分析中...
            </>
          ) : isRunning ? (
            <>
              <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: 14 }} />
              运行中...
            </>
          ) : (
            <>
              <i className="fa-solid fa-play" style={{ fontSize: 12 }} />
              开始分析
            </>
          )}
        </button>
      </div>
    </div>
  );
}
