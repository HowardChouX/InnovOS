import { useState, useEffect, useMemo } from 'react';
import { workflowApi } from '../../api/workflow';
import { historySolutionsApi } from '../../api/historySolutions';
import type { WorkflowState, AgentStep } from '../../types/workflow';
import { WORKFLOW_STEPS } from '../../types/workflow';
import type {
  HistorySolutionsData,
  InfringementResult,
  SolutionWithEval,
} from '../../api/historySolutions';
import type { Task } from '../../types/task';
import {
  ArrowLeft,
  History,
  Check,
  X as XIcon,
  ChevronDown,
  ChevronUp,
  LoaderCircle,
  AlertCircle,
  FolderOpen,
  Shield,
  Star,
  CircleHelp,
  Search,
  Box,
  FileText,
  WandSparkles,
  TrendingUp,
  FileSignature,
  Video,
} from 'lucide-react';

// ─── Lucide icon map ────────────────────────────────

const PHASE_ICONS: Record<
  string,
  React.ComponentType<{ size?: number; style?: React.CSSProperties }>
> = {
  demand_analysis: Search,
  problem_definition: Box,
  patent_search: FileText,
  solution_gen: WandSparkles,
  evaluation: TrendingUp,
  video_display: Video,
};

// ─── Types ───────────────────────────────────────────

interface StepCardProps {
  step: (typeof WORKFLOW_STEPS)[number];
  output: unknown;
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
    <span
      style={{
        color: '#fbbf24',
        fontSize: 10,
        letterSpacing: -1,
        whiteSpace: 'nowrap',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 1,
      }}
    >
      {Array.from({ length: max }, (_, i) => (
        <Star
          key={i}
          size={9}
          fill={i < count ? '#fbbf24' : 'transparent'}
          style={{ opacity: i < count ? 1 : 0.15 }}
        />
      ))}
    </span>
  );
}

function getItemRating(itemId: string, output: unknown): number | null {
  if (!output) return null;
  const out = output as Record<string, unknown>;
  const ratings = out.ratings as Array<Record<string, unknown>> | undefined;
  if (!ratings) return null;
  const found = ratings.find((r: unknown) => {
    const rt = r as Record<string, unknown>;
    return (
      rt.demandId === itemId ||
      rt.demand_id === itemId ||
      rt.innovationId === itemId ||
      rt.innovation_id === itemId ||
      String(rt.demandId) === itemId ||
      String(rt.demand_id) === itemId
    );
  });
  return (found?.score as number) || null;
}

// ─── Step renderers ──────────────────────────────────

function DemandOutput({ output }: { output: unknown }) {
  if (!output) return <EmptyOutput />;
  const out = output as Record<string, unknown>;
  const demands = (out.demands as Array<Record<string, unknown>>) || [];
  if (demands.length === 0) return <EmptyOutput />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {demands.map((d: unknown, i: number) => {
        const item = d as Record<string, unknown>;
        const rating =
          getItemRating(item.id as string, output) || (item.user_rating as number | undefined);
        return (
          <div
            key={(item.id as string) || i}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.15)',
              border: '1px solid var(--border-light)',
            }}
          >
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-primary)',
                marginBottom: 2,
              }}
            >
              {item.description as string}
            </div>
            <div
              style={{
                display: 'flex',
                gap: 6,
                fontSize: 10,
                color: 'var(--text-tertiary)',
                alignItems: 'center',
              }}
            >
              <span
                style={{
                  padding: '1px 5px',
                  borderRadius: 3,
                  background: 'rgba(59,130,246,0.1)',
                  color: 'var(--accent-blue)',
                }}
              >
                {item.category as string}
              </span>
              <span>{item.source as string}</span>
              {rating != null && <Stars count={rating} />}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ModelingOutput({ output }: { output: unknown }) {
  if (!output) return <EmptyOutput />;
  const out = output as Record<string, unknown>;
  const innovations = (out.innovations as Array<Record<string, unknown>>) || [];
  if (innovations.length === 0) return <EmptyOutput />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {innovations.map((inn: unknown, i: number) => {
        const item = inn as Record<string, unknown>;
        const rating =
          getItemRating(item.id as string, output) || (item.user_rating as number | undefined);
        const principle = item.principle as string | undefined;
        const expectedEffect = item.expected_effect as string | undefined;
        return (
          <div
            key={(item.id as string) || i}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.15)',
              border: '1px solid var(--border-light)',
            }}
          >
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-primary)',
                marginBottom: 2,
              }}
            >
              {item.description as string}
            </div>
            <div
              style={{
                display: 'flex',
                gap: 4,
                flexWrap: 'wrap',
                fontSize: 10,
                color: 'var(--text-tertiary)',
                alignItems: 'center',
              }}
            >
              {principle && (
                <span
                  style={{
                    padding: '1px 5px',
                    borderRadius: 3,
                    background: 'rgba(251,191,36,0.1)',
                    color: 'var(--accent-yellow)',
                  }}
                >
                  {principle}
                </span>
              )}
              {expectedEffect && <span>{expectedEffect}</span>}
              {rating != null && <Stars count={rating} />}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PatentOutput({ output }: { output: unknown }) {
  if (!output) return <EmptyOutput />;
  const patents: unknown[] = Array.isArray(output)
    ? output
    : ((output as Record<string, unknown>).patents as unknown[]) || [];
  if (patents.length === 0) return <EmptyOutput />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {patents.slice(0, 20).map((p: unknown, i: number) => {
        const item = p as Record<string, unknown>;
        const rating = getItemRating(String(i), output) || (item.user_rating as number | undefined);
        const title = (item._title as string) || (item.title as string) || '未命名专利';
        const patentNumber = item.patent_number as string | undefined;
        const abstract = item.abstract as string | undefined;
        const description = item.description as string | undefined;
        return (
          <div
            key={i}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.15)',
              border: '1px solid var(--border-light)',
            }}
          >
            <div
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}
            >
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    marginBottom: 2,
                  }}
                >
                  {title}
                </div>
                {patentNumber && (
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 2 }}>
                    专利号: {patentNumber}
                  </div>
                )}
                {(abstract || description) && (
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--text-secondary)',
                      lineHeight: 1.5,
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {(abstract || description || '').slice(0, 200)}
                  </div>
                )}
              </div>
              {rating != null && <Stars count={rating} />}
            </div>
          </div>
        );
      })}
      {patents.length > 20 && (
        <div
          style={{ fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', padding: 4 }}
        >
          还有 {patents.length - 20} 项专利
        </div>
      )}
    </div>
  );
}

function SolutionOutput({
  output,
  solutionsData,
}: {
  output: unknown;
  solutionsData?: HistorySolutionsData | null;
}) {
  const solutionRatingMap = useMemo(() => {
    const map: Record<string, number> = {};
    if (solutionsData?.solutions) {
      for (const s of solutionsData.solutions) {
        const key = (s.title || '').trim().toLowerCase();
        if (s.rating != null) map[key] = s.rating;
      }
    }
    return map;
  }, [solutionsData]);

  if (!output) return <EmptyOutput />;
  const solutions = Array.isArray(output) ? (output as unknown[]) : [];
  if (solutions.length === 0) return <EmptyOutput />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {solutions.map((sol: unknown, i: number) => {
        const item = sol as Record<string, unknown>;
        const fromOutput = getItemRating(String(i), output);
        const fromApi = solutionRatingMap[((item.title as string) || '').trim().toLowerCase()];
        const rating = fromOutput || fromApi || (item.user_rating as number | undefined);
        const description = item.description as string | undefined;
        const principles = item.principles as string[] | undefined;
        const referencedPatents = item.referencedPatents as string[] | undefined;
        return (
          <div
            key={i}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.15)',
              border: '1px solid var(--border-light)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: 2,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                方案 {i + 1}: {item.title as string}
              </div>
              {rating != null && <Stars count={rating} />}
            </div>
            {description && (
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--text-secondary)',
                  lineHeight: 1.5,
                  marginBottom: 4,
                }}
              >
                {description}
              </div>
            )}
            {principles && principles.length > 0 && (
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
                {principles.map((p: string, j: number) => (
                  <span
                    key={j}
                    style={{
                      fontSize: 9,
                      padding: '1px 5px',
                      borderRadius: 3,
                      background: 'rgba(251,191,36,0.1)',
                      color: 'var(--accent-yellow)',
                    }}
                  >
                    {p}
                  </span>
                ))}
              </div>
            )}
            {referencedPatents && referencedPatents.length > 0 && (
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                参考专利: {referencedPatents.join(', ').slice(0, 100)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function EvalOutput({ output }: { output: unknown }) {
  if (!output) return <EmptyOutput />;
  const evaluations: unknown[] = Array.isArray(output) ? output : [];
  if (evaluations.length === 0) return <EmptyOutput />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {evaluations.map((item: unknown, i: number) => {
        const itemRec = item as Record<string, unknown>;
        const ev = (itemRec.evaluation as Record<string, unknown>) || {};
        const scores = (ev.scores as Record<string, number>) || {};
        const overall = (ev.overall as number) || 0;
        const strengths = ev.strengths as string[] | undefined;
        const recommendations = ev.recommendations as string[] | undefined;
        return (
          <div
            key={i}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              background: 'rgba(0,0,0,0.15)',
              border: '1px solid var(--border-light)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 6,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                {itemRec.solution_title as string}
              </div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color:
                    overall >= 80
                      ? 'var(--accent-green)'
                      : overall >= 60
                        ? 'var(--accent-yellow)'
                        : 'var(--accent-red)',
                }}
              >
                {overall} 分
              </span>
            </div>
            {Object.keys(scores).length > 0 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                {Object.entries(scores).map(([key, val]) => (
                  <span
                    key={key}
                    style={{
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 3,
                      background: 'rgba(255,255,255,0.06)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {key === 'innovation'
                      ? '创新'
                      : key === 'feasibility'
                        ? '可行'
                        : key === 'completeness'
                          ? '完整'
                          : key === 'conversion'
                            ? '转化'
                            : key}
                    : {val}
                  </span>
                ))}
              </div>
            )}
            {strengths && strengths.length > 0 && (
              <div style={{ fontSize: 10, color: 'var(--accent-green)', marginBottom: 2 }}>
                优势: {strengths.slice(0, 2).join('、')}
              </div>
            )}
            {recommendations && recommendations.length > 0 && (
              <div style={{ fontSize: 10, color: 'var(--accent-blue)' }}>
                建议: {recommendations.slice(0, 2).join('、')}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ConversionOutput({
  output,
  solutions,
  infringementResults,
  infringementLoading,
}: {
  output: unknown;
  solutions?: HistorySolutionsData | null;
  infringementResults?: Record<string, InfringementResult>;
  infringementLoading?: boolean;
}) {
  if (output) {
    const report = output as Record<string, unknown>;
    const summary = report.summary as string | undefined;
    const sections = report.sections as Array<Record<string, unknown>> | undefined;
    const topSolutions = report.topSolutions as string[] | undefined;
    const recommendations = report.recommendations as string[] | undefined;
    if (summary || sections || topSolutions || recommendations) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {summary && (
            <div
              style={{
                fontSize: 12,
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
                padding: 8,
                borderRadius: 6,
                background: 'rgba(74,222,128,0.06)',
                border: '1px solid rgba(74,222,128,0.12)',
              }}
            >
              {summary}
            </div>
          )}
          {sections?.map((sec: unknown, i: number) => {
            const section = sec as Record<string, unknown>;
            return (
              <div
                key={i}
                style={{
                  padding: 8,
                  borderRadius: 6,
                  background: 'rgba(0,0,0,0.12)',
                  border: '1px solid var(--border-light)',
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    marginBottom: 4,
                  }}
                >
                  {section.heading as string}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--text-secondary)',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {section.content as string}
                </div>
              </div>
            );
          })}
          {topSolutions && topSolutions.length > 0 && (
            <div
              style={{
                padding: 8,
                borderRadius: 6,
                background: 'rgba(59,130,246,0.06)',
                border: '1px solid rgba(59,130,246,0.12)',
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--accent-blue)',
                  marginBottom: 4,
                }}
              >
                推荐方案
              </div>
              {topSolutions.map((s: string, i: number) => (
                <div
                  key={i}
                  style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '2px 0' }}
                >
                  {i + 1}. {s}
                </div>
              ))}
            </div>
          )}
          {recommendations && recommendations.length > 0 && (
            <div
              style={{
                padding: 8,
                borderRadius: 6,
                background: 'rgba(139,92,246,0.06)',
                border: '1px solid rgba(139,92,246,0.12)',
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--accent-purple)',
                  marginBottom: 4,
                }}
              >
                实施建议
              </div>
              {recommendations.map((r: string, i: number) => (
                <div
                  key={i}
                  style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '2px 0' }}
                >
                  - {r}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
  }

  if (solutions && solutions.solutions && solutions.solutions.length > 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {solutions.solutions.map((sol: SolutionWithEval) => {
          const ir = sol.id ? infringementResults?.[sol.id] : undefined;
          return (
            <div
              key={sol.id || undefined}
              style={{
                padding: '10px 12px',
                borderRadius: 6,
                background: 'rgba(0,0,0,0.15)',
                border: '1px solid var(--border-light)',
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  marginBottom: 4,
                }}
              >
                {sol.title}
              </div>
              {sol.description && (
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--text-secondary)',
                    lineHeight: 1.5,
                    marginBottom: 4,
                  }}
                >
                  {sol.description}
                </div>
              )}
              {sol.patentReferences?.length > 0 && (
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                  参考专利: {sol.patentReferences.join(', ').slice(0, 120)}
                </div>
              )}
              {infringementLoading && !ir && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0' }}>
                  <LoaderCircle
                    size={10}
                    className="animate-spin"
                    style={{ color: 'var(--accent-blue)' }}
                  />
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                    正在分析侵权风险...
                  </span>
                </div>
              )}
              {ir && (
                <div
                  style={{
                    marginTop: 6,
                    padding: 8,
                    borderRadius: 6,
                    background: 'rgba(248,113,113,0.06)',
                    border: '1px solid rgba(248,113,113,0.12)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <Shield size={10} style={{ color: 'var(--accent-red)' }} />
                    <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-primary)' }}>
                      侵权分析
                    </span>
                    <RiskBadgeSmall level={ir.riskLevel} />
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: 'var(--text-secondary)',
                      lineHeight: 1.5,
                      marginBottom: 4,
                    }}
                  >
                    {ir.analysisSummary}
                  </div>
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
  const color =
    level === '高'
      ? 'var(--accent-red)'
      : level === '中'
        ? 'var(--accent-yellow)'
        : level === '低'
          ? 'var(--accent-green)'
          : 'var(--text-tertiary)';
  const bg =
    level === '高'
      ? 'rgba(248,113,113,0.15)'
      : level === '中'
        ? 'rgba(251,191,36,0.15)'
        : level === '低'
          ? 'rgba(74,222,128,0.15)'
          : 'rgba(100,116,139,0.1)';
  return (
    <span
      style={{
        padding: '1px 6px',
        borderRadius: 3,
        fontSize: 9,
        fontWeight: 600,
        background: bg,
        color,
      }}
    >
      {level}
    </span>
  );
}

function EmptyOutput() {
  return (
    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', textAlign: 'center', padding: 8 }}>
      暂无数据
    </div>
  );
}

// ─── Step Card ───────────────────────────────────────

function StepCard({
  step,
  output,
  duration,
  status,
  defaultOpen,
  solutions,
  infringementResults,
  infringementLoading,
}: StepCardProps & {
  solutions?: HistorySolutionsData | null;
  infringementResults?: Record<string, InfringementResult>;
  infringementLoading?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen || false);
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';

  const statusLabel = isCompleted
    ? '已完成'
    : isFailed
      ? '失败'
      : status === 'running'
        ? '运行中'
        : '等待中';
  const statusColor = isCompleted
    ? 'var(--accent-green)'
    : isFailed
      ? 'var(--accent-red)'
      : 'var(--text-tertiary)';

  const stepOutput = useMemo(() => {
    if (!output) return null;
    try {
      return typeof output === 'string' ? JSON.parse(output) : output;
    } catch {
      return output;
    }
  }, [output]);

  const PhaseIcon = PHASE_ICONS[step.phaseId] || CircleHelp;

  return (
    <div
      style={{
        borderRadius: 8,
        overflow: 'hidden',
        border: `1px solid ${open ? step.color : 'var(--border-light)'}`,
        transition: 'border-color 0.2s',
      }}
    >
      {/* Header */}
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '9px 12px',
          cursor: 'pointer',
          background: open ? `${step.color}08` : 'transparent',
          transition: 'background 0.15s',
        }}
      >
        <PhaseIcon size={14} style={{ color: step.color, flexShrink: 0 }} />
        <div style={{ flex: 1, fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
          {step.label}
        </div>
        {duration && (
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{duration}</span>
        )}
        <span
          style={{
            fontSize: 10,
            padding: '1px 6px',
            borderRadius: 3,
            background: `${statusColor}15`,
            color: statusColor,
          }}
        >
          {statusLabel}
        </span>
        {open ? (
          <ChevronUp
            size={11}
            style={{ color: 'var(--text-tertiary)', transition: 'transform 0.2s' }}
          />
        ) : (
          <ChevronDown
            size={11}
            style={{ color: 'var(--text-tertiary)', transition: 'transform 0.2s' }}
          />
        )}
      </div>

      {/* Body */}
      {open && (
        <div style={{ padding: '8px 12px 12px', borderTop: '1px solid var(--border-light)' }}>
          {stepOutput ? (
            <StepOutputRenderer
              phaseId={step.phaseId}
              output={stepOutput}
              solutions={solutions || null}
              infringementResults={infringementResults || {}}
              infringementLoading={infringementLoading || false}
            />
          ) : (
            <div
              style={{
                fontSize: 11,
                color: 'var(--text-tertiary)',
                textAlign: 'center',
                padding: 8,
              }}
            >
              {status === 'pending' ? '该步骤尚未执行' : '暂无数据'}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StepOutputRenderer({
  phaseId,
  output,
  solutions,
  infringementResults,
  infringementLoading,
}: {
  phaseId: string;
  output: unknown;
  solutions: HistorySolutionsData | null;
  infringementResults?: Record<string, InfringementResult>;
  infringementLoading?: boolean;
}) {
  switch (phaseId) {
    case 'demand_analysis':
    case 'demand_portrait':
      return <DemandOutput output={output} />;
    case 'problem_definition':
    case 'problem_modeling':
      return <ModelingOutput output={output} />;
    case 'patent_search':
      return <PatentOutput output={output} />;
    case 'solution_gen':
      return <SolutionOutput output={output} solutionsData={solutions} />;
    case 'evaluation':
      return <EvalOutput output={output} />;
    case 'video_display':
    case 'conversion':
      return (
        <ConversionOutput
          output={output}
          solutions={solutions}
          infringementResults={infringementResults}
          infringementLoading={infringementLoading}
        />
      );
    default:
      return <EmptyOutput />;
  }
}

// ─── Status Badge ────────────────────────────────────

function StatusBadge({ workflow }: { workflow: WorkflowState }) {
  if (workflow.status === 'completed') {
    return (
      <span
        style={{
          fontSize: 10,
          padding: '2px 8px',
          borderRadius: 4,
          background: 'rgba(74,222,128,0.15)',
          color: 'var(--accent-green)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 3,
        }}
      >
        <Check size={10} /> 已完成
      </span>
    );
  }
  if (workflow.status === 'failed') {
    return (
      <span
        style={{
          fontSize: 10,
          padding: '2px 8px',
          borderRadius: 4,
          background: 'rgba(248,113,113,0.15)',
          color: 'var(--accent-red)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 3,
        }}
      >
        <XIcon size={10} /> 失败
      </span>
    );
  }
  return null;
}

// ─── Agent to Phase ID mapping ──────────────────────

const PHASE_TO_AGENT: Record<string, string> = {
  demand_analysis: 'agent1',
  demand_portrait: 'agent1',
  problem_definition: 'agent2',
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
  const [infringementResults, setInfringementResults] = useState<
    Record<string, InfringementResult>
  >({});
  const [infringementLoading, setInfringementLoading] = useState(false);

  // Fetch: try solutions data for task + workflow for step outputs
  useEffect(() => {
    if (!taskId) return;
    // loading already true from useState(true) initialization

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
    (async () => {
      await Promise.resolve(); // yield to satisfy hooks rule
      setInfringementLoading(true);
    })();
    Promise.allSettled(
      solutions.solutions.map((sol: SolutionWithEval) =>
        historySolutionsApi.checkInfringement(sol.id).then((result) => ({ id: sol.id, result })),
      ),
    )
      .then((outcomes) => {
        const results: Record<string, InfringementResult> = {};
        outcomes.forEach((o) => {
          if (o.status === 'fulfilled') results[o.value.id] = o.value.result;
        });
        setInfringementResults(results);
      })
      .finally(() => setInfringementLoading(false));
  }, [solutions]);

  // 取 taskTitle
  useEffect(() => {
    if (taskTitle || !taskId) return;
    import('../../api/tasks').then(({ tasksApi }) => {
      tasksApi.list({ pageSize: 1 }).then((res) => {
        const t = res.data?.find((t: Task) => t.id === taskId);
        if (t) setTaskTitle(t.title);
      });
    });
  }, [taskId, taskTitle]);

  // Build step data
  const stepData = useMemo(() => {
    if (!workflow) return [];
    return WORKFLOW_STEPS.map((step) => {
      const agentId = PHASE_TO_AGENT[step.phaseId];
      const agentStep: AgentStep | undefined = workflow.steps.find((s) => s.agentId === agentId);
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
      <div
        className="card"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          minHeight: 300,
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <LoaderCircle
            size={28}
            className="animate-spin"
            style={{ color: 'var(--accent-blue)', margin: '0 auto 12px', display: 'block' }}
          />
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            加载历史方案库数据...
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          minHeight: 300,
          gap: 12,
        }}
      >
        <AlertCircle size={28} style={{ color: 'var(--accent-red)' }} />
        <span style={{ fontSize: 13, color: 'var(--accent-red)' }}>{error}</span>
        <button
          onClick={onBack}
          style={{
            padding: '6px 16px',
            borderRadius: 6,
            fontSize: 12,
            background: 'var(--accent)',
            border: 'none',
            color: '#fff',
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          返回列表
        </button>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div
        className="card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          minHeight: 300,
          gap: 12,
        }}
      >
        <FolderOpen size={32} style={{ color: 'var(--text-tertiary)', opacity: 0.3 }} />
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>该任务暂无工作流数据</span>
        <button
          onClick={onBack}
          style={{
            padding: '6px 16px',
            borderRadius: 6,
            fontSize: 12,
            background: 'var(--accent)',
            border: 'none',
            color: '#fff',
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          返回列表
        </button>
      </div>
    );
  }

  const completedCount = stepData.filter((s) => s.status === 'completed').length;
  const totalSteps = stepData.length;

  return (
    <div
      className="card"
      style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: 1, minHeight: 0 }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={onBack}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '5px 10px',
            borderRadius: 5,
            fontSize: 11,
            background: 'rgba(0,0,0,0.2)',
            border: '1px solid var(--border-light)',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontFamily: 'inherit',
            transition: 'background 0.15s',
          }}
        >
          <ArrowLeft size={12} /> 返回
        </button>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
          <History size={15} style={{ color: 'var(--accent-red)' }} />
          <span
            className="card-title"
            style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}
          >
            {taskTitle || '历史方案库'}
          </span>
          {workflow && <StatusBadge workflow={workflow} />}
        </div>
      </div>

      {/* Summary stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        <div
          style={{
            textAlign: 'center',
            padding: '8px',
            borderRadius: 6,
            background: 'rgba(59,130,246,0.08)',
            border: '1px solid rgba(59,130,246,0.15)',
          }}
        >
          <div
            style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-blue)', marginBottom: 2 }}
          >
            {completedCount}/{totalSteps}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>完成步骤</div>
        </div>
        <div
          style={{
            textAlign: 'center',
            padding: '8px',
            borderRadius: 6,
            background: 'rgba(74,222,128,0.08)',
            border: '1px solid rgba(74,222,128,0.15)',
          }}
        >
          <div
            style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-green)', marginBottom: 2 }}
          >
            {solutions?.solutions?.length || 0}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>生成方案</div>
        </div>
        <div
          style={{
            textAlign: 'center',
            padding: '8px',
            borderRadius: 6,
            background: 'rgba(248,113,113,0.08)',
            border: '1px solid rgba(248,113,113,0.15)',
          }}
        >
          <div
            style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-red)', marginBottom: 2 }}
          >
            {solutions?.solutions?.reduce(
              (sum: number, s: SolutionWithEval) => sum + (s.patentReferences?.length || 0),
              0,
            ) || 0}
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
            solutions={
              item.step.phaseId === 'conversion' || item.step.phaseId === 'solution_gen'
                ? solutions
                : undefined
            }
            infringementResults={
              item.step.phaseId === 'conversion' ? infringementResults : undefined
            }
            infringementLoading={
              item.step.phaseId === 'conversion' ? infringementLoading : undefined
            }
          />
        ))}
      </div>
    </div>
  );
}
