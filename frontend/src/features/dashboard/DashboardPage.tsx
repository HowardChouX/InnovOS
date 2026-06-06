import { useEffect, useRef } from 'react';
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

export function DashboardPage() {
  const tasks = useTaskStore((s) => s.tasks);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);

  const fetchAnalysis = useAnalysisStore((s) => s.fetchAnalysis);
  const fetchStats = usePatentStore((s) => s.fetchStats);
  const fetchSolutions = useSolutionStore((s) => s.fetchSolutions);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const startPolling = useWorkflowStore((s) => s.startPolling);
  const stopPolling = useWorkflowStore((s) => s.stopPolling);
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      fetchTasks();
    }
  }, [fetchTasks]);

  useEffect(() => {
    if (!selectedTaskId) {
      stopPolling();
      return;
    }
    fetchAnalysis(selectedTaskId);
    fetchStats(selectedTaskId);
    fetchSolutions(selectedTaskId);
    fetchWorkflow(selectedTaskId);
    startPolling(selectedTaskId);

    return () => {
      stopPolling();
    };
  }, [selectedTaskId, fetchAnalysis, fetchStats, fetchSolutions, fetchWorkflow, startPolling, stopPolling]);

  if (tasks.length === 0) {
    return (
      <div style={{ display: 'flex', flex: 1, gap: 14, minWidth: 800 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="card-enter"><TaskInputPanel /></div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 14, minWidth: 800, minHeight: 0, height: '100%' }}>
      {/* Left main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="card-enter"><TaskInputPanel /></div>
        <div className="card-enter"><TaskList /></div>
        {selectedTaskId ? (
          <div className="card-enter" style={{ flex: 1, minHeight: 0 }}><AnalysisResult /></div>
        ) : null}
        {selectedTaskId && (
          <div className="card-enter"><PatentStatsPanel /></div>
        )}
        {selectedTaskId && (
          <div className="card-enter"><SolutionGeneration /></div>
        )}
      </div>

      {/* Right sidebar */}
      <div style={{ width: 320, flexShrink: 0, minHeight: 0 }}>
        <div className="card-enter" style={{ height: '100%', minHeight: 0 }}><AgentWorkflowPanel /></div>
      </div>
    </div>
  );
}
