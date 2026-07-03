import { useMemo } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { DemandPortraitView } from './DemandPortraitView';
import { ProblemModelingView } from './ProblemModelingView';
import { PatentSearchView } from './PatentSearchView';
import { SolutionGenView } from './SolutionGenView';
import { EvaluationView } from './EvaluationView';
import { CompletedView } from './CompletedView';
import { ConversionView } from './ConversionView';
import { EmptyState, getStepOutput } from './workflowStepUtils';
import { WORKFLOW_STEPS } from '../../types/workflow';
import { StepRunningIndicator } from '../../components/ui/StepRunningIndicator';

const PHASE_VIEWS: Record<string, React.ComponentType<{ output: unknown }>> = {
  demand_portrait: DemandPortraitView,
  problem_modeling: ProblemModelingView,
  patent_search: PatentSearchView,
  solution_gen: SolutionGenView as React.ComponentType<{ output: unknown }>,
  evaluation: EvaluationView as React.ComponentType<{ output: unknown }>,
  conversion: ConversionView,
  completed: CompletedView,
};

export function WorkflowStepResults() {
  const { workflow, currentPhase, phaseStatus, loading } = useWorkflowStore();
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);

  // 等待评分或已完成时，显示最后一个已完成的阶段
  const displayPhase = useMemo(() => {
    if (!workflow) return currentPhase;
    const order = [
      'demand_portrait',
      'problem_modeling',
      'patent_search',
      'solution_gen',
      'evaluation',
      'conversion',
    ];
    if ((workflow.status as string) === 'awaiting_rating' || workflow.status === 'completed') {
      let lastComplete = '';
      for (const phase of order) {
        if (phaseStatus[phase] === 'completed') {
          lastComplete = phase;
        }
      }
      return lastComplete || currentPhase;
    }
    return currentPhase;
  }, [workflow, currentPhase, phaseStatus]);

  const stepInfo = WORKFLOW_STEPS.find((s) => s.phaseId === displayPhase);

  const currentOutput = useMemo(() => {
    if (!workflow) return null;
    return getStepOutput(workflow, displayPhase);
  }, [workflow, displayPhase]);

  if (!selectedTaskId) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <EmptyState msg="输入文字，点击开始进行分析" icon="fa-solid fa-hand-pointer" />
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <EmptyState msg="加载中..." icon="fa-solid fa-circle-notch" />
      </div>
    );
  }

  if (!workflow) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <EmptyState msg="暂无运行中的工作流" icon="fa-solid fa-diagram-project" />
      </div>
    );
  }

  const isRunning =
    (phaseStatus[displayPhase] === 'running' || phaseStatus[displayPhase] === 'pending') &&
    (workflow.status === 'running' || workflow.status === 'idle');

  // 运行中且无输出时，显示当前步骤名称和等待提示
  if (isRunning && !currentOutput) {
    const accentColor = stepInfo?.color || 'var(--accent-blue)';
    return (
      <div
        className="card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 60,
          flex: 1,
        }}
      >
        {/* Step label */}
        <p
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: 'var(--text-primary)',
            margin: '0 0 10px',
          }}
        >
          {stepInfo?.label || '分析中'}
        </p>
        {/* Description */}
        <p
          style={{
            fontSize: 13,
            color: 'var(--text-tertiary)',
            margin: '0 0 28px',
            textAlign: 'center',
            lineHeight: 1.5,
            maxWidth: 400,
          }}
        >
          {stepInfo?.description || '正在执行分析...'}
        </p>
        {/* StepRunningIndicator - 使用统一的阶段动画 */}
        <StepRunningIndicator phaseId={displayPhase} size={100} color={accentColor} />
      </div>
    );
  }

  const PhaseComponent = PHASE_VIEWS[displayPhase];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, flex: 1, minHeight: 0 }}>
      {PhaseComponent ? (
        <PhaseComponent output={currentOutput} />
      ) : (
        <EmptyState msg="未知阶段" icon="fa-solid fa-question-circle" />
      )}
    </div>
  );
}
