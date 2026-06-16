import { useState, useEffect } from 'react';
import { useTaskStore } from '../../store/useTaskStore';
import { tasksApi } from '../../api/tasks';
import { conversionApi } from '../../api/conversion';
import { InlineConfirmModal } from '../../components/ui/InlineConfirmModal';
import type { Task } from '../../types/task';
import type { ConversionData, SolutionWithEval, InfringementResult } from '../../api/conversion';

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '待处理', color: 'var(--accent-yellow)', bg: 'rgba(251,191,36,0.12)' },
  analyzing: { label: '分析中', color: 'var(--accent-blue)', bg: 'rgba(59,130,246,0.12)' },
  completed: { label: '已完成', color: 'var(--accent-green)', bg: 'rgba(74,222,128,0.12)' },
  failed: { label: '失败', color: 'var(--accent-red)', bg: 'rgba(248,113,113,0.12)' },
};

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '';
  const d = new Date(dateStr.replace(' ', 'T') + 'Z');
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);
  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin}分钟前`;
  if (diffHour < 24) return `${diffHour}小时前`;
  if (diffDay < 7) return `${diffDay}天前`;
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

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
      <span style={{ fontSize: 11, color: 'var(--text-secondary)', width: 56, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'rgba(0,0,0,0.3)', overflow: 'hidden' }}>
        <div style={{ width: `${value}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.3s' }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 600, color, width: 28, textAlign: 'right' }}>{value}</span>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const color = level === '高' ? 'var(--accent-red)' : level === '中' ? 'var(--accent-yellow)' : level === '低' ? 'var(--accent-green)' : 'var(--text-tertiary)';
  const bg = level === '高' ? 'rgba(248,113,113,0.15)' : level === '中' ? 'rgba(251,191,36,0.15)' : level === '低' ? 'rgba(74,222,128,0.15)' : 'rgba(100,116,139,0.1)';
  return (
    <span style={{ padding: '2px 10px', borderRadius: 4, fontSize: 12, fontWeight: 600, background: bg, color }}>
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
    <div style={{
      background: 'rgba(0,0,0,0.25)', borderRadius: 8, padding: 16, marginTop: 12,
      border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <i className="fa-solid fa-shield-halved" style={{ color: 'var(--accent-red)', fontSize: 14 }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>侵权风险分析</span>
      </div>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 20 }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ color: 'var(--accent-blue)' }} />
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>AI 正在分析侵权风险...</span>
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

          <div style={{
            padding: 10, borderRadius: 6,
            background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.15)',
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 4 }}>分析概要与结论</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{result.analysisSummary}</div>
          </div>

          {result.claimOverlaps && result.claimOverlaps.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-red)', marginBottom: 6 }}>技术特征对比</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {result.claimOverlaps.map((item, i) => (
                  <div key={i} style={{
                    padding: 10, borderRadius: 6,
                    background: 'rgba(248,113,113,0.05)', border: '1px solid rgba(248,113,113,0.12)',
                  }}>
                    <div style={{ fontSize: 11, marginBottom: 2 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>方案特征：</span>
                      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{item.feature}</span>
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
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-green)', marginBottom: 6 }}>规避设计建议</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {result.designArounds.map((d, i) => (
                  <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, paddingLeft: 12 }}>
                    <span style={{ color: 'var(--accent-green)', marginRight: 4 }}>-</span>
                    {d}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.keyRecommendations && result.keyRecommendations.length > 0 && (
            <div style={{
              padding: 10, borderRadius: 6,
              background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.15)',
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-green)', marginBottom: 4 }}>关键建议</div>
              {result.keyRecommendations.map((r, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
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
  onAnalyze,
  analyzingId,
  analysisResult,
}: {
  solution: SolutionWithEval;
  onAnalyze: (id: string) => void;
  analyzingId: string | null;
  analysisResult: InfringementResult | null;
}) {
  const [showPatents, setShowPatents] = useState(false);

  return (
    <div style={{
      background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 16,
      border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            {solution.title}
          </div>
          {solution.principles && solution.principles.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {solution.principles.map((p, i) => (
                <span key={i} style={{
                  fontSize: 10, padding: '1px 6px', borderRadius: 3,
                  background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.2)',
                  color: 'var(--accent-yellow)',
                }}>
                  <i className="fa-regular fa-lightbulb" style={{ marginRight: 2, fontSize: 9 }} />
                  {p}
                </span>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={() => onAnalyze(solution.id)}
          disabled={analyzingId === solution.id}
          style={{
            display: 'flex', alignItems: 'center', gap: 4,
            padding: '5px 12px', borderRadius: 5, fontSize: 11,
            background: analyzingId === solution.id ? 'var(--text-tertiary)' : 'rgba(248,113,113,0.15)',
            border: '1px solid rgba(248,113,113,0.3)',
            color: analyzingId === solution.id ? 'var(--text-tertiary)' : 'var(--accent-red)',
            cursor: analyzingId === solution.id ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit', whiteSpace: 'nowrap',
          }}
        >
          {analyzingId === solution.id ? (
            <><i className="fa-solid fa-circle-notch fa-spin" /> 分析中</>
          ) : (
            <><i className="fa-solid fa-shield-halved" /> 侵权分析</>
          )}
        </button>
      </div>

      {solution.description && (
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 10 }}>
          {solution.description}
        </div>
      )}

      {Object.keys(solution.evaluation).length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 6 }}>评估分数</div>
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
              display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
              fontSize: 11, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: showPatents ? 8 : 0,
            }}
          >
            <i className={`fa-solid fa-chevron-${showPatents ? 'down' : 'right'}`} style={{ fontSize: 9 }} />
            参考专利（{solution.patentReferences.length}）
          </div>
          {showPatents && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {solution.refPatents.length > 0 ? solution.refPatents.map((p, i) => (
                <div key={i} style={{
                  padding: 8, borderRadius: 6,
                  background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.12)',
                }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 2 }}>
                    <i className="fa-regular fa-copyright" style={{ marginRight: 4, fontSize: 10, color: 'var(--accent-blue)' }} />
                    {p.title || p._title || '未知专利'}
                  </div>
                  {p.patent_number && (
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 2 }}>
                      专利号：{p.patent_number}
                    </div>
                  )}
                  {(p.abstract || p.description) && (
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {(p.abstract || p.description || '').slice(0, 200)}
                    </div>
                  )}
                </div>
              )) : solution.patentReferences.map((name, i) => (
                <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '4px 0' }}>
                  <i className="fa-regular fa-copyright" style={{ marginRight: 4, fontSize: 9 }} />
                  {name}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {analysisResult && (
        <InfringementPanel result={analysisResult} loading={false} />
      )}
    </div>
  );
}

export function PatentConversionPage() {
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const selectTask = useTaskStore((s) => s.selectTask);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [confirmModal, setConfirmModal] = useState<{ open: boolean; title: string; message: string; onConfirm: () => void }>({ open: false, title: '', message: '', onConfirm: () => {} });
  const [data, setData] = useState<ConversionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResults, setAnalysisResults] = useState<Record<string, InfringementResult>>({});
  const [expandedResult, setExpandedResult] = useState<string | null>(null);

  // 加载任务列表
  useEffect(() => {
    setTasksLoading(true);
    tasksApi.list({ pageSize: 50 })
      .then((res) => setTasks(res.data))
      .catch(() => {})
      .finally(() => setTasksLoading(false));
  }, []);

  // 选中任务时加载转化数据
  useEffect(() => {
    if (!selectedTaskId) {
      setData(null);
      setLoading(false);
      setError('');
      return;
    }
    setLoading(true);
    setError('');
    setAnalysisResults({});
    setExpandedResult(null);
    conversionApi.getData(selectedTaskId)
      .then(setData)
      .catch((err) => setError(err?.message || '加载失败'))
      .finally(() => setLoading(false));
  }, [selectedTaskId]);

  const handleSelectTask = (taskId: string) => {
    selectTask(taskId);
  };

  const handleBackToList = () => {
    selectTask('');
  };

  const handleAnalyze = async (solutionId: string) => {
    if (analysisResults[solutionId]) {
      setExpandedResult(expandedResult === solutionId ? null : solutionId);
      return;
    }
    setAnalyzingId(solutionId);
    try {
      const result = await conversionApi.checkInfringement(solutionId);
      setAnalysisResults((prev) => ({ ...prev, [solutionId]: result }));
      setExpandedResult(solutionId);
    } catch (err) {
      console.error('侵权分析失败:', err);
    } finally {
      setAnalyzingId(null);
    }
  };

  // ====== 默认视图：历史方案库（与首页"我的任务"同款样式） ======
  if (!selectedTaskId) {
    const filtered = tasks.filter((t) => {
      const matchSearch = !search || t.title.toLowerCase().includes(search.toLowerCase());
      const matchFilter = filter === 'all' || t.status === filter;
      return matchSearch && matchFilter;
    });
    const statusCounts = tasks.reduce((acc, t) => {
      acc[t.status] = (acc[t.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, minHeight: 0 }}>
        <div className="card-title">
          <i className="fa-solid fa-file-contract" style={{ marginRight: 8, color: 'var(--accent-red)' }} />
          成果转化 | 历史方案库
          <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400 }}>({tasks.length})</span>
        </div>

        {/* 搜索 */}
        <div style={{ position: 'relative' }}>
          <i className="fa-solid fa-magnifying-glass" style={{
            position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)',
            fontSize: 10, color: 'var(--text-tertiary)',
          }} />
          <input
            value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索任务..."
            style={{
              width: '100%', padding: '6px 8px 6px 24px', borderRadius: 6,
              background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
              color: 'var(--text-primary)', fontSize: 11, outline: 'none', fontFamily: 'inherit',
            }}
          />
        </div>

        {/* 状态筛选 */}
        <div style={{ display: 'flex', gap: 4 }}>
          {[
            { key: 'all', label: '全部', count: tasks.length },
            { key: 'pending', label: '待处理', count: statusCounts.pending || 0 },
            { key: 'analyzing', label: '分析中', count: statusCounts.analyzing || 0 },
            { key: 'completed', label: '已完成', count: statusCounts.completed || 0 },
          ].map((item) => (
            <button key={item.key} onClick={() => setFilter(item.key)} style={{
              padding: '3px 8px', borderRadius: 4, fontSize: 10, cursor: 'pointer',
              background: filter === item.key ? 'rgba(59,130,246,0.15)' : 'transparent',
              border: filter === item.key ? '1px solid rgba(59,130,246,0.3)' : '1px solid transparent',
              color: filter === item.key ? 'var(--accent-blue)' : 'var(--text-tertiary)',
              fontFamily: 'inherit',
            }}>
              {item.label} {item.count > 0 && <span style={{ opacity: 0.6 }}>{item.count}</span>}
            </button>
          ))}
        </div>

        {/* 列表 */}
        {tasksLoading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
            <i className="fa-solid fa-circle-notch fa-spin" style={{ color: 'var(--accent-blue)', fontSize: 20 }} />
          </div>
        ) : tasks.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 12 }}>
            <i className="fa-solid fa-folder-open" style={{ fontSize: 24, color: 'var(--text-tertiary)', opacity: 0.4 }} />
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>暂无历史任务</span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>完成一个分析流程后，方案会自动出现在这里</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 400, overflow: 'auto' }}>
            {filtered.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 16, fontSize: 11, color: 'var(--text-tertiary)' }}>
                无匹配任务
              </div>
            ) : (
              filtered.map((task) => {
                const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
                return (
                  <div
                    key={task.id}
                    onClick={() => handleSelectTask(task.id)}
                    onMouseEnter={() => setHoveredId(task.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px',
                      borderRadius: 6, cursor: 'pointer', fontSize: 12,
                      background: 'transparent',
                      border: '1px solid transparent',
                      transition: 'all 0.1s ease',
                    }}
                  >
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0, marginTop: 5,
                      background: cfg.color,
                    }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        color: 'var(--text-primary)', fontWeight: 500, marginBottom: 2,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {task.title}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{
                          fontSize: 9, padding: '1px 5px', borderRadius: 3,
                          background: cfg.bg, color: cfg.color,
                        }}>
                          {cfg.label}
                        </span>
                        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                          {formatDate(task.createdAt)}
                        </span>
                      </div>
                    </div>
                    {hoveredId === task.id && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmModal({
                            open: true,
                            title: '确认删除',
                            message: `确认删除任务 "${task.title}"？`,
                            onConfirm: () => {
                              setConfirmModal(prev => ({ ...prev, open: false }));
                              tasksApi.remove(task.id).then(() => {
                                setTasks((prev) => prev.filter((t) => t.id !== task.id));
                              }).catch(() => alert('删除失败'));
                            },
                          });
                        }}
                        style={{
                          background: 'rgba(248,113,113,0.1)',
                          border: '1px solid rgba(248,113,113,0.2)',
                          color: 'var(--accent-red)',
                          cursor: 'pointer', fontSize: 10,
                          padding: '2px 6px', borderRadius: 4, fontFamily: 'inherit', flexShrink: 0,
                          transition: 'all 0.15s',
                        }}
                      >
                        <i className="fa-solid fa-trash-can" style={{ fontSize: 9 }} />
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        <InlineConfirmModal
          open={confirmModal.open}
          title={confirmModal.title}
          message={confirmModal.message}
          onConfirm={confirmModal.onConfirm}
          onCancel={() => setConfirmModal(prev => ({ ...prev, open: false }))}
        />
      </div>
    );
  }

  // ====== 任务详情视图 ======
  if (loading) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, minHeight: 300 }}>
        <div style={{ textAlign: 'center' }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 24, color: 'var(--accent-blue)', marginBottom: 12, display: 'block' }} />
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>加载成果转化数据...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, minHeight: 300, gap: 12 }}>
        <i className="fa-solid fa-circle-exclamation" style={{ fontSize: 24, color: 'var(--accent-red)' }} />
        <span style={{ fontSize: 13, color: 'var(--accent-red)' }}>{error}</span>
        <button onClick={handleBackToList} style={{
          padding: '6px 16px', borderRadius: 6, fontSize: 12,
          background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit',
        }}>
          返回列表
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, minHeight: 300, gap: 12 }}>
        <i className="fa-solid fa-folder-open" style={{ fontSize: 32, color: 'var(--text-tertiary)', opacity: 0.3 }} />
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>该任务暂无成果转化数据</span>
        <button onClick={handleBackToList} style={{
          padding: '6px 16px', borderRadius: 6, fontSize: 12,
          background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit',
        }}>
          返回列表
        </button>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, minHeight: 0 }}>
      {/* Header with back button */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="card-title" style={{ margin: 0 }}>
          <i className="fa-solid fa-file-contract" style={{ marginRight: 8, color: 'var(--accent-red)' }} />
          成果转化 | {data.taskTitle}
        </div>
        <button onClick={handleBackToList} style={{
          display: 'flex', alignItems: 'center', gap: 4,
          padding: '5px 12px', borderRadius: 5, fontSize: 11,
          background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
          color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
        }}>
          <i className="fa-solid fa-arrow-left" /> 返回列表
        </button>
      </div>

      {/* Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        <div style={{ textAlign: 'center', padding: '10px', borderRadius: 6, background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)' }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-blue)', marginBottom: 2 }}>{data.solutions.length}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>生成方案</div>
        </div>
        <div style={{ textAlign: 'center', padding: '10px', borderRadius: 6, background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.15)' }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-green)', marginBottom: 2 }}>
            {data.solutions.length > 0
              ? Math.round(data.solutions.reduce((sum, s) => sum + (s.evaluation?.conversion || 0), 0) / data.solutions.length)
              : 0}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>平均转化潜力</div>
        </div>
        <div style={{ textAlign: 'center', padding: '10px', borderRadius: 6, background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.15)' }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent-red)', marginBottom: 2 }}>
            {data.solutions.reduce((sum, s) => sum + s.patentReferences.length, 0)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>关联专利</div>
        </div>
      </div>

      {/* Guide text */}
      <div style={{
        padding: '8px 12px', borderRadius: 6, fontSize: 12,
        background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.15)',
        color: 'var(--accent-yellow)', lineHeight: 1.5,
      }}>
        <i className="fa-solid fa-circle-info" style={{ marginRight: 4 }} />
        对每个方案进行「侵权分析」，检查方案是否与参考专利存在技术重叠，并获取规避设计建议，避免专利侵权风险。
      </div>

      {/* Solutions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {data.solutions.map((sol) => (
          <SolutionCard
            key={sol.id}
            solution={sol}
            onAnalyze={handleAnalyze}
            analyzingId={analyzingId}
            analysisResult={expandedResult === sol.id ? (analysisResults[sol.id] || null) : null}
          />
        ))}
      </div>
    </div>
  );
}
