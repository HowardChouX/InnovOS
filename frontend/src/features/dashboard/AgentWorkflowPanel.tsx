import type { ReactNode } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { WORKFLOW_STEPS } from '../../types/workflow';
import type { AgentStatus } from '../../types/workflow';

const statusConfig: Record<AgentStatus, { color: string; bg: string; label: string }> = {
  completed: { color: 'var(--accent-green)', bg: 'rgba(74,222,128,0.15)', label: '已完成' },
  running: { color: 'var(--accent-blue)', bg: 'rgba(96,165,250,0.15)', label: '运行中' },
  pending: { color: 'var(--text-tertiary)', bg: 'rgba(100,116,139,0.1)', label: '等待中' },
  failed: { color: 'var(--accent-red)', bg: 'rgba(248,113,113,0.15)', label: '失败' },
};

const workflowStatusConfig: Record<string, { color: string; bg: string; label: string }> = {
  completed: { color: 'var(--accent-green)', bg: 'rgba(74,222,128,0.15)', label: '已完成' },
  running: { color: 'var(--accent-blue)', bg: 'rgba(96,165,250,0.15)', label: '运行中' },
  failed: { color: 'var(--accent-red)', bg: 'rgba(248,113,113,0.15)', label: '失败' },
  idle: { color: 'var(--text-tertiary)', bg: 'rgba(100,116,139,0.1)', label: '空闲' },
};

function TimelineStep({
  agent,
  step,
  index,
  isLast,
}: {
  agent: typeof WORKFLOW_STEPS[number];
  step: { status: AgentStatus; description?: string; duration?: string };
  index: number;
  isLast: boolean;
}) {
  const cfg = statusConfig[step.status] || statusConfig.pending;
  const isCompleted = step.status === 'completed';
  const isRunning = step.status === 'running';
  const isFailed = step.status === 'failed';

  return (
    <div style={{ display: 'flex', gap: 12, position: 'relative' }}>
      {/* Timeline column */}
      <div style={{
        width: 24, display: 'flex', flexDirection: 'column', alignItems: 'center',
        flexShrink: 0,
      }}>
        {/* Node */}
        <div style={{
          width: 20, height: 20, borderRadius: '50%', marginTop: 12,
          background: isCompleted ? cfg.color : 'var(--bg-card)',
          border: `2px solid ${cfg.color}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, color: isCompleted ? '#fff' : cfg.color,
          zIndex: 1,
          boxShadow: isRunning ? `0 0 0 3px ${cfg.color}30` : 'none',
          animation: isRunning ? 'pulse-ring 1.5s ease-in-out infinite' : 'none',
          transition: 'all 0.3s ease',
        }}>
          {isCompleted ? '✓' : isRunning ? (
            <div style={{
              width: 8, height: 8, border: `2px solid ${cfg.color}`,
              borderTopColor: 'transparent', borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }} />
          ) : isFailed ? '✕' : (index + 1)}
        </div>
        {/* Line */}
        {!isLast && (
          <div style={{
            width: 1, flex: 1, minHeight: 20,
            background: isCompleted ? cfg.color : 'var(--border)',
            transition: 'background 0.3s ease',
          }} />
        )}
      </div>

      {/* Content */}
      <div style={{
        flex: 1, padding: '8px 0',
        opacity: step.status === 'pending' ? 0.5 : 1,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
            {agent.label}
          </div>
          <span style={{
            fontSize: 10, padding: '2px 8px', borderRadius: 4,
            background: cfg.bg, color: cfg.color,
          }}>
            {cfg.label}
          </span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
          {step.description || '等待执行...'}
        </div>
        {step.duration && (
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
            耗时 {step.duration}
          </div>
        )}
      </div>
    </div>
  );
}

function DefaultStateView() {
  const defaultSteps = WORKFLOW_STEPS.map((agent) => ({
    status: 'pending' as const,
    description: agent.description,
    duration: undefined,
  }));

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {WORKFLOW_STEPS.map((agent, i) => (
          <TimelineStep
            key={agent.phaseId}
            agent={agent}
            step={defaultSteps[i]}
            index={i}
            isLast={i === WORKFLOW_STEPS.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

function WorkflowProgressView({ workflow }: { workflow: NonNullable<ReturnType<typeof useWorkflowStore.getState>['workflow']> }) {
  const steps = workflow.steps || [];

  const getStepForAgent = (phaseId: string) => {
    return steps.find(s => s.agentId === phaseId) || {
      status: 'pending' as AgentStatus,
      description: undefined,
      duration: undefined,
    };
  };

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {WORKFLOW_STEPS.map((agent, i) => (
          <TimelineStep
            key={agent.phaseId}
            agent={agent}
            step={getStepForAgent(agent.phaseId)}
            index={i}
            isLast={i === WORKFLOW_STEPS.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

export function AgentWorkflowPanel() {
  const workflow = useWorkflowStore((s) => s.workflow);

  const wrap = (content: ReactNode) => (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%', minHeight: 0 }}>
<div className="card-title">
         流程步骤状态
        {workflow && (
          <span style={{
            marginLeft: 'auto',
            fontSize: 10, padding: '2px 8px', borderRadius: 4,
            ...(() => {
              const cfg = workflowStatusConfig[workflow.status] || workflowStatusConfig.idle;
              return { background: cfg.bg, color: cfg.color };
            })(),
          }}>
            {workflowStatusConfig[workflow.status]?.label || workflow.status}
          </span>
        )}
      </div>
      {content}
    </div>
  );

  if (!workflow) {
    return wrap(<DefaultStateView />);
  }

  return wrap(<WorkflowProgressView workflow={workflow} />);
}
