import { useMemo } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { DemandPortraitView } from './DemandPortraitView';
import { ProblemModelingView } from './ProblemModelingView';
import { PatentSearchView } from './PatentSearchView';
import { SolutionGenView } from './SolutionGenView';
import { EvaluationView } from './EvaluationView';
import { CompletedView } from './CompletedView';
import type { WorkflowState } from '../../types/workflow';
import { WORKFLOW_STEPS } from '../../types/workflow';

const PHASE_TO_AGENT: Record<string, string> = {
  demand_portrait: 'agent1',
  problem_modeling: 'agent2',
  patent_search: 'agent5',
  solution_gen: 'agent3',
  evaluation: 'agent4',
  completed: 'agent6',
};

function getStepOutput(workflow: WorkflowState, phaseId: string): any {
  const agentId = PHASE_TO_AGENT[phaseId];
  if (!agentId) return null;
  const step = workflow.steps.find(s => s.agentId === agentId);
  if (!step || !step.output) return null;
  try { return JSON.parse(step.output); } catch { return step.output; }
}

function EmptyState({ msg, icon }: { msg: string; icon: string }) {
  return (
    <div className="card" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      minHeight: 260, padding: 40, height: '100%',
    }}>
      <i className={icon} style={{
        fontSize: 48, color: 'var(--text-tertiary)', opacity: 0.3,
        marginBottom: 16, display: 'block',
      }} />
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>{msg}</p>
    </div>
  );
}

const PHASE_VIEWS: Record<string, React.ComponentType<{ output: any }>> = {
  demand_portrait: DemandPortraitView,
  problem_modeling: ProblemModelingView,
  patent_search: PatentSearchView,
  solution_gen: SolutionGenView,
  evaluation: EvaluationView,
  completed: CompletedView,
};

export function WorkflowStepResults() {
  const { workflow, currentPhase, phaseStatus } = useWorkflowStore();
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);

  // 等待评分时，显示最后一个已完成的阶段（让用户看到结果并确认）
  const displayPhase = useMemo(() => {
    if (!workflow) return currentPhase;
    if (workflow.status === 'awaiting_rating') {
      const order = ['demand_portrait', 'problem_modeling', 'patent_search', 'solution_gen', 'evaluation'];
      let lastComplete = '';
      for (const phase of order) {
        if (phaseStatus[phase] === 'completed') {
          lastComplete = phase;
        }
      }
      return lastComplete || 'demand_portrait';
    }
    return currentPhase;
  }, [workflow, currentPhase, phaseStatus]);

  const stepInfo = WORKFLOW_STEPS.find(s => s.phaseId === displayPhase);

  const currentOutput = useMemo(() => {
    if (!workflow) return null;
    return getStepOutput(workflow, displayPhase);
  }, [workflow, displayPhase]);

  if (!selectedTaskId) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <EmptyState msg="输入文字，点击开始进行分析" icon="fa-solid fa-hand-pointer" />
      </div>
    );
  }

  if (!workflow) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <EmptyState msg="暂无运行中的工作流" icon="fa-solid fa-diagram-project" />
      </div>
    );
  }

  const isRunning = phaseStatus[displayPhase] === 'running' && workflow.status !== 'awaiting_rating';

  // 运行中且无输出时，显示当前步骤名称和等待提示
  if (isRunning && !currentOutput) {
    return (
      <div className="card" style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: 260, padding: 40, height: '100%',
      }}>
        <i className={stepInfo?.icon || 'fa-solid fa-circle-notch fa-spin'} style={{
          fontSize: 36, color: stepInfo?.color || 'var(--accent-blue)', opacity: 0.6,
          marginBottom: 16,
        }} />
        <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 8px' }}>
          {stepInfo?.label || '分析中'}
        </p>
        <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: 0 }}>
          {stepInfo?.description || '正在执行分析...'}
        </p>
        <div style={{ marginTop: 16 }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 20, color: 'var(--accent-blue)' }} />
        </div>
      </div>
    );
  }

  const PhaseComponent = PHASE_VIEWS[displayPhase];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, height: '100%' }}>
      {PhaseComponent ? (
        <PhaseComponent output={currentOutput} />
      ) : (
        <EmptyState msg="未知阶段" icon="fa-solid fa-question-circle" />
      )}
    </div>
  );
}

export { EmptyState, getStepOutput };
