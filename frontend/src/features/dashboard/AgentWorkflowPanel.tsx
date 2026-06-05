import type { ReactNode } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';

const statusConfig: Record<string, { color: string; bg: string; label: string; icon: string }> = {
  completed: { color: 'var(--accent-green)', bg: 'rgba(74,222,128,0.15)', label: '已完成', icon: '✓' },
  running: { color: 'var(--accent-blue)', bg: 'rgba(96,165,250,0.15)', label: '运行中', icon: '◌' },
  pending: { color: 'var(--text-tertiary)', bg: 'rgba(100,116,139,0.1)', label: '等待中', icon: '○' },
  failed: { color: 'var(--accent-red)', bg: 'rgba(248,113,113,0.15)', label: '失败', icon: '✕' },
};

export function AgentWorkflowPanel() {
  const workflow = useWorkflowStore((s) => s.workflow);
  const loading = useWorkflowStore((s) => s.loading);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);

  const wrap = (content: ReactNode) => (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', width: '100%', minHeight: 300 }}>
      <div className="card-title">
        <i className="fa-solid fa-robot" style={{ fontSize: 12, color: 'var(--accent-blue)' }} />
        多Agent协同工作流
        {workflow && (
          <span style={{
            marginLeft: 'auto',
            fontSize: 10, padding: '2px 8px', borderRadius: 4,
            ...(() => {
              const cfg = statusConfig[workflow.status] || statusConfig.pending;
              return { background: cfg.bg, color: cfg.color };
            })(),
          }}>
            {statusConfig[workflow.status]?.label || workflow.status}
          </span>
        )}
      </div>
      {content}
    </div>
  );

  if (!selectedTaskId) {
    return wrap(
      <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-tertiary)', marginTop: 40 }}>
        选择一个任务查看工作流
      </div>
    );
  }

  const steps = workflow?.steps || [];

  return wrap(
    <div style={{ flex: 1, overflowY: 'auto' }}>
      {loading && steps.length === 0 ? (
        <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-tertiary)', marginTop: 40 }}>加载中...</div>
      ) : steps.length === 0 ? (
        <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-tertiary)', marginTop: 40 }}>暂无工作流数据</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {steps.map((step, idx) => {
            const cfg = statusConfig[step.status] || statusConfig.pending;
            const isLast = idx === steps.length - 1;
            return (
              <div key={step.agentId} style={{ display: 'flex', gap: 12, position: 'relative' }}>
                {/* Timeline column */}
                <div style={{
                  width: 24, display: 'flex', flexDirection: 'column', alignItems: 'center',
                  flexShrink: 0,
                }}>
                  {/* Node */}
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%', marginTop: 12,
                    background: step.status === 'completed' ? cfg.color : 'var(--bg-card)',
                    border: `2px solid ${cfg.color}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, color: step.status === 'completed' ? '#fff' : cfg.color,
                    zIndex: 1,
                  }}>
                    {cfg.icon}
                  </div>
                  {/* Line */}
                  {!isLast && (
                    <div style={{
                      width: 1, flex: 1, minHeight: 20,
                      background: step.status === 'completed' ? cfg.color : 'var(--border)',
                    }} />
                  )}
                </div>

                {/* Content */}
                <div style={{
                  flex: 1, padding: '10px 0',
                  opacity: step.status === 'pending' ? 0.5 : 1,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {step.agentLabel}
                    </div>
                    <span style={{
                      fontSize: 10, padding: '2px 8px', borderRadius: 4,
                      background: cfg.bg, color: cfg.color,
                    }}>
                      {cfg.label}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                    {step.description}
                  </div>
                  {step.duration && (
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                      耗时 {step.duration}
                    </div>
                  )}
                  {step.status === 'running' && (
                    <div style={{ fontSize: 10, color: 'var(--accent-blue)', marginTop: 4 }}>
                      预计剩余 5.2s
                    </div>
                  )}
                  {step.status === 'pending' && (
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>
                      预计等待 3.1s
                    </div>
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
