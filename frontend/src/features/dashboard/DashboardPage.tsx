import { useEffect, useRef, useState } from 'react';
import { TaskInputPanel } from './TaskInputPanel';
import { TaskList } from './TaskList';
import { AnalysisResult } from './AnalysisResult';
import { PatentStatsPanel } from './PatentStatsPanel';
import { SolutionGeneration } from './SolutionGeneration';
import { AgentWorkflowPanel } from './AgentWorkflowPanel';
import { ProblemModelingPanel } from '../modeling/ProblemModelingPanel';
import { useTaskStore } from '../../store/useTaskStore';
import { useAnalysisStore } from '../../store/useAnalysisStore';
import { usePatentStore } from '../../store/usePatentStore';
import { useSolutionStore } from '../../store/useSolutionStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { modelingApi } from '../../api/modeling';
import type { ProblemModeling } from '../../types/modeling';

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
  const [modeling, setModeling] = useState<ProblemModeling | null>(null);
  const [modelingLoading, setModelingLoading] = useState(false);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      fetchTasks();
    }
  }, [fetchTasks]);

  useEffect(() => {
    if (!selectedTaskId) {
      stopPolling();
      setModeling(null);
      return;
    }
    fetchAnalysis(selectedTaskId);
    fetchStats(selectedTaskId);
    fetchSolutions(selectedTaskId);
    fetchWorkflow(selectedTaskId);
    startPolling(selectedTaskId);

    // 加载问题建模
    setModelingLoading(true);
    modelingApi.getByTaskId(selectedTaskId)
      .then((data) => setModeling(data))
      .catch(() => setModeling(null))
      .finally(() => setModelingLoading(false));

    return () => {
      stopPolling();
    };
  }, [selectedTaskId, fetchAnalysis, fetchStats, fetchSolutions, fetchWorkflow, startPolling, stopPolling]);

  // 当工作流完成或agent2完成时，刷新分析结果和问题建模
  useEffect(() => {
    if (!workflow || !selectedTaskId) return;
    
    // 检查agent2是否已完成
    const agent2Step = workflow.steps?.find((s) => s.agentId === 'agent2');
    if (agent2Step?.status === 'completed') {
      // 刷新问题建模
      setModelingLoading(true);
      modelingApi.getByTaskId(selectedTaskId)
        .then((data) => setModeling(data))
        .catch(() => setModeling(null))
        .finally(() => setModelingLoading(false));
    }
    
    // 整个工作流完成时刷新所有数据
    if (workflow.status === 'completed') {
      fetchAnalysis(selectedTaskId);
      fetchSolutions(selectedTaskId);
    }
  }, [workflow, selectedTaskId, fetchAnalysis, fetchSolutions]);

  return (
    <div style={{ display: 'flex', gap: 14, minWidth: 800, minHeight: 0, height: '100%' }}>
      {/* Left main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="card-enter"><TaskInputPanel /></div>
        <div className="card-enter"><TaskList /></div>
        <div className="card-enter"><ProblemModelingPanel modeling={modeling} loading={modelingLoading} /></div>
        <div className="card-enter" style={{ flex: 1, minHeight: 0 }}><AnalysisResult /></div>
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
