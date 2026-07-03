import { useState } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { workflowApi } from '../../api/workflow';
import { StepRunningIndicator } from '../../components/ui/StepRunningIndicator';

interface PatentData {
  id?: string;
  title?: string;
  summary?: string;
  abstract?: string;
  applicant?: string;
  inventor?: string;
  mainIpc?: string;
  documentNumber?: string;
  patent_number?: string;
  relevance_score?: number;
  source?: string;
}

function RelevanceBadge({ score }: { score?: number }) {
  if (!score && score !== 0) return null;
  const pct = Math.round(score * 100);
  const color =
    pct >= 70
      ? 'var(--accent-green)'
      : pct >= 40
        ? 'var(--accent-yellow)'
        : 'var(--text-tertiary)';
  return (
    <span
      style={{
        fontSize: 10,
        padding: '1px 6px',
        borderRadius: 3,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        color,
        fontWeight: 500,
      }}
    >
      相关度 {pct}%
    </span>
  );
}

export function PatentSearchView({ output }: { output: unknown }) {
  const workflow = useWorkflowStore((s) => s.workflow);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const patents: PatentData[] = Array.isArray(output)
    ? (output as PatentData[])
    : ((output as Record<string, unknown>)?.patents as PatentData[]) || [];

  if (!workflow || patents.length === 0) {
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
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无专利数据</span>
      </div>
    );
  }

  if (submitted) {
    return null;
  }

  const allRated = patents.every((_, i: number) => (ratings[String(i)] ?? 0) > 0);

  const handleSubmit = async () => {
    if (!selectedTaskId || !allRated || submitting) return;
    setSubmitting(true);
    try {
      const ratingsPayload = patents.map((patent, i: number) => ({
        demandId: (patent.id as string) || String(i),
        score: ratings[String(i)] || 0,
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
      className="card"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        width: '100%',
        flex: 1,
        minHeight: 0,
      }}
    >
      <div className="card-title">
        专利检索
        <span
          style={{
            marginLeft: 8,
            fontSize: 11,
            padding: '2px 8px',
            borderRadius: 10,
            background: 'rgba(59,130,246,0.15)',
            color: 'var(--accent-blue)',
          }}
        >
          {patents.length} 项
        </span>
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
        请对以下专利的相关度进行评分，评分后确认进入下一步
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1, minHeight: 0 }}>
        {patents.map((patent, i: number) => (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 12,
              padding: '10px 14px',
              borderRadius: 8,
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border)',
              flex: '1 1 auto',
              minHeight: 120,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              {/* 专利标题 */}
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  marginBottom: 4,
                }}
              >
                {patent.title || '未命名专利'}
              </div>

              {/* 元数据标签行 */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 4 }}>
                {(patent.documentNumber || patent.patent_number) && (
                  <span
                    style={{
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 3,
                      background: 'rgba(59,130,246,0.1)',
                      color: 'var(--accent-blue)',
                    }}
                  >
                    {patent.documentNumber || patent.patent_number}
                  </span>
                )}
                {patent.applicant && (
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                    {patent.applicant}
                  </span>
                )}
                {patent.mainIpc && (
                  <span
                    style={{
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 3,
                      background: 'rgba(167,139,250,0.1)',
                      color: 'var(--accent-purple)',
                    }}
                  >
                    IPC: {patent.mainIpc}
                  </span>
                )}
                <RelevanceBadge score={patent.relevance_score} />
              </div>

              {/* 摘要 */}
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {(patent.summary || patent.abstract || '').slice(0, 250)}
                {(patent.summary || patent.abstract || '').length > 250 ? '...' : ''}
              </div>
            </div>

            {/* 星级评分 */}
            <div style={{ display: 'flex', gap: 2, cursor: 'pointer', flexShrink: 0 }}>
              {[1, 2, 3, 4, 5].map((star) => (
                <span
                  key={star}
                  onClick={(e) => {
                    e.stopPropagation();
                    setRatings((prev) => ({ ...prev, [String(i)]: star }));
                  }}
                  style={{
                    fontSize: 18,
                    color:
                      star <= (ratings[String(i)] || 0) ? '#fbbf24' : 'rgba(255,255,255,0.15)',
                  }}
                >
                  <i className="fa-solid fa-star" />
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {submitError && (
        <div
          style={{
            padding: '8px 12px',
            borderRadius: 6,
            background: 'rgba(248,113,113,0.1)',
            border: '1px solid rgba(248,113,113,0.3)',
            color: 'var(--accent-red)',
            fontSize: 12,
          }}
        >
          {submitError}
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
        <button
          onClick={handleSubmit}
          disabled={!allRated || submitting || submitted}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 20px',
            borderRadius: 6,
            fontSize: 13,
            background:
              !allRated || submitting
                ? 'var(--text-tertiary)'
                : submitted
                  ? 'var(--accent-green)'
                  : 'var(--accent)',
            border: 'none',
            color: '#fff',
            cursor: !allRated || submitting ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit',
          }}
        >
          {submitting ? (
            <>
              <StepRunningIndicator phaseId="patent_search" size={16} color="#fff" /> 提交中...
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
  );
}
