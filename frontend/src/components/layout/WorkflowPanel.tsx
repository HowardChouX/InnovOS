import { useWorkflowStore } from '../../store/useWorkflowStore';
import { WORKFLOW_STEPS } from '../../types/workflow';

const STEP_NUMBERS = ['①', '②', '③', '④', '⑤'];

const STATUS_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '等待中', color: 'var(--text-tertiary)', bg: 'rgba(100,116,139,0.1)' },
  running: { label: '运行中', color: 'var(--accent-blue)', bg: 'rgba(96,165,250,0.15)' },
  completed: { label: '已完成', color: 'var(--accent-green)', bg: 'rgba(74,222,128,0.15)' },
  failed: { label: '失败', color: 'var(--accent-red)', bg: 'rgba(248,113,113,0.15)' },
};

export function WorkflowPanel() {
  const { currentPhase, phaseStatus, isRunning } = useWorkflowStore();
  const hasActiveTask = useWorkflowStore((s) => s.workflow !== null);

  if (!isRunning && !hasActiveTask) return null;

  return (
    <aside style={{
      width: 200,
      background: 'var(--bg-panel)',
      borderLeft: '1px solid var(--border-light)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 14px',
        borderBottom: '1px solid var(--border-light)',
        fontSize: 12,
        fontWeight: 600,
        color: 'var(--text-primary)',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        <i className="fa-solid fa-diagram-project" style={{ fontSize: 11, color: 'var(--accent-blue)' }} />
        流程步骤状态
      </div>

      {/* Steps list */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '8px 0',
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
      }}>
        {WORKFLOW_STEPS.map((step, i) => {
          const status: string = phaseStatus[step.phaseId] || 'pending';
          const cfg = STATUS_STYLE[status] || STATUS_STYLE.pending;
          const isCurrent = step.phaseId === currentPhase;
          const isDone = status === 'completed';

          return (
            <div key={step.phaseId} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '9px 14px',
              borderLeft: '3px solid transparent',
              borderLeftColor: isCurrent ? 'var(--accent-blue)' : 'transparent',
              background: isCurrent ? 'rgba(96,165,250,0.05)' : 'transparent',
              transition: 'all 0.15s',
            }}>
              {/* Number circle */}
              <div style={{
                width: 22,
                height: 22,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 700,
                flexShrink: 0,
                background: isDone ? cfg.color : 'var(--bg-card)',
                border: `2px solid ${cfg.color}`,
                color: isDone ? '#fff' : cfg.color,
                transition: 'all 0.3s',
              }}>
                {isDone ? (
                  <i className="fa-solid fa-check" style={{ fontSize: 8 }} />
                ) : isCurrent ? (
                  <div style={{
                    width: 6, height: 6,
                    border: `2px solid ${cfg.color}`,
                    borderTopColor: 'transparent',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite',
                  }} />
                ) : (
                  i + 1
                )}
              </div>

              {/* Label + Status */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 12,
                  fontWeight: isCurrent ? 600 : 400,
                  color: isCurrent ? 'var(--text-primary)' : 'var(--text-secondary)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {step.label}
                </div>
                <div style={{
                  fontSize: 10,
                  color: 'var(--text-tertiary)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {step.description}
                </div>
              </div>

              {/* Status badge */}
              <span style={{
                fontSize: 10,
                padding: '1px 6px',
                borderRadius: 4,
                background: cfg.bg,
                color: cfg.color,
                flexShrink: 0,
              }}>
                {cfg.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Bottom status bar */}
      {isRunning && (
        <div style={{
          padding: '8px 14px',
          borderTop: '1px solid var(--border-light)',
          fontSize: 10,
          color: 'var(--text-tertiary)',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--accent-green)',
            display: 'inline-block',
          }} />
          分析进行中...
        </div>
      )}
    </aside>
  );
}
