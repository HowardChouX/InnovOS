import { useState, useEffect, useRef } from 'react';
import { useTaskStore } from '../../store/useTaskStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { WORKFLOW_STEPS } from '../../types/workflow';
import type { AgentStatus } from '../../types/workflow';

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

const PHASE_TO_AGENT: Record<string, string> = {
  demand_portrait: 'agent1',
  problem_modeling: 'agent2',
  patent_search: 'agent5',
  solution_gen: 'agent3',
  evaluation: 'agent4',
};

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  pending: { label: '待处理', color: 'var(--accent-yellow)', bg: 'rgba(251,191,36,0.12)', border: '#fbbf24' },
  analyzing: { label: '分析中', color: 'var(--accent-blue)', bg: 'rgba(59,130,246,0.12)', border: '#3b82f6' },
  completed: { label: '已完成', color: 'var(--accent-green)', bg: 'rgba(74,222,128,0.12)', border: '#22c55e' },
  failed: { label: '失败', color: 'var(--accent-red)', bg: 'rgba(248,113,113,0.12)', border: '#ef4444' },
};

const STEP_STATUS: Record<string, string> = {
  pending: 'rgba(255,255,255,0.08)',
  running: 'var(--accent-blue)',
  completed: 'var(--accent-green)',
  failed: 'var(--accent-red)',
};

function WorkflowStepsMini({ steps }: { steps: any[] }) {
  return (
    <div style={{ display: 'flex', gap: 2, marginTop: 6 }}>
      {WORKFLOW_STEPS.map((step) => {
        const agentId = PHASE_TO_AGENT[step.phaseId];
        const stepData = steps.find((s: any) => s.agentId === agentId);
        const s = stepData?.status || 'pending';
        return (
          <div
            key={step.phaseId}
            title={`${step.label}: ${s === 'completed' ? '已完成' : s === 'running' ? '运行中' : s === 'failed' ? '失败' : '等待中'}`}
            style={{
              flex: 1, height: 4, borderRadius: 2,
              background: STEP_STATUS[s] || STEP_STATUS.pending,
              transition: 'background 0.3s',
            }}
          />
        );
      })}
    </div>
  );
}

export function MyTasksPage() {
  const tasks = useTaskStore((s) => s.tasks);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const selectTask = useTaskStore((s) => s.selectTask);
  const loading = useTaskStore((s) => s.loading);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);
  const workflow = useWorkflowStore((s) => s.workflow);
  const initialized = useRef(false);

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      fetchTasks();
    }
  }, [fetchTasks]);

  const filtered = tasks.filter((t) => {
    const matchSearch = !search || t.title.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'all' || t.status === filter;
    return matchSearch && matchFilter;
  });

  const statusCounts = tasks.reduce((acc, t) => {
    acc[t.status] = (acc[t.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const workflowMap = new Map<string, any>();
  if (workflow) workflowMap.set(workflow.taskId, workflow);

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '20px 0' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>
          <i className="fa-solid fa-list-check" style={{ marginRight: 10, color: 'var(--accent-blue)' }} />
          我的任务
          <span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 6, fontSize: 14 }}>
            ({tasks.length})
          </span>
        </div>
        <button onClick={() => fetchTasks()} style={{
          background: 'none', border: 'none', color: 'var(--text-tertiary)',
          cursor: 'pointer', fontSize: 13, fontFamily: 'inherit', padding: '4px 8px',
        }}>
          <i className="fa-solid fa-arrows-rotate" style={{ fontSize: 12 }} />
        </button>
      </div>

      {/* Search */}
      <div style={{ position: 'relative', marginBottom: 12 }}>
        <i className="fa-solid fa-magnifying-glass" style={{
          position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
          fontSize: 12, color: 'var(--text-tertiary)',
        }} />
        <input
          value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索任务..."
          style={{
            width: '100%', padding: '8px 10px 8px 28px', borderRadius: 6,
            background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
            color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {[
          { key: 'all', label: '全部', count: tasks.length },
          { key: 'pending', label: '待处理', count: statusCounts.pending || 0 },
          { key: 'analyzing', label: '分析中', count: statusCounts.analyzing || 0 },
          { key: 'completed', label: '已完成', count: statusCounts.completed || 0 },
        ].map((item) => (
          <button key={item.key} onClick={() => setFilter(item.key)} style={{
            padding: '4px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
            background: filter === item.key ? 'var(--accent)' : 'transparent',
            border: 'none',
            color: filter === item.key ? '#fff' : 'var(--text-tertiary)',
            fontFamily: 'inherit', transition: 'all 0.15s',
          }}>
            {item.label}
            {item.count > 0 && <span style={{ opacity: 0.7, marginLeft: 3 }}>{item.count}</span>}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-tertiary)' }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 24, marginBottom: 12, display: 'block' }} />
          加载中...
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-tertiary)' }}>
          <i className="fa-solid fa-inbox" style={{ fontSize: 48, opacity: 0.3, marginBottom: 16, display: 'block' }} />
          {tasks.length === 0 ? '暂无任务' : '无匹配任务'}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map((task) => {
            const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
            const wf = workflowMap.get(task.id);
            const steps = wf?.steps || [];
            const isSelected = selectedTaskId === task.id;

            return (
              <div
                key={task.id}
                onClick={() => selectTask(task.id)}
                onMouseEnter={() => setHoveredId(task.id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{
                  background: 'var(--bg-card)',
                  border: `1px solid ${isSelected ? cfg.border : 'var(--border)'}`,
                  borderLeft: `3px solid ${cfg.border}`,
                  borderRadius: 8, padding: '12px 14px', cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 5,
                    background: cfg.color,
                  }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4,
                    }}>
                      {task.title}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{
                        fontSize: 10, padding: '2px 7px', borderRadius: 4,
                        background: cfg.bg, color: cfg.color,
                      }}>
                        {cfg.label}
                      </span>
                      {formatDate(task.createdAt) && (
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                          {formatDate(task.createdAt)}
                        </span>
                      )}
                      {steps.length > 0 && (
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                          {steps.filter((s: any) => s.status === 'completed').length}/{steps.length} 步
                        </span>
                      )}
                    </div>
                    {steps.length > 0 && (
                      <WorkflowStepsMini steps={steps} />
                    )}
                  </div>
                  {hoveredId === task.id && (
                    <button
                      onClick={(e) => { e.stopPropagation(); /* delete handler */ }}
                      style={{
                        background: 'rgba(248,113,113,0.1)',
                        border: '1px solid rgba(248,113,113,0.2)',
                        color: 'var(--accent-red)',
                        cursor: 'pointer', fontSize: 10,
                        padding: '2px 6px', borderRadius: 4, fontFamily: 'inherit', flexShrink: 0,
                      }}
                    >
                      <i className="fa-solid fa-trash-can" style={{ fontSize: 9 }} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
