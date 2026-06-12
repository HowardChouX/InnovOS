import { useState, useEffect } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { workflowApi } from '../../api/workflow';

interface Innovation {
  id: string;
  source: string;
  description: string;
  principle: string;
  expected_effect: string;
  user_rating: number | null;
}

function StarInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div style={{ display: 'flex', gap: 2, cursor: 'pointer' }}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span key={star} onClick={(e) => { e.stopPropagation(); onChange(star); }}
          style={{
            fontSize: 18, color: star <= value ? '#fbbf24' : 'rgba(255,255,255,0.15)',
            transition: 'color 0.1s',
          }}
        >★</span>
      ))}
    </div>
  );
}

export function ProblemModelingView({ output }: { output: any }) {
  const workflow = useWorkflowStore((s) => s.workflow);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (output?.ratings) {
      const init: Record<string, number> = {};
      for (const r of output.ratings) {
        init[r.innovationId || r.innovation_id] = r.score;
      }
      setRatings(init);
      if (Object.keys(init).length > 0) setSubmitted(true);
    }
  }, [output]);

  const innovations: Innovation[] = output?.innovations || [];

  if (!workflow || innovations.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无创新方向数据</span>
      </div>
    );
  }

  const allRated = innovations.every((d) => (ratings[d.id] ?? 0) > 0);

  const handleSubmit = async () => {
    if (!selectedTaskId || !allRated || submitting) return;
    setSubmitting(true);
    try {
      const ratingsPayload = innovations.map((d) => ({
        demandId: d.id,
        score: ratings[d.id] || 0,
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
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card-title">
        <i className="fa-solid fa-cube" style={{ marginRight: 8, color: 'var(--accent-purple)' }} />
        创新方向
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
        请对以下创新方向进行评分，评分后确认进入下一步
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {innovations.map((item) => (
          <div key={item.id} style={{
            display: 'flex', alignItems: 'flex-start', gap: 12,
            padding: '10px 14px', borderRadius: 8,
            background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                {item.description}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{
                  fontSize: 10, padding: '1px 6px', borderRadius: 3,
                  background: 'rgba(167,139,250,0.1)', color: 'var(--accent-purple)',
                }}>
                  {item.source}
                </span>
                {item.principle && (
                  <span style={{ fontSize: 10, color: 'var(--accent-yellow)' }}>
                    {item.principle}
                  </span>
                )}
                {item.expected_effect && (
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                    {item.expected_effect}
                  </span>
                )}
              </div>
            </div>
            <StarInput
              value={ratings[item.id] || 0}
              onChange={(v) => setRatings((prev) => ({ ...prev, [item.id]: v }))}
            />
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
        <button
          onClick={handleSubmit}
          disabled={!allRated || submitting || submitted}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 20px', borderRadius: 6, fontSize: 13,
            background: !allRated || submitting ? 'var(--text-tertiary)' : submitted ? 'var(--accent-green)' : 'var(--accent)',
            border: 'none', color: '#fff', cursor: !allRated || submitting ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit', transition: 'all 0.15s',
          }}
        >
          {submitting ? (
            <><i className="fa-solid fa-circle-notch fa-spin" /> 提交中...</>
          ) : submitted ? (
            <><i className="fa-solid fa-check" /> 已确认</>
          ) : (
            <><i className="fa-solid fa-check" /> 确认并进入下一步</>
          )}
        </button>
      </div>
    </div>
  );
}
