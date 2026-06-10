import { useEffect, useRef } from 'react';
import { KnowledgeQAPanel } from './KnowledgeQAPanel';
import { TaskInputPanel } from './TaskInputPanel';
import { TaskList } from './TaskList';
import { AnalysisResult } from './AnalysisResult';
import { PatentStatsPanel } from './PatentStatsPanel';
import { SolutionGeneration } from './SolutionGeneration';
import { AgentWorkflowPanel } from './AgentWorkflowPanel';
import { useTaskStore } from '../../store/useTaskStore';
import { useAnalysisStore } from '../../store/useAnalysisStore';
import { usePatentStore } from '../../store/usePatentStore';
import { useSolutionStore } from '../../store/useSolutionStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useModelingStore } from '../../store/useModelingStore';

export function DashboardPage() {
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);
  const fetchAnalysis = useAnalysisStore((s) => s.fetchAnalysis);
  const fetchStats = usePatentStore((s) => s.fetchStats);
  const fetchSolutions = useSolutionStore((s) => s.fetchSolutions);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const startPolling = useWorkflowStore((s) => s.startPolling);
  const stopPolling = useWorkflowStore((s) => s.stopPolling);
  const workflow = useWorkflowStore((s) => s.workflow);
  const initialized = useRef(false);
  
  // 问题建模状态
  const modeling = useModelingStore((s) => s.modeling);
  const fetchModeling = useModelingStore((s) => s.fetchModeling);
  const refreshModeling = useModelingStore((s) => s.refreshModeling);
  const clearModeling = useModelingStore((s) => s.clearModeling);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      fetchTasks();
    }
  }, [fetchTasks]);

  useEffect(() => {
    if (!selectedTaskId) {
      stopPolling();
      clearModeling();
      // 清除 workflow 状态，确保右侧面板重置
      useWorkflowStore.getState().clearWorkflow();
      return;
    }

    // 关键：切换任务时先清除旧的 workflow，避免显示上一个任务的 workflow
    useWorkflowStore.getState().clearWorkflow();

    fetchAnalysis(selectedTaskId);
    fetchStats(selectedTaskId);
    fetchSolutions(selectedTaskId);
    fetchWorkflow(selectedTaskId);
    fetchModeling(selectedTaskId);
    startPolling(selectedTaskId);

    return () => {
      stopPolling();
    };
  }, [selectedTaskId, fetchAnalysis, fetchStats, fetchSolutions, fetchWorkflow, fetchModeling, startPolling, stopPolling, clearModeling]);

  // 监听工作流步骤变化，实时同步问题建模
  useEffect(() => {
    if (!workflow || !selectedTaskId) return;

    // 关键：workflow首次被获取到时，刷新task列表以更新status（pending -> analyzing）
    // 这解决了createTask和triggerAnalysis之间的竞态条件
    if (workflow.status === 'running' || workflow.status === 'idle') {
      fetchTasks();
    }

    // 检查每个Agent步骤是否完成，完成后刷新对应数据
    const completedSteps = workflow.steps?.filter((s) => s.status === 'completed');
    if (completedSteps && completedSteps.length > 0) {
      // 刷新问题建模数据
      refreshModeling(selectedTaskId);
    }

    // 整个工作流完成时刷新所有数据
    if (workflow.status === 'completed') {
      fetchAnalysis(selectedTaskId);
      fetchSolutions(selectedTaskId);
      fetchTasks();  // 再次刷新task以更新status为completed
    }
  }, [workflow, selectedTaskId, fetchAnalysis, fetchSolutions, refreshModeling, fetchTasks]);

  return (
    <div style={{ display: 'flex', gap: 14, minWidth: 800, minHeight: 0, height: '100%' }}>
      {/* Left main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="card-enter"><KnowledgeQAPanel /></div>
        <div className="card-enter"><TaskInputPanel /></div>
        <div className="card-enter"><TaskList /></div>
        <div className="card-enter" style={{ flex: 1, minHeight: 0 }}><AnalysisResult modeling={modeling} /></div>
        <div className="card-enter"><PatentStatsPanel /></div>
        <div className="card-enter"><SolutionGeneration /></div>
      </div>

      {/* Right sidebar */}
      <div style={{ width: 320, flexShrink: 0, minHeight: 0 }}>
        <div className="card-enter" style={{ height: '100%', minHeight: 0 }}><AgentWorkflowPanel /></div>
      </div>
    </div>
  );
}
