import { useState } from 'react';
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
        <span
          key={star}
          onClick={(e) => {
            e.stopPropagation();
            onChange(star);
          }}
          style={{
            fontSize: 18,
            color: star <= value ? '#fbbf24' : 'rgba(255,255,255,0.15)',
            transition: 'color 0.1s',
          }}
        >
          <i className="fa-solid fa-star" />
        </span>
      ))}
    </div>
  );
}

export function ProblemModelingView({ output }: { output: unknown }) {
  return (
    <ProblemModelingViewInner key={output ? JSON.stringify(output) : 'empty'} output={output} />
  );
}

function ProblemModelingViewInner({ output }: { output: unknown }) {
  const workflow = useWorkflowStore((s) => s.workflow);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);

  const out = output as Record<string, unknown> | null;

  const initialRatings = (() => {
    if (!out) return {};
    const ratingsData = out.ratings as
      | Array<{ innovationId?: string; innovation_id?: string; score: number }>
      | undefined;
    if (ratingsData) {
      const init: Record<string, number> = {};
      for (const r of ratingsData) {
        init[r.innovationId || r.innovation_id || ''] = r.score;
      }
      return init;
    }
    return {};
  })();

  const [ratings, setRatings] = useState<Record<string, number>>(initialRatings);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(Object.keys(initialRatings).length > 0);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const innovations: Innovation[] = (out?.innovations as Innovation[]) || [];

  const conflictNodes = (() => {
    if (!out) return [];
    const funcAnalysis = out.function_analysis as Record<string, unknown> | undefined;
    if (
      funcAnalysis &&
      ((funcAnalysis.key_interactions as Record<string, unknown>[])?.length ?? 0) > 0
    ) {
      const harmful = (funcAnalysis.key_interactions as Record<string, unknown>[])
        .filter((ix) => (ix as { type?: string }).type === '有害')
        .slice(0, 4);
      if (harmful.length > 0) {
        return harmful.map((ix) => ({
          label: `${(ix as { tool?: string }).tool || ''} → ${(ix as { receiver?: string }).receiver || ''}`,
          sublabel: ((ix as { verb?: string }).verb || '').slice(0, 18),
        }));
      }
    }
    if (
      funcAnalysis &&
      ((funcAnalysis.system_components as Record<string, unknown>[])?.length ?? 0) > 0
    ) {
      return (funcAnalysis.system_components as Record<string, unknown>[]).slice(0, 4).map((c) => ({
        label: (c as { name?: string }).name || '',
        sublabel: ((c as { description?: string }).description || '').slice(0, 15),
      }));
    }
    const rootCause = out.root_cause_analysis as Record<string, unknown> | undefined;
    if (rootCause && ((rootCause.root_causes as Record<string, unknown>[])?.length ?? 0) > 0) {
      return (rootCause.root_causes as Record<string, unknown>[]).slice(0, 4).map((rc) => ({
        label: ((rc as { text?: string }).text || '').slice(0, 10),
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

  const centerConflict =
    ((out?.root_cause_analysis as Record<string, unknown>)?.initial_defect as string) ||
    (((out?.function_analysis as Record<string, unknown>)?.summary as string) || '').slice(0, 15) ||
    '核心冲突';

  if (!workflow || (innovations.length === 0 && conflictNodes.length === 0)) {
    return (
      <div
        className="card"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          minHeight: 0,
        }}
      >
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无问题建模数据</span>
      </div>
    );
  }

  // 已确认 → 显示加载状态，直到组件因 phase 切换而卸载
  if (submitted) {
    return (
      <div
        className="card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          minHeight: 0,
          gap: 16,
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: '50%',
            background: 'rgba(167,139,250,0.15)',
            border: '2px solid rgba(167,139,250,0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <i
            className="fa-solid fa-circle-notch fa-spin"
            style={{ fontSize: 20, color: 'var(--accent-purple)' }}
          />
        </div>
        <div style={{ textAlign: 'center' }}>
          <div
            style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
          >
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
      setSubmitError(err instanceof Error ? err.message : '提交评分失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
      }}
    >
      {/* Section 1: Analysis Summary */}
      <div
        style={{
          padding: '12px 16px',
          borderRadius: 8,
          background: 'rgba(59,130,246,0.06)',
          border: '1px solid rgba(59,130,246,0.15)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: 'rgba(59,130,246,0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <i
            className="fa-solid fa-diagram-project"
            style={{ color: 'var(--accent-blue)', fontSize: 14 }}
          />
        </div>
        <div>
          <div
            style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}
          >
            问题分析结果
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            AI 识别了 {innovations.length} 个创新方向，请评分后确认
          </div>
        </div>
      </div>

      {/* Section 2: Conflict Graph (on top when exists) */}
      {conflictNodes.length > 0 && (
        <div
          style={{
            padding: 12,
            borderRadius: 8,
            background: 'rgba(0,0,0,0.15)',
            border: '1px solid var(--border)',
          }}
        >
          <div
            style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}
          >
            <i
              className="fa-solid fa-code-branch"
              style={{ marginRight: 6, color: 'var(--accent-purple)' }}
            />
            冲突分析图
          </div>
          <ConflictGraph centerConflict={centerConflict} nodes={conflictNodes} />
          <div
            style={{
              marginTop: 8,
              padding: '6px 10px',
              borderRadius: 6,
              background: 'rgba(59,130,246,0.06)',
              border: '1px solid rgba(59,130,246,0.15)',
              fontSize: 11,
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
            }}
          >
            <i
              className="fa-solid fa-circle-info"
              style={{ marginRight: 6, color: 'var(--accent-blue)' }}
            />
            {centerConflict}
          </div>
        </div>
      )}

      {/* Section 3: Innovation Points (always visible) */}
      <div className="card" style={{ flexShrink: 0 }}>
        <div className="card-title">
          <i
            className="fa-solid fa-lightbulb"
            style={{ marginRight: 8, color: 'var(--accent-yellow)' }}
          />
          创新方向（共 {innovations.length} 项）
        </div>

        {innovations.length > 0 && (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
            请对以下创新方向进行评分，评分后确认进入下一步
          </div>
        )}

        {innovations.length === 0 ? (
          <div
            style={{
              textAlign: 'center',
              padding: 24,
              color: 'var(--text-tertiary)',
              fontSize: 12,
            }}
          >
            <i
              className="fa-solid fa-cube"
              style={{ fontSize: 20, display: 'block', marginBottom: 8, opacity: 0.3 }}
            />
            暂无创新方向数据
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {innovations.map((item) => (
              <div
                key={item.id}
                style={{
                  padding: '12px 14px',
                  borderRadius: 8,
                  background: 'rgba(0,0,0,0.2)',
                  border: '1px solid var(--border)',
                  transition: 'border-color 0.15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  {/* Icon for the principle */}
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 6,
                      flexShrink: 0,
                      background: 'rgba(251,191,36,0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <i
                      className="fa-solid fa-wand-magic-sparkles"
                      style={{ fontSize: 11, color: 'var(--accent-yellow)' }}
                    />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Description */}
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                        marginBottom: 4,
                      }}
                    >
                      {item.description}
                    </div>

                    {/* Tags row */}
                    <div
                      style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}
                    >
                      {/* Source / analyzer tags */}
                      {(item.sources || (item.source_analyzer ? [item.source_analyzer] : [])).map(
                        (src: string, i: number) => (
                          <span
                            key={i}
                            style={{
                              fontSize: 10,
                              padding: '1px 6px',
                              borderRadius: 3,
                              background: 'rgba(167,139,250,0.1)',
                              color: 'var(--accent-purple)',
                            }}
                          >
                            {src}
                          </span>
                        ),
                      )}
                      {item.principle && (
                        <span
                          style={{
                            fontSize: 10,
                            padding: '1px 6px',
                            borderRadius: 3,
                            background: 'rgba(251,191,36,0.1)',
                            color: 'var(--accent-yellow)',
                          }}
                        >
                          {item.principle}
                        </span>
                      )}
                      {item.expected_effect && (
                        <span
                          style={{
                            fontSize: 10,
                            padding: '1px 6px',
                            borderRadius: 3,
                            background: 'rgba(74,222,128,0.1)',
                            color: 'var(--accent-green)',
                          }}
                        >
                          {item.expected_effect}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Star rating */}
                  <StarInput
                    value={ratings[item.id] || 0}
                    onChange={(v) => setRatings((prev) => ({ ...prev, [item.id]: v }))}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        {submitError && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(248,113,113,0.1)',
              border: '1px solid rgba(248,113,113,0.3)',
              color: 'var(--accent-red)',
              fontSize: 12,
              marginTop: 8,
            }}
          >
            {submitError}
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
          <button
            onClick={handleSubmit}
            disabled={(innovations.length > 0 && !allRated) || submitting || submitted}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 20px',
              borderRadius: 6,
              fontSize: 13,
              background:
                (innovations.length > 0 && !allRated) || submitting
                  ? 'var(--text-tertiary)'
                  : submitted
                    ? 'var(--accent-green)'
                    : 'var(--accent)',
              border: 'none',
              color: '#fff',
              cursor:
                (innovations.length > 0 && !allRated) || submitting ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
          >
            {submitting ? (
              <>
                <i className="fa-solid fa-circle-notch fa-spin" /> 提交中...
              </>
            ) : submitted ? (
              <>
                <i className="fa-solid fa-check" /> 已确认
              </>
            ) : (
              <>
                <i className="fa-solid fa-check" /> 确认并进入下一步
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
