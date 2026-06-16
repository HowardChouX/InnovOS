import { useState, useEffect } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { workflowApi } from '../../api/workflow';
import { ConflictGraph } from './ConflictGraph';

interface Innovation {
  id: string;
  source?: string;
  sources?: string[];
  source_analyzer?: string;
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
        ><i className="fa-solid fa-star" /></span>
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

  const conflictNodes = (() => {
    if (!output) return [];
    const funcAnalysis = output.function_analysis;
    if (funcAnalysis?.system_components?.length > 0) {
      return funcAnalysis.system_components.slice(0, 4).map((c: any) => ({
        label: c.name,
        sublabel: c.description?.slice(0, 15),
      }));
    }
    const rootCause = output.root_cause_analysis;
    if (rootCause?.root_causes?.length > 0) {
      return rootCause.root_causes.slice(0, 4).map((rc: any) => ({
        label: rc.text?.slice(0, 10) || '',
        sublabel: '',
      }));
    }
    if (innovations.length > 0) {
      return innovations.slice(0, 4).map((inn) => ({
        label: inn.source_analyzer || '分析',
        sublabel: inn.description?.slice(0, 15),
      }));
    }
    return [];
  })();

  const centerConflict = output?.root_cause_analysis?.initial_defect
    || output?.function_analysis?.summary?.slice(0, 15)
    || '核心冲突';

  if (!workflow || (innovations.length === 0 && conflictNodes.length === 0)) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无问题建模数据</span>
      </div>
    );
  }

  if (submitted && workflow?.status === 'running') {
    return (
      <div className="card" style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: 200, gap: 16,
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: '50%',
          background: 'rgba(167,139,250,0.15)', border: '2px solid rgba(167,139,250,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 20, color: 'var(--accent-purple)' }} />
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            正在检索相关专利...
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            AI 正在基于您的评分检索相关专利，请稍候
          </div>
        </div>
      </div>
    );
  }

  const allRated = innovations.length > 0 && innovations.every((d) => (ratings[d.id] ?? 0) > 0);

  const handleSubmit = async () => {
    if (!selectedTaskId || submitting) return;
    if (innovations.length > 0 && !allRated) return;
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%', overflowY: 'auto' }}>
      <div className="card" style={{ flexShrink: 0 }}>
        <div className="card-title">
          <i className="fa-solid fa-diagram-project" style={{ marginRight: 8, color: 'var(--accent-purple)' }} />
          问题建模 — 冲突图谱
        </div>
        {conflictNodes.length > 0 && (
          <ConflictGraph centerConflict={centerConflict} nodes={conflictNodes} />
        )}
        <div style={{
          marginTop: 12, padding: '8px 12px', borderRadius: 6,
          background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.15)',
          fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
        }}>
          <i className="fa-solid fa-circle-info" style={{ marginRight: 6, color: 'var(--accent-blue)' }} />
          {centerConflict}
        </div>
      </div>

      <div className="card" style={{ flexShrink: 0 }}>
        <div className="card-title">
          <i className="fa-solid fa-cube" style={{ marginRight: 8, color: 'var(--accent-purple)' }} />
          创新方向
        </div>

        {innovations.length > 0 && (
          <>
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
                      {(item.sources || [item.source_analyzer].filter(Boolean)).map((src: string, i: number) => (
                        <span key={i} style={{
                          fontSize: 10, padding: '1px 6px', borderRadius: 3,
                          background: 'rgba(167,139,250,0.1)', color: 'var(--accent-purple)',
                        }}>
                          {src}
                        </span>
                      ))}
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
          </>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
          <button
            onClick={handleSubmit}
            disabled={(innovations.length > 0 && !allRated) || submitting || submitted}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 20px', borderRadius: 6, fontSize: 13,
              background: (innovations.length > 0 && !allRated) || submitting ? 'var(--text-tertiary)' : submitted ? 'var(--accent-green)' : 'var(--accent)',
              border: 'none', color: '#fff',
              cursor: (innovations.length > 0 && !allRated) || submitting ? 'not-allowed' : 'pointer',
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
    </div>
  );
}
