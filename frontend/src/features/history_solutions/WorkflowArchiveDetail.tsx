import { useState, useEffect, useMemo } from 'react';
import { workflowApi } from '../../api/workflow';
import { historySolutionsApi } from '../../api/historySolutions';
import type { WorkflowState, AgentStep } from '../../types/workflow';
import { WORKFLOW_STEPS } from '../../types/workflow';
import type { HistorySolutionsData, InfringementResult } from '../../api/historySolutions';

// ─── Types ───────────────────────────────────────────

interface StepCardProps {
  step: typeof WORKFLOW_STEPS[number];
  output: any;
  duration?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  defaultOpen?: boolean;
}

interface WorkflowArchiveDetailProps {
  taskId: string;
  onBack: () => void;
}

// ─── Helpers ─────────────────────────────────────────

function Stars({ count, max = 5 }: { count: number; max?: number }) {
  if (count <= 0) return null;
  return (
    <span style={{ color: '#fbbf24', fontSize: 10, letterSpacing: -1, whiteSpace: 'nowrap' }}>
      {Array.from({ length: max }, (_, i) => (
        <i key={i} className="fa-solid fa-star" style={{ opacity: i < count ? 1 : 0.15, marginRight: 1 }} />
      ))}
    </span>
  );
}

function getItemRating(itemId: string, output: any): number | null {
  if (!output?.ratings) return null;
  const found = output.ratings.find((r: any) =>
    r.demandId === itemId || r.demand_id === itemId
    || r.innovationId === itemId || r.innovation_id === itemId
    || String(r.demandId) === itemId || String(r.demand_id) === itemId
  );
  return found?.score || null;
}

// ─── Step renderers ──────────────────────────────────

function DemandOutput({ output }: { output: any }) {
  if (!output) return <EmptyOutput />;
  const demands = output?.demands || [];
  if (demands.length === 0) return <EmptyOutput />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {demands.map((d: any, i: number) => {
        const rating = getItemRating(d.id, output) || d.user_rating;
        return (
        <div key={d.id || i} style={{
          padding: '8px 10px', borderRadius: 6,
          background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
            {d.description}
          </div>
          <div style={{ display: 'flex', gap: 6, fontSize: 10, color: 'var(--text-tertiary)', alignItems: 'center' }}>
            <span style={{ padding: '1px 5px', borderRadius: 3, background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)' }}>
              {d.category}
            </span>
            <span>{d.source}</span>
            {rating != null && <Stars count={rating} />}
          </div>
        </div>
        );
      })}
    </div>
  );
}

function ModelingOutput({ output }: { output: any }) {
  if (!output) return <EmptyOutput />;
  const innovations = output?.innovations || [];
  if (innovations.length === 0) return <EmptyOutput />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {innovations.map((inn: any, i: number) => {
        const rating = getItemRating(inn.id, output) || inn.user_rating;
        return (
        <div key={inn.id || i} style={{
          padding: '8px 10px', borderRadius: 6,
          background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
            {inn.description}
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', fontSize: 10, color: 'var(--text-tertiary)', alignItems: 'center' }}>
            {inn.principle && <span style={{ padding: '1px 5px', borderRadius: 3, background: 'rgba(251,191,36,0.1)', color: 'var(--accent-yellow)' }}>{inn.principle}</span>}
            {inn.expected_effect && <span>{inn.expected_effect}</span>}
            {rating != null && <Stars count={rating} />}
          </div>
        </div>
        );
      })}
    </div>
  );
}

function PatentOutput({ output }: { output: any }) {
  if (!output) return <EmptyOutput />;
  const patents = Array.isArray(output) ? output : (output?.patents || []);
  if (patents.length === 0) return <EmptyOutput />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {patents.slice(0, 20).map((p: any, i: number) => {
        const rating = getItemRating(String(i), output) || p.user_rating;
        return (
        <div key={i} style={{
          padding: '8px 10px', borderRadius: 6,
          background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                {p._title || p.title || '未命名专利'}
              </div>
              {p.patent_number && (
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 2 }}>专利号: {p.patent_number}</div>
              )}
              {(p.abstract || p.description) && (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {(p.abstract || p.description || '').slice(0, 200)}
                </div>
              )}
            </div>
            {rating != null && <Stars count={rating} />}
          </div>
        </div>
        );
      })}
      {patents.length > 20 && (
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', padding: 4 }}>
          还有 {patents.length - 20} 项专利
        </div>
      )}
    </div>
  );
}

function SolutionOutput({ output, solutionsData }: { output: any; solutionsData?: HistorySolutionsData | null }) {
  if (!output) return <EmptyOutput />;
  const solutions = Array.isArray(output) ? output : [];
  if (solutions.length === 0) return <EmptyOutput />;
  // Build a lookup map from solutions API data (keyed by normalized title)
  const solutionRatingMap = useMemo(() => {
    const map: Record<string, number> = {};
    if (solutionsData?.solutions) {
      for (const s of solutionsData.solutions) {
        const key = (s.title || '').trim().toLowerCase();
        // rating from API is 1-5 or 0-100 scale; assume 1-5 if <=5
        if (s.rating != null) map[key] = s.rating;
      }
    }
    return map;
  }, [solutionsData]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {solutions.map((sol: any, i: number) => {
        // Try: output.ratings → solution API rating → user_rating on object
        const fromOutput = getItemRating(String(i), output);
        const fromApi = solutionRatingMap[(sol.title || '').trim().toLowerCase()];
        const rating = fromOutput || fromApi || sol.user_rating;
        return (
        <div key={i} style={{
          padding: '8px 10px', borderRadius: 6,
          background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 2 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
              方案 {i + 1}: {sol.title}
            </div>
            {rating != null && <Stars count={rating} />}
          </div>
          {sol.description && (
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 4 }}>
              {sol.description}
            </div>
          )}
          {sol.principles && sol.principles.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
              {sol.principles.map((p: string, j: number) => (
                <span key={j} style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(251,191,36,0.1)', color: 'var(--accent-yellow)' }}>{p}</span>
              ))}
            </div>
          )}
          {sol.referencedPatents && sol.referencedPatents.length > 0 && (
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
              参考专利: {sol.referencedPatents.join(', ').slice(0, 100)}
            </div>
          )}
        </div>
        );
      })}
    </div>
  );
}

function EvalOutput({ output }: { output: any }) {
  if (!output) return <EmptyOutput />;
  const evaluations = Array.isArray(output) ? output : [];
  if (evaluations.length === 0) return <EmptyOutput />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {evaluations.map((item: any, i: number) => {
        const ev = item.evaluation || {};
        const scores = ev.scores || {};
        const overall = ev.overall || 0;
        return (
          <div key={i} style={{
            padding: '8px 10px', borderRadius: 6,
            background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{item.solution_title}</div>
              <span style={{ fontSize: 11, fontWeight: 700, color: overall >= 80 ? 'var(--accent-green)' : overall >= 60 ? 'var(--accent-yellow)' : 'var(--accent-red)' }}>
                {overall} 分
              </span>
            </div>
            {Object.keys(scores).length > 0 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                {Object.entries(scores as Record<string, number>).map(([key, val]) => (
                  <span key={key} style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: 'rgba(255,255,255,0.06)', color: 'var(--text-secondary)' }}>
                    {key === 'innovation' ? '创新' : key === 'feasibility' ? '可行' : key === 'completeness' ? '完整' : key === 'conversion' ? '转化' : key}: {val}
                  </span>
                ))}
              </div>
            )}
            {ev.strengths?.length > 0 && (
              <div style={{ fontSize: 10, color: 'var(--accent-green)', marginBottom: 2 }}>
                优势: {ev.strengths.slice(0, 2).join('、')}
              </div>
            )}
            {ev.recommendations?.length > 0 && (
              <div style={{ fontSize: 10, color: 'var(--accent-blue)' }}>
                建议: {ev.recommendations.slice(0, 2).join('、')}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ConversionOutput({ output, solutions, infringementResults, infringementLoading }: { output: any; solutions?: HistorySolutionsData | null; infringementResults?: Record<string, InfringementResult>; infringementLoading?: boolean }) {
  // Try agent6 workflow output first (report format)
  if (output && (output.title || output.summary || output.sections)) {
    const report = output;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {report.summary && (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, padding: 8, borderRadius: 6, background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.12)' }}>
            {report.summary}
          </div>
        )}
        {report.sections?.map((sec: any, i: number) => (
          <div key={i} style={{ padding: 8, borderRadius: 6, background: 'rgba(0,0,0,0.12)', border: '1px solid var(--border-light)' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>{sec.heading}</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{sec.content}</div>
          </div>
        ))}
        {report.topSolutions?.length > 0 && (
          <div style={{ padding: 8, borderRadius: 6, background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.12)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 4 }}>推荐方案</div>
            {report.topSolutions.map((s: string, i: number) => (
              <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '2px 0' }}>{i + 1}. {s}</div>
            ))}
          </div>
        )}
        {report.recommendations?.length > 0 && (
          <div style={{ padding: 8, borderRadius: 6, background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.12)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-purple)', marginBottom: 4 }}>实施建议</div>
            {report.recommendations.map((r: string, i: number) => (
              <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '2px 0' }}>- {r}</div>
            ))}
          </div>
        )}
        {!report.summary && !report.sections && !report.topSolutions && !report.recommendations && (
          <EmptyOutput />
        )}
      </div>
    );
  }

  // Show solutions data with auto-infringement results
  if (solutions && solutions.solutions && solutions.solutions.length > 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {solutions.solutions.map((sol: any, i: number) => {
          const ir = sol.id ? infringementResults?.[sol.id] : undefined;
          return (
          <div key={sol.id || i} style={{
            padding: '10px 12px', borderRadius: 6,
            background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
              {sol.title}
            </div>
            {sol.description && <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 4 }}>{sol.description}</div>}
            {sol.patentReferences?.length > 0 && (
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                参考专利: {sol.patentReferences.join(', ').slice(0, 120)}
              </div>
            )}
            {/* Auto-infringement analysis */}
            {infringementLoading && !ir && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0' }}>
                <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 10, color: 'var(--accent-blue)' }} />
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>正在分析侵权风险...</span>
              </div>
            )}
            {ir && (
              <div style={{ marginTop: 6, padding: 8, borderRadius: 6, background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.12)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <i className="fa-solid fa-shield-halved" style={{ fontSize: 10, color: 'var(--accent-red)' }} />
                  <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-primary)' }}>侵权分析</span>
                  <RiskBadgeSmall level={ir.riskLevel} />
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 4 }}>{ir.analysisSummary}</div>
                {ir.keyRecommendations?.length > 0 && (
                  <div style={{ fontSize: 10, color: 'var(--accent-green)' }}>
                    {ir.keyRecommendations.slice(0, 2).map((r: string, j: number) => (
                      <div key={j}>• {r}</div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          );
        })}
      </div>
    );
  }

  return <EmptyOutput />;
}

function RiskBadgeSmall({ level }: { level: string }) {
  const color = level === '高' ? 'var(--accent-red)' : level === '中' ? 'var(--accent-yellow)' : level === '低' ? 'var(--accent-green)' : 'var(--text-tertiary)';
  const bg = level === '高' ? 'rgba(248,113,113,0.15)' : level === '中' ? 'rgba(251,191,36,0.15)' : level === '低' ? 'rgba(74,222,128,0.15)' : 'rgba(100,116,139,0.1)';
  return (
    <span style={{ padding: '1px 6px', borderRadius: 3, fontSize: 9, fontWeight: 600, background: bg, color }}>
      {level}
    </span>
  );
}

function EmptyOutput() {
  return <div style={{ fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', padding: 8 }}>暂无数据</div>;
}

// ─── Step Card ───────────────────────────────────────

function StepCard({ step, output, duration, status, defaultOpen, solutions, infringementResults, infringementLoading }: StepCardProps & { solutions?: HistorySolutionsData | null; infringementResults?: Record<string, InfringementResult>; infringementLoading?: boolean }) {
  const [open, setOpen] = useState(defaultOpen || false);
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';

  const statusLabel = isCompleted ? '已完成' : isFailed ? '失败' : status === 'running' ? '运行中' : '等待中';
  const statusColor = isCompleted ? 'var(--accent-green)' : isFailed ? 'var(--accent-red)' : 'var(--text-tertiary)';

  const stepOutput = useMemo(() => {
    if (!output) return null;
    try { return typeof output === 'string' ? JSON.parse(output) : output; } catch { return output; }
  }, [output]);

  return (
    <div style={{
      borderRadius: 8, overflow: 'hidden',
      border: `1px solid ${open ? step.color : 'var(--border-light)'}`,
      transition: 'border-color 0.2s',
    }}>
      {/* Header */}
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 12px', cursor: 'pointer',
          background: open ? `${step.color}08` : 'transparent',
          transition: 'background 0.15s',
        }}
      >
        <i className={step.icon} style={{ fontSize: 12, color: step.color, width: 16 }} />
        <div style={{ flex: 1, fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
          {step.label}
        </div>
        {duration && <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{duration}</span>}
        <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: `${statusColor}15`, color: statusColor }}>
          {statusLabel}
        </span>
        <i className={`fa-solid fa-chevron-${open ? 'up' : 'down'}`} style={{ fontSize: 9, color: 'var(--text-tertiary)', transition: 'transform 0.2s' }} />
      </div>

      {/* Body */}
      {open && (
        <div style={{ padding: '8px 12px 12px', borderTop: '1px solid var(--border-light)' }}>
          {stepOutput ? (
            <StepOutputRenderer phaseId={step.phaseId} output={stepOutput} solutions={solutions || null} infringementResults={infringementResults || {}} infringementLoading={infringementLoading || false} />
          ) : (
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', padding: 8 }}>
              {status === 'pending' ? '该步骤尚未执行' : '暂无数据'}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StepOutputRenderer({ phaseId, output, solutions, infringementResults, infringementLoading }: { phaseId: string; output: any; solutions: HistorySolutionsData | null; infringementResults?: Record<string, InfringementResult>; infringementLoading?: boolean }) {
  switch (phaseId) {
    case 'demand_portrait': return <DemandOutput output={output} />;
    case 'problem_modeling': return <ModelingOutput output={output} />;
    case 'patent_search': return <PatentOutput output={output} />;
    case 'solution_gen': return <SolutionOutput output={output} solutionsData={solutions} />;
    case 'evaluation': return <EvalOutput output={output} />;
    case 'conversion': return <ConversionOutput output={output} solutions={solutions} infringementResults={infringementResults} infringementLoading={infringementLoading} />;
    default: return <EmptyOutput />;
  }
}

// ─── Status Badge ────────────────────────────────────

function StatusBadge({ workflow }: { workflow: WorkflowState }) {
  if (workflow.status === 'completed') {
    return (
      <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(74,222,128,0.15)', color: 'var(--accent-green)' }}>
        <i className="fa-solid fa-check" style={{ marginRight: 3 }} /> 已完成
      </span>
    );
  }
  if (workflow.status === 'failed') {
    return (
      <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(248,113,113,0.15)', color: 'var(--accent-red)' }}>
        <i className="fa-solid fa-xmark" style={{ marginRight: 3 }} /> 失败
      </span>
    );
  }
  return null;
}

// ─── Agent to Phase ID mapping ──────────────────────

const PHASE_TO_AGENT: Record<string, string> = {
  demand_portrait: 'agent1',
  problem_modeling: 'agent2',
  patent_search: 'agent5',
  solution_gen: 'agent3',
  evaluation: 'agent4',
  conversion: 'agent6',
};

// ─── Main Component ─────────────────────────────────

export function WorkflowArchiveDetail({ taskId, onBack }: WorkflowArchiveDetailProps) {
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [solutions, setSolutions] = useState<HistorySolutionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [taskTitle, setTaskTitle] = useState('');
  const [infringementResults, setInfringementResults] = useState<Record<string, InfringementResult>>({});
  const [infringementLoading, setInfringementLoading] = useState(false);

  // Fetch: try solutions data for task + workflow for step outputs
  useEffect(() => {
    if (!taskId) return;
    setLoading(true);
    setError('');

    Promise.all([
      historySolutionsApi.getData(taskId).catch(() => null),
      workflowApi.getByTaskId(taskId).catch(() => null),
    ])
      .then(([solutionsData, workflowData]) => {
        if (solutionsData) {
          setSolutions(solutionsData);
          setTaskTitle(solutionsData.taskTitle);
        }
        if (workflowData) {
          setWorkflow(workflowData);
          // 从 workflow 拿 taskTitle（如果 solutions API 没返回）
          if (!solutionsData && workflowData.taskId) {
            // task title from task record
          }
        }
        if (!solutionsData && !workflowData) {
          setError('无法加载任务数据');
        }
      })
      .catch((err) => setError(err?.message || '加载失败'))
      .finally(() => setLoading(false));
  }, [taskId]);

  // Auto-run infringement analysis when solutions load
  useEffect(() => {
    if (!solutions?.solutions?.length) return;
    setInfringementLoading(true);
    Promise.allSettled(
      solutions.solutions.map((sol: any) =>
        historySolutionsApi.checkInfringement(sol.id).then((result) => ({ id: sol.id, result }))
      )
    ).then((outcomes) => {
      const results: Record<string, InfringementResult> = {};
      outcomes.forEach((o) => {
        if (o.status === 'fulfilled') results[o.value.id] = o.value.result;
      });
      setInfringementResults(results);
    }).finally(() => setInfringementLoading(false));
  }, [solutions]);

  // 取 taskTitle
  useEffect(() => {
    if (taskTitle || !taskId) return;
    // fallback: fetch task title
    import('../../api/tasks').then(({ tasksApi }) => {
      tasksApi.list({ pageSize: 1 }).then((res) => {
        const t = res.data?.find((t: any) => t.id === taskId);
        if (t) setTaskTitle(t.title);
      });
    });
  }, [taskId, taskTitle]);

  // Build step data
  const stepData = useMemo(() => {
    if (!workflow) return [];
    return WORKFLOW_STEPS.map((step) => {
      const agentId = PHASE_TO_AGENT[step.phaseId];
      const agentStep: AgentStep | undefined = workflow.steps.find(
        (s) => s.agentId === agentId
      );
      return {
        step,
        output: agentStep?.output || null,
        duration: agentStep?.duration,
        status: (agentStep?.status || 'pending') as 'pending' | 'running' | 'completed' | 'failed',
      };
    });
  }, [workflow]);

  if (loading) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, minHeight: 300 }}>
        <div style={{ textAlign: 'center' }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 24, color: 'var(--accent-blue)', marginBottom: 12, display: 'block' }} />
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>加载历史方案库数据...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, minHeight: 300, gap: 12 }}>
        <i className="fa-solid fa-circle-exclamation" style={{ fontSize: 24, color: 'var(--accent-red)' }} />
        <span style={{ fontSize: 13, color: 'var(--accent-red)' }}>{error}</span>
        <button onClick={onBack} style={{ padding: '6px 16px', borderRadius: 6, fontSize: 12, background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit' }}>
          返回列表
        </button>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, minHeight: 300, gap: 12 }}>
        <i className="fa-solid fa-folder-open" style={{ fontSize: 32, color: 'var(--text-tertiary)', opacity: 0.3 }} />
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>该任务暂无工作流数据</span>
        <button onClick={onBack} style={{ padding: '6px 16px', borderRadius: 6, fontSize: 12, background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit' }}>
          返回列表
        </button>
      </div>
    );
  }

  const completedCount = stepData.filter((s) => s.status === 'completed').length;
  const totalSteps = stepData.length;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: 1, minHeight: 0 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={onBack} style={{
            display: 'flex', alignItems: 'center', gap: 4,
            padding: '5px 10px', borderRadius: 5, fontSize: 11,
            background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
            color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
          }}>
            <i className="fa-solid fa-arrow-left" /> 返回
          </button>
          <div className="card-title" style={{ margin: 0 }}>
            <i className="fa-solid fa-clock-rotate-left" style={{ marginRight: 8, color: 'var(--accent-red)' }} />
            {taskTitle || '历史方案库'}
          </div>
          {workflow && <StatusBadge workflow={workflow} />}
        </div>
      </div>

      {/* Summary stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        <div style={{ textAlign: 'center', padding: '8px', borderRadius: 6, background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-blue)', marginBottom: 2 }}>{completedCount}/{totalSteps}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>完成步骤</div>
        </div>
        <div style={{ textAlign: 'center', padding: '8px', borderRadius: 6, background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.15)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-green)', marginBottom: 2 }}>
            {solutions?.solutions?.length || 0}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>生成方案</div>
        </div>
        <div style={{ textAlign: 'center', padding: '8px', borderRadius: 6, background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.15)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-red)', marginBottom: 2 }}>
            {solutions?.solutions?.reduce((sum: number, s: any) => sum + (s.patentReferences?.length || 0), 0) || 0}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>关联专利</div>
        </div>
      </div>

      {/* Step timeline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, overflowY: 'auto', flex: 1 }}>
        {stepData.map((item, i) => (
          <StepCard
            key={item.step.phaseId}
            step={item.step}
            output={item.output}
            duration={item.duration}
            status={item.status}
            defaultOpen={item.status === 'completed' && i === stepData.length - 1}
            solutions={item.step.phaseId === 'conversion' || item.step.phaseId === 'solution_gen' ? solutions : undefined}
            infringementResults={item.step.phaseId === 'conversion' ? infringementResults : undefined}
            infringementLoading={item.step.phaseId === 'conversion' ? infringementLoading : undefined}
          />
        ))}
      </div>
    </div>
  );
}
