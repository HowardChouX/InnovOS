import { useEffect } from 'react';
import { TaskInputPanel } from './TaskInputPanel';
import { AgentWorkflowPanel } from './AgentWorkflowPanel';
import { WorkflowStepResults } from '../workflow/WorkflowStepResults';
import { PageSkeleton, CardSkeleton } from '../../components/common/LoadingSkeleton';
import { useTaskStore } from '../../store/useTaskStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';

export function DashboardPage() {
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const loading = useTaskStore((s) => s.loading);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const startPolling = useWorkflowStore((s) => s.startPolling);
  const stopPolling = useWorkflowStore((s) => s.stopPolling);
  const clearWorkflow = useWorkflowStore((s) => s.clearWorkflow);

  // 选中任务 → 加载 workflow + 启动轮询
  // 任务列表的获取由 TaskList 自己负责（单一职责），这里不再重复 fetchTasks
  useEffect(() => {
    if (!selectedTaskId) {
      stopPolling();
      clearWorkflow();
      return;
    }
    fetchWorkflow(selectedTaskId);
    startPolling(selectedTaskId);

    return () => stopPolling();
  }, [selectedTaskId, fetchWorkflow, startPolling, stopPolling, clearWorkflow]);

  if (loading) return <PageSkeleton />;

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
