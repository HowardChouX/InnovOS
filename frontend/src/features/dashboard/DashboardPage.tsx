import { useEffect } from 'react';
import { TaskInputPanel } from './TaskInputPanel';
import { AgentWorkflowPanel } from './AgentWorkflowPanel';
import { WorkflowStepResults } from '../workflow/WorkflowStepResults';
import { PageSkeleton, CardSkeleton } from '../../components/common/LoadingSkeleton';
import { useTaskStore } from '../../store/useTaskStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';

export function DashboardPage() {
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const tasks = useTaskStore((s) => s.tasks);
  const loading = useTaskStore((s) => s.loading);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const startPolling = useWorkflowStore((s) => s.startPolling);
  const stopPolling = useWorkflowStore((s) => s.stopPolling);
  const workflow = useWorkflowStore((s) => s.workflow);

  // Load tasks ONCE on mount (not on every render)
  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Load workflow when task is selected
  useEffect(() => {
    if (!selectedTaskId) {
      stopPolling();
      useWorkflowStore.getState().clearWorkflow();
      return;
    }

    fetchWorkflow(selectedTaskId);
    startPolling(selectedTaskId);

    return () => {
      stopPolling();
    };
  }, [selectedTaskId, fetchWorkflow, startPolling, stopPolling]);

  // Refresh task list only when workflow finishes
  useEffect(() => {
    if (!workflow) return;
    if (workflow.status === 'completed' || workflow.status === 'failed') {
      fetchTasks();
      stopPolling(); // 完成时停止轮询
    }
  }, [workflow, fetchTasks, stopPolling]);

  // 首次加载时显示全页骨架屏
  if (loading && tasks.length === 0) {
    return <PageSkeleton />;
  }

  return (
    <div style={{ display: 'flex', gap: 14, minWidth: 800, minHeight: 0, height: '100%' }}>
      {/* Left main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="card-enter">
          <TaskInputPanel />
        </div>
        <div
          className="card-enter"
          style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
        >
          <WorkflowStepResults />
        </div>
      </div>

      {/* Right sidebar */}
      <div style={{ width: 320, flexShrink: 0, minHeight: 0 }}>
        <div className="card-enter" style={{ height: '100%', minHeight: 0 }}>
          {loading ? <CardSkeleton /> : <AgentWorkflowPanel />}
        </div>
      </div>
    </div>
  );
}
