import { useState, useEffect } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { workflowApi } from '../../api/workflow';

interface Demand {
  id: string;
  source: string;
  category: string;
  description: string;
  priority: number;
  user_rating: number | null;
}

function StarInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div style={{ display: 'flex', gap: 2, cursor: 'pointer' }}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span
          key={star}
          onClick={(e) => { e.stopPropagation(); onChange(star); }}
          style={{
            fontSize: 18, color: star <= value ? '#fbbf24' : 'rgba(255,255,255,0.15)',
            transition: 'color 0.1s',
          }}
        >
          ★
        </span>
      ))}
    </div>
  );
}

export function DemandPortraitView({ output }: { output: any }) {
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
        init[r.demandId || r.demand_id] = r.score;
      }
      setRatings(init);
      if (Object.keys(init).length > 0) setSubmitted(true);
    }
  }, [output]);

  const demands: Demand[] = output?.demands || [];

  if (!workflow || demands.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无需求数据</span>
      </div>
    );
  }

  const allRated = demands.every((d) => (ratings[d.id] ?? 0) > 0);

  const handleSubmit = async () => {
    if (!selectedTaskId || !allRated || submitting) return;
    setSubmitting(true);
    try {
      const ratingsPayload = demands.map((d) => ({
        demandId: d.id,
        score: ratings[d.id] || 0,
      }));
      await workflowApi.proceed(selectedTaskId, ratingsPayload);
      setSubmitted(true);
      // 立即刷新工作流状态，状态机同步更新
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
        <i className="fa-solid fa-magnifying-glass" style={{ marginRight: 8, color: 'var(--accent-blue)' }} />
        需求洞察
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
        请对以下需求进行评分，评分后确认进入下一步
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {demands.map((demand) => (
          <div key={demand.id} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '10px 14px', borderRadius: 8,
            background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                {demand.description}
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{
                  fontSize: 10, padding: '1px 6px', borderRadius: 3,
                  background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)',
                }}>
                  {demand.category}
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                  {demand.source}
                </span>
              </div>
            </div>
            <StarInput
              value={ratings[demand.id] || 0}
              onChange={(v) => setRatings((prev) => ({ ...prev, [demand.id]: v }))}
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
