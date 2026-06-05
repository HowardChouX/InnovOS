import { useEffect, useRef } from 'react';
import { useTaskStore } from '../../store/useTaskStore';

const statusColors: Record<string, string> = {
  pending: '#f59e0b',
  analyzing: '#3b82f6',
  completed: '#10b981',
  failed: '#ef4444',
};

const statusLabels: Record<string, string> = {
  pending: '待处理',
  analyzing: '分析中',
  completed: '已完成',
  failed: '失败',
};

export function TaskList() {
  const tasks = useTaskStore((s) => s.tasks);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const selectTask = useTaskStore((s) => s.selectTask);
  const deleteTask = useTaskStore((s) => s.deleteTask);
  const loading = useTaskStore((s) => s.loading);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      fetchTasks();
    }
  }, [fetchTasks]);

  if (tasks.length === 0 && !loading) return null;

  return (
    <div className="card" style={{ padding: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
          我的任务 <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>({tasks.length})</span>
        </div>
        <button
          onClick={() => fetchTasks()}
          style={{
            background: 'none', border: 'none', color: 'var(--text-tertiary)',
            cursor: 'pointer', fontSize: 11, fontFamily: 'inherit',
          }}
        >
          &#x21bb; 刷新
        </button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflow: 'auto' }}>
        {tasks.map((task) => (
          <div
            key={task.id}
            onClick={() => selectTask(task.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
              borderRadius: 6, cursor: 'pointer', fontSize: 12,
              background: selectedTaskId === task.id ? 'rgba(59,130,246,0.12)' : 'transparent',
              border: selectedTaskId === task.id ? '1px solid rgba(59,130,246,0.3)' : '1px solid transparent',
              transition: 'all 0.1s ease',
            }}
          >
            <span style={{
              width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
              background: statusColors[task.status] || '#666',
            }} />
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-primary)' }}>
              {task.title}
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)', flexShrink: 0 }}>
              {statusLabels[task.status] || task.status}
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); if (confirm('确认删除此任务?')) deleteTask(task.id); }}
              style={{
                background: 'none', border: 'none', color: 'var(--text-tertiary)',
                cursor: 'pointer', fontSize: 12, padding: '2px 4px', fontFamily: 'inherit',
                opacity: 0, transition: 'opacity 0.1s',
              }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '0'}
              className="task-delete-btn"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
