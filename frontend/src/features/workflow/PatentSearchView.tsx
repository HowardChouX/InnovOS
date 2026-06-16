import { useState, useEffect } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { workflowApi } from '../../api/workflow';

export function PatentSearchView({ output }: { output: any }) {
  const workflow = useWorkflowStore((s) => s.workflow);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const patents = Array.isArray(output) ? output : (output?.patents || []);

  // 监听 workflow 状态变化，确认后进入 running 时重置 submitted 以显示加载状态
  useEffect(() => {
    if (submitted && workflow?.status === 'running') {
      // workflow 已经在运行下一步了，保持 submitted 状态让父组件切换视图
    }
  }, [submitted, workflow?.status]);

  if (!workflow || patents.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无专利数据</span>
      </div>
    );
  }

  // 已确认且 workflow 正在运行下一步 → 显示加载状态
  if (submitted && workflow?.status === 'running') {
    return (
      <div className="card" style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: 200, gap: 16,
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: '50%',
          background: 'rgba(59,130,246,0.15)', border: '2px solid rgba(59,130,246,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 20, color: 'var(--accent-blue)' }} />
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            正在生成创新方案...
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            AI 正在基于您的专利评分生成解决方案，请稍候
          </div>
        </div>
      </div>
    );
  }

  const allRated = patents.every((_, i) => (ratings[String(i)] ?? 0) > 0);

  const handleSubmit = async () => {
    if (!selectedTaskId || !allRated || submitting) return;
    setSubmitting(true);
    try {
      const ratingsPayload = patents.map((p, i) => ({
        demandId: String(i),
        score: ratings[String(i)] || 0,
      }));
      await workflowApi.proceed(selectedTaskId, ratingsPayload);
      setSubmitted(true);
      fetchWorkflow(selectedTaskId);
    } catch (err) {
      console.error('提交评分失败:', err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="card-title">
        <i className="fa-solid fa-file-lines" style={{ marginRight: 8, color: 'var(--accent-cyan)' }} />
        专利检索
        <span style={{ marginLeft: 8, fontSize: 11, padding: '2px 8px', borderRadius: 10,
          background: 'rgba(59,130,246,0.15)', color: 'var(--accent-blue)' }}>
          {patents.length} 项
        </span>
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
        请对以下专利的相关度进行评分，评分后确认进入下一步
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {patents.map((patent: any, i: number) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 12,
            padding: '10px 14px', borderRadius: 8,
            background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                {(patent._title || patent.title || '').replace(/^CN\d+_FullTextImage\.pdf/i, '') || '未命名专利'}
              </div>
              {patent.patent_number && (
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                  {patent.patent_number}
                </div>
              )}
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {(patent.abstract || (patent.description || '').slice(0, 300))}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 2, cursor: 'pointer', flexShrink: 0 }}>
              {[1, 2, 3, 4, 5].map((star) => (
                <span key={star} onClick={(e) => { e.stopPropagation(); setRatings(prev => ({ ...prev, [String(i)]: star })); }}
                  style={{ fontSize: 18, color: star <= (ratings[String(i)] || 0) ? '#fbbf24' : 'rgba(255,255,255,0.15)' }}>
                  <i className="fa-solid fa-star" />
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
        <button onClick={handleSubmit} disabled={!allRated || submitting || submitted}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 20px', borderRadius: 6, fontSize: 13,
            background: !allRated || submitting ? 'var(--text-tertiary)' : submitted ? 'var(--accent-green)' : 'var(--accent)',
            border: 'none', color: '#fff', cursor: !allRated || submitting ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit',
          }}>
          {submitting ? <><i className="fa-solid fa-circle-notch fa-spin" /> 提交中...</>
            : submitted ? <><i className="fa-solid fa-check" /> 已确认</>
            : <><i className="fa-solid fa-check" /> 确认并进入下一步</>}
        </button>
      </div>
    </div>
  );
}
