import { useState, useEffect } from 'react';
import { useTaskStore } from '../../store/useTaskStore';
import { historySolutionsApi } from '../../api/historySolutions';
import { StepRunningIndicator } from '../../components/ui/StepRunningIndicator';
import type {
  HistorySolutionsData,
  SolutionWithEval,
  InfringementResult,
} from '../../api/historySolutions';

const SCORE_LABELS: Record<string, string> = {
  innovation: '创新性',
  feasibility: '可行性',
  completeness: '完整性',
  conversion: '转化潜力',
};

const SCORE_COLORS: Record<string, string> = {
  innovation: 'var(--accent-purple)',
  feasibility: 'var(--accent-green)',
  completeness: 'var(--accent-blue)',
  conversion: 'var(--accent-yellow)',
};

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text-secondary)', width: 56, flexShrink: 0 }}>
        {label}
      </span>
      <div
        style={{
          flex: 1,
          height: 6,
          borderRadius: 3,
          background: 'rgba(0,0,0,0.3)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${value}%`,
            height: '100%',
            background: color,
            borderRadius: 3,
            transition: 'width 0.3s',
          }}
        />
      </div>
      <span style={{ fontSize: 11, fontWeight: 600, color, width: 28, textAlign: 'right' }}>
        {value}
      </span>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
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
        padding: '2px 10px',
        borderRadius: 4,
        fontSize: 12,
        fontWeight: 600,
        background: bg,
        color,
      }}
    >
      {level === '无法分析' ? '—' : level}
    </span>
  );
}

function InfringementPanel({
  result,
  loading,
}: {
  result: InfringementResult | null;
  loading: boolean;
}) {
  return (
    <div
      style={{
        background: 'rgba(0,0,0,0.25)',
        borderRadius: 8,
        padding: 16,
        marginTop: 12,
        border: '1px solid var(--border)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
          侵权风险分析
        </span>
      </div>

      {loading ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            padding: 40,
          }}
        >
          <StepRunningIndicator phaseId="conversion" size={48} color="var(--accent-green)" />
          <div style={{ textAlign: 'center' }}>
            <div
              style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
            >
              正在进行成果转化...
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              AI 正在生成分析报告与转化建议，请稍候
            </div>
          </div>
        </div>
      ) : result ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>风险等级：</span>
            <RiskBadge level={result.riskLevel} />
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              风险评分：{result.riskScore}/100
            </span>
          </div>

          <div
            style={{
              padding: 10,
              borderRadius: 6,
              background: 'rgba(59,130,246,0.06)',
              border: '1px solid rgba(59,130,246,0.15)',
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
              分析概要与结论
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {result.analysisSummary}
            </div>
          </div>

          {result.claimOverlaps && result.claimOverlaps.length > 0 && (
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--accent-red)',
                  marginBottom: 6,
                }}
              >
                技术特征对比
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {result.claimOverlaps.map((item, i) => (
                  <div
                    key={i}
                    style={{
                      padding: 10,
                      borderRadius: 6,
                      background: 'rgba(248,113,113,0.05)',
                      border: '1px solid rgba(248,113,113,0.12)',
                    }}
                  >
                    <div style={{ fontSize: 11, marginBottom: 2 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>方案特征：</span>
                      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                        {item.feature}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, marginBottom: 2 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>专利权利要求：</span>
                      <span style={{ color: 'var(--accent-red)' }}>{item.patentClaim}</span>
                    </div>
                    <div style={{ fontSize: 11, marginBottom: 2 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>风险：</span>
                      <span style={{ color: 'var(--accent-yellow)' }}>{item.risk}</span>
                    </div>
                    <div style={{ fontSize: 11 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>建议：</span>
                      <span style={{ color: 'var(--accent-green)' }}>{item.suggestion}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.designArounds && result.designArounds.length > 0 && (
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--accent-green)',
                  marginBottom: 6,
                }}
              >
                规避设计建议
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {result.designArounds.map((d, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      lineHeight: 1.6,
                      paddingLeft: 12,
                    }}
                  >
                    <span style={{ color: 'var(--accent-green)', marginRight: 4 }}>-</span>
                    {d}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.keyRecommendations && result.keyRecommendations.length > 0 && (
            <div
              style={{
                padding: 10,
                borderRadius: 6,
                background: 'rgba(74,222,128,0.06)',
                border: '1px solid rgba(74,222,128,0.15)',
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--accent-green)',
                  marginBottom: 4,
                }}
              >
                关键建议
              </div>
              {result.keyRecommendations.map((r, i) => (
                <div
                  key={i}
                  style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}
                >
                  {i + 1}. {r}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function SolutionCard({
  solution,
  analysisResult,
  analyzingAll,
}: {
  solution: SolutionWithEval;
  analysisResult: InfringementResult | null;
  analyzingAll: boolean;
}) {
  const [showPatents, setShowPatents] = useState(false);

  return (
    <div
      style={{
        background: 'rgba(0,0,0,0.2)',
        borderRadius: 8,
        padding: 16,
        border: '1px solid var(--border)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 12,
        }}
      >
        <div style={{ flex: 1 }}>
          <div
            style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
          >
            {solution.title}
          </div>
          {solution.principles && solution.principles.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {solution.principles.map((p, i) => (
                <span
                  key={i}
                  style={{
                    fontSize: 10,
                    padding: '1px 6px',
                    borderRadius: 3,
                    background: 'rgba(251,191,36,0.1)',
                    border: '1px solid rgba(251,191,36,0.2)',
                    color: 'var(--accent-yellow)',
                  }}
                >
                  <i className="fa-regular fa-lightbulb" style={{ marginRight: 2, fontSize: 9 }} />
                  {p}
                </span>
              ))}
            </div>
          )}
        </div>
        {analyzingAll && !analysisResult && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '5px 12px',
              borderRadius: 5,
              fontSize: 11,
              background: 'rgba(59,130,246,0.1)',
              border: '1px solid rgba(59,130,246,0.2)',
              color: 'var(--accent-blue)',
            }}
          >
            <StepRunningIndicator phaseId="conversion" size={14} color="var(--accent-blue)" /> 分析中
          </div>
        )}
      </div>

      {solution.description && (
        <div
          style={{
            fontSize: 12,
            color: 'var(--text-secondary)',
            lineHeight: 1.6,
            marginBottom: 10,
          }}
        >
          {solution.description}
        </div>
      )}

      {Object.keys(solution.evaluation).length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--text-tertiary)',
              marginBottom: 6,
            }}
          >
            评估分数
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {Object.entries(solution.evaluation).map(([key, val]) => (
              <ScoreBar
                key={key}
                label={SCORE_LABELS[key] || key}
                value={Math.round(val)}
                color={SCORE_COLORS[key] || 'var(--accent-blue)'}
              />
            ))}
          </div>
        </div>
      )}

      {solution.patentReferences.length > 0 && (
        <div>
          <div
            onClick={() => setShowPatents(!showPatents)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              cursor: 'pointer',
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--accent-blue)',
              marginBottom: showPatents ? 8 : 0,
            }}
          >
            <i
              className={`fa-solid fa-chevron-${showPatents ? 'down' : 'right'}`}
              style={{ fontSize: 9 }}
            />
            参考专利（{solution.patentReferences.length}）
          </div>
          {showPatents && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {solution.refPatents.length > 0
                ? solution.refPatents.map((p, i) => (
                    <div
                      key={i}
                      style={{
                        padding: 8,
                        borderRadius: 6,
                        background: 'rgba(59,130,246,0.05)',
                        border: '1px solid rgba(59,130,246,0.12)',
                      }}
                    >
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 500,
                          color: 'var(--text-primary)',
                          marginBottom: 2,
                        }}
                      >
                        <i
                          className="fa-regular fa-copyright"
                          style={{ marginRight: 4, fontSize: 10, color: 'var(--accent-blue)' }}
                        />
                        {p.title || p._title || '未知专利'}
                      </div>
                      {p.patent_number && (
                        <div
                          style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 2 }}
                        >
                          专利号：{p.patent_number}
                        </div>
                      )}
                      {(p.abstract || p.description) && (
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
                          {(p.abstract || p.description || '').slice(0, 200)}
                        </div>
                      )}
                    </div>
                  ))
                : solution.patentReferences.map((name, i) => (
                    <div
                      key={i}
                      style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '4px 0' }}
                    >
                      <i
                        className="fa-regular fa-copyright"
                        style={{ marginRight: 4, fontSize: 9 }}
                      />
                      {name}
                    </div>
                  ))}
            </div>
          )}
        </div>
      )}

      {analysisResult && <InfringementPanel result={analysisResult} loading={false} />}
    </div>
  );
}

export function ConversionView(props: { output: unknown }) {
  void props;
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  if (!selectedTaskId) return null;
  return <ConversionViewInner key={selectedTaskId} selectedTaskId={selectedTaskId} />;
}

function ConversionViewInner({ selectedTaskId }: { selectedTaskId: string }) {
  const [data, setData] = useState<HistorySolutionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [analyzingAll, setAnalyzingAll] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<Record<string, InfringementResult>>({});
  const [analysisFailed, setAnalysisFailed] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;

    const loadData = async () => {
      setLoading(true);
      try {
        const d = await historySolutionsApi.getData(selectedTaskId);
        if (cancelled) return;
        setData(d);
        if (d.solutions.length > 0 && d.solutions.some((s) => s.refPatents.length > 0)) {
          setAnalyzingAll(true);
          const outcomes = await Promise.allSettled(
            d.solutions.map((sol) =>
              historySolutionsApi
                .checkInfringement(sol.id)
                .then((result) => ({ id: sol.id, result }))
                .catch(() => ({ id: sol.id, result: null })),
            ),
          );
          if (cancelled) return;
          const results: Record<string, InfringementResult> = {};
          const failed: string[] = [];
          outcomes.forEach((o) => {
            if (o.status === 'fulfilled' && o.value.result) {
              results[o.value.id] = o.value.result;
            } else {
              failed.push(o.status === 'fulfilled' ? o.value.id : 'unknown');
            }
          });
          setAnalysisResults(results);
          setAnalysisFailed(failed);
          setAnalyzingAll(false);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : '加载失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadData();
    return () => {
      cancelled = true;
    };
  }, [selectedTaskId]);

  if (loading) {
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
          padding: 60,
        }}
      >
        <p style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 10px' }}>
          成果转化
        </p>
        <p style={{ fontSize: 13, color: 'var(--text-tertiary)', margin: '0 0 28px', textAlign: 'center', lineHeight: 1.5, maxWidth: 400 }}>
          正在加载成果转化数据...
        </p>
        <StepRunningIndicator phaseId="conversion" size={100} color="var(--accent-green)" />
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
          minHeight: 0,
          gap: 12,
        }}
      >
        <i
          className="fa-solid fa-circle-exclamation"
          style={{ fontSize: 24, color: 'var(--accent-red)' }}
        />
        <span style={{ fontSize: 13, color: 'var(--accent-red)' }}>{error}</span>
      </div>
    );
  }

  if (!data || data.solutions.length === 0) {
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
          gap: 12,
        }}
      >
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>该任务暂无成果转化数据</span>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%' }}>
      <div className="card-title">
        成果转化 | {data.taskTitle}
      </div>

      <div
        style={{
          padding: '8px 12px',
          borderRadius: 6,
          fontSize: 12,
          background: 'rgba(251,191,36,0.08)',
          border: '1px solid rgba(251,191,36,0.15)',
          color: 'var(--accent-yellow)',
          lineHeight: 1.5,
        }}
      >
        <i className="fa-solid fa-circle-info" style={{ marginRight: 4 }} />
        对每个方案进行「侵权分析」，检查方案是否与参考专利存在技术重叠，并获取规避设计建议，避免专利侵权风险。
      </div>

      {analysisFailed.length > 0 && (
        <div
          style={{
            padding: '8px 12px',
            borderRadius: 6,
            fontSize: 12,
            background: 'rgba(248,113,113,0.08)',
            border: '1px solid rgba(248,113,113,0.15)',
            color: 'var(--accent-red)',
            lineHeight: 1.5,
          }}
        >
          <i className="fa-solid fa-circle-exclamation" style={{ marginRight: 4 }} />
          {analysisFailed.length} 个方案的侵权分析暂时不可用，请确认已配置可用的对话模型后刷新重试
        </div>
      )}

      {!analyzingAll && data.solutions.every((s) => s.refPatents.length === 0) && (
        <div
          style={{
            padding: '8px 12px',
            borderRadius: 6,
            fontSize: 12,
            background: 'rgba(251,191,36,0.08)',
            border: '1px solid rgba(251,191,36,0.15)',
            color: 'var(--accent-yellow)',
            lineHeight: 1.5,
          }}
        >
          <i className="fa-solid fa-circle-info" style={{ marginRight: 4 }} />
          当前方案暂无关联的参考专利数据（分析流程中专利搜索未匹配到相关专利），侵权分析无法进行
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {data.solutions.map((sol) => (
          <SolutionCard
            key={sol.id}
            solution={sol}
            analyzingAll={analyzingAll}
            analysisResult={analysisResults[sol.id] || null}
          />
        ))}
      </div>
    </div>
  );
}
