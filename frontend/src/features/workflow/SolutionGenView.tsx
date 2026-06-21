import { useState, useEffect } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { workflowApi } from '../../api/workflow';

interface SolutionItem {
  title: string;
  description: string;
  principles?: string[];
  referencedPatents?: string[];
}

export function SolutionGenView({ output }: { output: SolutionItem[] | null }) {
  const workflow = useWorkflowStore((s) => s.workflow);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const solutions = Array.isArray(output) ? output : [];

  const allRated = solutions.length > 0 && solutions.every((_, i) => (ratings[String(i)] ?? 0) > 0);

  const handleSubmit = async () => {
    if (!selectedTaskId || !allRated || submitting) return;
    setSubmitting(true);
    try {
      const ratingsPayload = solutions.map((s, i) => ({
        demandId: String(i),
        score: ratings[String(i)] || 0,
      }));
      await workflowApi.proceed(selectedTaskId, ratingsPayload);
      setSubmitted(true);
      fetchWorkflow(selectedTaskId);
    } catch (err) {
      console.error('确认方案失败:', err);
      setSubmitError(err instanceof Error ? err.message : '确认方案失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (!output || !Array.isArray(output) || output.length === 0) {
    return (
      <div className="card" style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        flex: 1, minHeight: 0, gap: 12,
      }}>
        <i className="fa-solid fa-wand-magic-sparkles" style={{ fontSize: 32, color: 'var(--text-tertiary)', opacity: 0.3 }} />
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无方案数据</span>
      </div>
    );
  }

  // 已确认 → 显示加载状态，直到组件因 phase 切换而卸载
  if (submitted) {
    return (
      <div className="card" style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        flex: 1, minHeight: 0, gap: 16,
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: '50%',
          background: 'rgba(139,92,246,0.15)', border: '2px solid rgba(139,92,246,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 20, color: 'var(--accent-purple)' }} />
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            正在评估方案...
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            AI 正在对方案进行多维度评估，请稍候
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="card-title">
        <i className="fa-solid fa-wand-magic-sparkles" style={{ marginRight: 8, color: 'var(--accent-green)' }} />
        方案生成
        <span style={{ marginLeft: 8, fontSize: 11, padding: '2px 8px', borderRadius: 10,
          background: 'rgba(74,222,128,0.15)', color: 'var(--accent-green)' }}>
          {solutions.length} 项
        </span>
      </div>

      {workflow?.status === 'awaiting_rating' && (
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
          请对以下方案的可行性进行评分，评分后确认进入下一步
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {output.map((sol, i) => (
          <div key={i} style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 14,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginBottom: 8, gap: 8,
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                方案 {i + 1}: {sol.title}
              </div>
              {workflow?.status === 'awaiting_rating' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 2, cursor: 'pointer', flexShrink: 0 }}>
                  {[1, 2, 3, 4, 5].map((star) => (
                    <span key={star}
                      onClick={(e) => { e.stopPropagation(); setRatings(prev => ({ ...prev, [String(i)]: star })); }}
                      style={{ fontSize: 18, color: star <= (ratings[String(i)] || 0) ? '#fbbf24' : 'rgba(255,255,255,0.15)' }}>
                      <i className="fa-solid fa-star" />
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div style={{
              fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 8,
              display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical', overflow: 'hidden',
            }}>
              {sol.description}
            </div>

            {sol.principles && sol.principles.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                {sol.principles.map((p, j) => (
                  <span key={j} style={{
                    padding: '2px 8px', borderRadius: 3, fontSize: 10,
                    background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.2)',
                    color: 'var(--accent-yellow)',
                  }}>
                    <i className="fa-regular fa-lightbulb" style={{ marginRight: 4, fontSize: 9 }} />
                    {p}
                  </span>
                ))}
              </div>
            )}

            {sol.referencedPatents && sol.referencedPatents.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {sol.referencedPatents.map((patent, j) => (
                  <span key={j} style={{
                    padding: '2px 8px', borderRadius: 3, fontSize: 10,
                    background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                    color: 'var(--accent-blue)',
                  }}>
                    <i className="fa-regular fa-copyright" style={{ marginRight: 4, fontSize: 9 }} />
                    {patent}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {submitError && (
        <div style={{ padding: '8px 12px', borderRadius: 6, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: 'var(--accent-red)', fontSize: 12 }}>
          {submitError}
        </div>
      )}
      {workflow?.status === 'awaiting_rating' && (
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
      )}
    </div>
  );
}
