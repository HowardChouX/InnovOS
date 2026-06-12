import { useEffect, useRef } from 'react';
import { TaskInputPanel } from './TaskInputPanel';
import { TaskList } from './TaskList';
import { AgentWorkflowPanel } from './AgentWorkflowPanel';
import { WorkflowStepResults } from '../workflow/WorkflowStepResults';
import { useTaskStore } from '../../store/useTaskStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';

export function DashboardPage() {
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const startPolling = useWorkflowStore((s) => s.startPolling);
  const stopPolling = useWorkflowStore((s) => s.stopPolling);
  const workflow = useWorkflowStore((s) => s.workflow);
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
      useWorkflowStore.getState().clearWorkflow();
      return;
    }

    useWorkflowStore.getState().clearWorkflow();

    fetchWorkflow(selectedTaskId);
    startPolling(selectedTaskId);

    return () => {
      stopPolling();
    };
  }, [selectedTaskId, fetchWorkflow, startPolling, stopPolling]);

  // 工作流状态变化时刷新任务列表
  useEffect(() => {
    if (!workflow || !selectedTaskId) return;

    if (workflow.status === 'running' || workflow.status === 'idle') {
      fetchTasks();
    }

    if (workflow.status === 'completed') {
      fetchTasks();
    }
  }, [workflow, selectedTaskId, fetchTasks]);

  return (
    <div style={{ display: 'flex', gap: 14, minWidth: 800, minHeight: 0, height: '100%' }}>
      {/* Left main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="card-enter"><TaskInputPanel /></div>
        <div className="card-enter"><TaskList /></div>
        <div className="card-enter" style={{ flex: 1, minHeight: 0 }}>
          <WorkflowStepResults />
        </div>
      </div>

      {/* Right sidebar */}
      <div style={{ width: 320, flexShrink: 0, minHeight: 0 }}>
        <div className="card-enter" style={{ height: '100%', minHeight: 0 }}><AgentWorkflowPanel /></div>
      </div>
    </div>
  );
}
