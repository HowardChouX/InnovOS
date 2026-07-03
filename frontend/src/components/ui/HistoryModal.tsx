import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useTaskStore } from '../../store/useTaskStore';
import type { Task, TaskStatus } from '../../types/task';

interface HistoryModalProps {
  show: boolean;
  onClose: () => void;
  onSelectTask?: (task: Task) => void;
}

function HistoryModal({ show, onClose, onSelectTask }: HistoryModalProps) {
  const tasks = useTaskStore((s) => s.tasks);
  const loading = useTaskStore((s) => s.loading);
  const deleteTask = useTaskStore((s) => s.deleteTask);
  const updateTask = useTaskStore((s) => s.updateTask);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);

  const [searchQuery, setSearchQuery] = useState('');
  const [filterCurrentVault, setFilterCurrentVault] = useState(false);
  const [filterHasData, setFilterHasData] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [showConfirmDelete, setShowConfirmDelete] = useState<string | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (show) {
      fetchTasks({ pageSize: 100 });
      setTimeout(() => searchInputRef.current?.focus(), 100);
    }
  }, [show, fetchTasks]);

  useEffect(() => {
    if (!show) {
      setSearchQuery('');
      setFilterCurrentVault(false);
      setFilterHasData(false);
      setEditingTaskId(null);
      setShowConfirmDelete(null);
    }
  }, [show]);

  const handleStartEdit = useCallback((task: Task) => {
    setEditingTaskId(task.id);
    setEditingTitle(task.title);
  }, []);

  const handleSaveEdit = useCallback(async (taskId: string) => {
    if (!editingTitle.trim()) {
      setEditingTaskId(null);
      return;
    }
    await updateTask(taskId, { title: editingTitle.trim() });
    setEditingTaskId(null);
    setEditingTitle('');
  }, [editingTitle, updateTask]);

  const handleCancelEdit = useCallback(() => {
    setEditingTaskId(null);
    setEditingTitle('');
  }, []);

  const handleDeleteTask = useCallback(async (taskId: string) => {
    await deleteTask(taskId);
    setShowConfirmDelete(null);
    fetchTasks({ pageSize: 100 });
  }, [deleteTask, fetchTasks]);

  const handleResumeTask = useCallback((task: Task) => {
    onSelectTask?.(task);
    onClose();
  }, [onSelectTask, onClose]);

  const getStatusConfig = useCallback((status: TaskStatus) => {
    switch (status) {
      case 'pending':
        return { color: '#f59e0b', label: '待处理', icon: 'fa-clock' };
      case 'analyzing':
        return { color: '#3b82f6', label: '分析中', icon: 'fa-spinner fa-spin' };
      case 'completed':
        return { color: '#10b981', label: '已完成', icon: 'fa-check-circle' };
      case 'failed':
        return { color: '#ef4444', label: '失败', icon: 'fa-times-circle' };
      default:
        return { color: '#6b7280', label: '未知', icon: 'fa-question-circle' };
    }
  }, []);

  const formatDate = useCallback((dateStr: string | null | undefined) => {
    if (!dateStr) return '';
    try {
      const d = dateStr.includes('T') ? new Date(dateStr) : new Date(dateStr.replace(' ', 'T') + 'Z');
      if (isNaN(d.getTime())) return '';

      const now = Date.now();
      const diffMs = now - d.getTime();
      const diffMin = Math.floor(diffMs / 60000);

      if (diffMin < 1) return '刚刚';
      if (diffMin < 60) return `${diffMin} 分钟前`;

      const diffHour = Math.floor(diffMin / 60);
      if (diffHour < 24) return `${diffHour} 小时前`;

      const diffDay = Math.floor(diffHour / 24);
      if (diffDay < 7) return `${diffDay} 天前`;

      if (diffDay < 30) return `${Math.floor(diffDay / 7)} 周前`;

      return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  }, []);

  const filteredTasks = tasks.filter((task) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      if (!task.title.toLowerCase().includes(query) && !task.description.toLowerCase().includes(query)) {
        return false;
      }
    }

    if (filterHasData && task.status !== 'completed') {
      return false;
    }

    return true;
  });

  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }, [onClose]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
  }, [onClose]);

  if (!show) return null;

  const modalContent = (
    <div
      ref={modalRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 99999,
      }}
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      tabIndex={-1}
    >
      <div
        style={{
          width: 520,
          maxHeight: '85vh',
          background: 'var(--bg-primary, #1a1a2e)',
          border: '1px solid var(--border, rgba(255,255,255,0.1))',
          borderRadius: 16,
          boxShadow: '0 24px 48px rgba(0,0,0,0.6)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 20px',
            borderBottom: '1px solid var(--border, rgba(255,255,255,0.1))',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: 18,
              fontWeight: 600,
              color: 'var(--text-primary, #ffffff)',
            }}
          >
            历史方案
          </h2>
          <button
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'transparent',
              border: 'none',
              color: 'var(--text-tertiary, #9ca3af)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
              e.currentTarget.style.color = 'var(--text-primary, #ffffff)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = 'var(--text-tertiary, #9ca3af)';
            }}
          >
            <i className="fa-solid fa-xmark" />
          </button>
        </div>

        {/* Search Bar */}
        <div style={{ padding: '12px 20px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 14px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid var(--border, rgba(255,255,255,0.1))',
              borderRadius: 10,
            }}
          >
            <i
              className="fa-solid fa-search"
              style={{ fontSize: 13, color: 'var(--text-tertiary, #9ca3af)' }}
            />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="搜索历史方案..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                fontSize: 13,
                color: 'var(--text-primary, #ffffff)',
                fontFamily: 'inherit',
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-tertiary, #9ca3af)',
                  cursor: 'pointer',
                  padding: 4,
                  fontSize: 12,
                }}
              >
                <i className="fa-solid fa-xmark" />
              </button>
            )}
          </div>
        </div>

        {/* Filters */}
        <div
          style={{
            padding: '0 20px 12px',
            display: 'flex',
            gap: 12,
            fontSize: 12,
            color: 'var(--text-secondary, #d1d5db)',
          }}
        >
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <input
              type="checkbox"
              checked={filterCurrentVault}
              onChange={(e) => setFilterCurrentVault(e.target.checked)}
              style={{
                width: 14,
                height: 14,
                borderRadius: 4,
                cursor: 'pointer',
                accentColor: 'var(--accent, #3b82f6)',
              }}
            />
            <span>仅当前知识库</span>
          </label>

          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            <input
              type="checkbox"
              checked={filterHasData}
              onChange={(e) => setFilterHasData(e.target.checked)}
              style={{
                width: 14,
                height: 14,
                borderRadius: 4,
                cursor: 'pointer',
                accentColor: 'var(--accent, #3b82f6)',
              }}
            />
            <span>仅已完成</span>
          </label>
        </div>

        {/* Task List */}
        <div
          style={{
            overflowY: 'auto',
            flex: 1,
            maxHeight: '50vh',
            borderTop: '1px solid var(--border, rgba(255,255,255,0.1))',
          }}
        >
          {loading ? (
            <div
              style={{
                padding: '60px 20px',
                textAlign: 'center',
                color: 'var(--text-tertiary, #9ca3af)',
              }}
            >
              <i
                className="fa-solid fa-circle-notch fa-spin"
                style={{ fontSize: 24, marginBottom: 12, display: 'block', opacity: 0.6 }}
              />
              <p style={{ margin: 0, fontSize: 13 }}>加载中...</p>
            </div>
          ) : filteredTasks.length === 0 ? (
            <div
              style={{
                padding: '60px 20px',
                textAlign: 'center',
                color: 'var(--text-tertiary, #9ca3af)',
              }}
            >
              <i
                className="fa-solid fa-folder-open"
                style={{ fontSize: 32, marginBottom: 12, display: 'block', opacity: 0.4 }}
              />
              <p style={{ margin: 0, fontSize: 13 }}>
                {searchQuery ? '没有找到匹配的方案' : '暂无历史方案'}
              </p>
            </div>
          ) : (
            filteredTasks.map((task) => {
              const statusCfg = getStatusConfig(task.status);
              const isEditing = editingTaskId === task.id;
              const isConfirmingDelete = showConfirmDelete === task.id;

              return (
                <div
                  key={task.id}
                  style={{
                    padding: '14px 20px',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  {/* Task Title and Status */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      marginBottom: 6,
                    }}
                  >
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: statusCfg.color,
                        flexShrink: 0,
                      }}
                    />
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
                        style={{
                          flex: 1,
                          padding: '6px 10px',
                          borderRadius: 6,
                          background: 'rgba(255,255,255,0.1)',
                          border: '1px solid var(--accent, #3b82f6)',
                          color: 'var(--text-primary, #ffffff)',
                          fontSize: 13,
                          fontWeight: 500,
                          outline: 'none',
                          fontFamily: 'inherit',
                        }}
                      />
                    ) : (
                      <span
                        style={{
                          flex: 1,
                          fontSize: 13,
                          fontWeight: 500,
                          color: 'var(--text-primary, #ffffff)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {task.title || '无标题'}
                      </span>
                    )}

                    {/* Status Badge */}
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: 10,
                        fontSize: 11,
                        background: `${statusCfg.color}20`,
                        color: statusCfg.color,
                        fontWeight: 500,
                      }}
                    >
                      {statusCfg.label}
                    </span>
                  </div>

                  {/* Timestamp and Actions */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      paddingLeft: 18,
                    }}
                  >
                    <span style={{ fontSize: 12, color: 'var(--text-tertiary, #6b7280)' }}>
                      {formatDate(task.updatedAt || task.createdAt)}
                    </span>

                    {!isEditing && !isConfirmingDelete && (
                      <div style={{ display: 'flex', gap: 2 }}>
                        {/* Edit Button */}
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
                            color: 'var(--text-tertiary, #6b7280)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 12,
                            transition: 'all 0.15s',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
                            e.currentTarget.style.color = 'var(--text-primary, #ffffff)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                            e.currentTarget.style.color = 'var(--text-tertiary, #6b7280)';
                          }}
                        >
                          <i className="fa-solid fa-pen" />
                        </button>

                        {/* Resume Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleResumeTask(task);
                          }}
                          title="继续此方案"
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 6,
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-tertiary, #6b7280)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 12,
                            transition: 'all 0.15s',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(59,130,246,0.2)';
                            e.currentTarget.style.color = '#3b82f6';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                            e.currentTarget.style.color = 'var(--text-tertiary, #6b7280)';
                          }}
                        >
                          <i className="fa-solid fa-play" />
                        </button>

                        {/* Share Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                          title="分享"
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 6,
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-tertiary, #6b7280)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 12,
                            transition: 'all 0.15s',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
                            e.currentTarget.style.color = 'var(--text-primary, #ffffff)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                            e.currentTarget.style.color = 'var(--text-tertiary, #6b7280)';
                          }}
                        >
                          <i className="fa-solid fa-link" />
                        </button>

                        {/* Delete Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowConfirmDelete(task.id);
                          }}
                          title="删除"
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 6,
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-tertiary, #6b7280)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 12,
                            transition: 'all 0.15s',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(239,68,68,0.2)';
                            e.currentTarget.style.color = '#ef4444';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                            e.currentTarget.style.color = 'var(--text-tertiary, #6b7280)';
                          }}
                        >
                          <i className="fa-solid fa-trash" />
                        </button>
                      </div>
                    )}

                    {/* Delete Confirmation */}
                    {isConfirmingDelete && (
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <span style={{ fontSize: 12, color: '#ef4444' }}>确定删除？</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteTask(task.id);
                          }}
                          style={{
                            padding: '4px 10px',
                            borderRadius: 6,
                            background: '#ef4444',
                            border: 'none',
                            color: '#fff',
                            fontSize: 11,
                            fontWeight: 500,
                            cursor: 'pointer',
                          }}
                        >
                          删除
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowConfirmDelete(null);
                          }}
                          style={{
                            padding: '4px 10px',
                            borderRadius: 6,
                            background: 'rgba(255,255,255,0.1)',
                            border: 'none',
                            color: 'var(--text-secondary, #d1d5db)',
                            fontSize: 11,
                            cursor: 'pointer',
                          }}
                        >
                          取消
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid var(--border, rgba(255,255,255,0.1))',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: 12,
            color: 'var(--text-tertiary, #6b7280)',
          }}
        >
          <span>
            {filteredTasks.length} / {tasks.length} 个方案
          </span>
          <span style={{ fontSize: 11, opacity: 0.6 }}>
            按 ESC 关闭
          </span>
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}

export default HistoryModal;
