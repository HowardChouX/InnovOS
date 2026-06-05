import { useEffect, useRef } from 'react';
import { TaskInputPanel } from './TaskInputPanel';
import { TaskList } from './TaskList';
import { AnalysisResult } from './AnalysisResult';
import { PatentStatsPanel } from './PatentStatsPanel';
import { SolutionGeneration } from './SolutionGeneration';
import { AgentWorkflowPanel } from './AgentWorkflowPanel';
import { WelcomeGuide } from './WelcomeGuide';
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
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      fetchTasks();
    }
  }, [fetchTasks]);

  useEffect(() => {
    if (!selectedTaskId) return;
    fetchAnalysis(selectedTaskId);
    fetchStats(selectedTaskId);
    fetchSolutions(selectedTaskId);
    fetchWorkflow(selectedTaskId);
  }, [selectedTaskId, fetchAnalysis, fetchStats, fetchSolutions, fetchWorkflow]);

  if (tasks.length === 0) {
    return (
      <div style={{ display: 'flex', flex: 1, gap: 14, minWidth: 800 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="card-enter"><TaskInputPanel /></div>
          <div className="card-enter"><WelcomeGuide /></div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 14, minWidth: 800, minHeight: 0 }}>
      {/* Left main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="card-enter"><TaskInputPanel /></div>
        <div className="card-enter"><TaskList /></div>
        {selectedTaskId ? (
          <div className="card-enter" style={{ flex: 1, minHeight: 0 }}><AnalysisResult /></div>
        ) : (
          <div className="card-enter"><WelcomeGuide /></div>
        )}
        {selectedTaskId && (
          <div className="card-enter"><PatentStatsPanel /></div>
        )}
      </div>

      {/* Right sidebar */}
      <div style={{ width: 320, display: 'flex', flexDirection: 'column', gap: 12, flexShrink: 0 }}>
        <div className="card-enter" style={{ flex: 1 }}><SolutionGeneration /></div>
        <div className="card-enter" style={{ flex: 1 }}><AgentWorkflowPanel /></div>
      </div>
    </div>
  );
}
