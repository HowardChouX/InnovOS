import { useState, useEffect } from 'react';
import { useTaskStore } from '../../store/useTaskStore';
import { useAnalysisStore } from '../../store/useAnalysisStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';

export function TaskInputPanel() {
  const [description, setDescription] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const createTask = useTaskStore((s) => s.createTask);
  const triggerAnalysis = useAnalysisStore((s) => s.triggerAnalysis);
  const stopPolling = useWorkflowStore((s) => s.stopPolling);
  const workflow = useWorkflowStore((s) => s.workflow);

  // 根据工作流状态更新分析按钮
  useEffect(() => {
    if (!workflow) {
      setIsAnalyzing(false);
      return;
    }
    if (workflow.status === 'running') {
      setIsAnalyzing(true);
    } else if (workflow.status === 'completed' || workflow.status === 'failed') {
      setIsAnalyzing(false);
    }
  }, [workflow]);

  const handleSubmit = async () => {
    if (!description.trim()) return;

    // 禁用输入，显示加载状态
    setIsAnalyzing(true);

    try {
      // 创建任务
      const task = await createTask({ title: description.slice(0, 50), description, tags: [] });
      if (!task) {
        setIsAnalyzing(false);
        return;
      }

      setDescription('');

      // 触发分析（后台执行，不阻塞UI）
      // 注意：selectedTaskId 的设置会自动触发 DashboardPage 的 workflow 轮询
      await triggerAnalysis(task.id);
    } catch (error) {
      console.error('Failed to start analysis:', error);
      setIsAnalyzing(false);
    }
  };

  const handleCancel = () => {
    stopPolling();
    setIsAnalyzing(false);
  };

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="card-title">
          创新任务输入
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={{
            fontSize: 11, padding: '5px 12px', background: 'transparent',
            color: 'var(--text-secondary)', border: '1px solid var(--border)',
            borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
          }}>
            任务模板 <i className="fa-solid fa-chevron-down" style={{ fontSize: 8, marginLeft: 4 }} />
          </button>
          <button style={{
            fontSize: 11, padding: '5px 12px', background: 'transparent',
            color: 'var(--text-secondary)', border: '1px solid var(--border)',
            borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
          }}>
            <i className="fa-solid fa-file-import" style={{ marginRight: 4 }} />
            导入文档
          </button>
        </div>
      </div>

      <textarea value={description} onChange={(e) => setDescription(e.target.value)}
        placeholder="输入您的创新问题..."
        disabled={isAnalyzing}
        style={{
          width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 12, marginBottom: 12, minHeight: 60,
          fontSize: 14, color: 'var(--text-primary)',
          resize: 'vertical', outline: 'none', fontFamily: 'inherit',
          opacity: isAnalyzing ? 0.6 : 1,
        }} />

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        {isAnalyzing && (
          <button
            onClick={handleCancel}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--accent-red)', border: 'none',
              color: '#fff', padding: '8px 20px', borderRadius: 6,
              cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
            }}
          >
            <i className="fa-solid fa-stop" style={{ fontSize: 11 }} />
            取消
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={isAnalyzing || !description.trim()}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: isAnalyzing ? 'var(--text-tertiary)' : 'var(--accent)',
            border: 'none',
            color: '#fff', padding: '8px 20px', borderRadius: 6,
            cursor: isAnalyzing ? 'not-allowed' : 'pointer', fontSize: 13, fontFamily: 'inherit',
          }}
        >
          {isAnalyzing ? (
            <>
              <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 11 }} />
              分析中...
            </>
          ) : (
            <>
              开始分析 <i className="fa-solid fa-arrow-right" style={{ fontSize: 11 }} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
