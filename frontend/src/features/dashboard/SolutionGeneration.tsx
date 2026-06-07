import { useState } from 'react';
import { useSolutionStore } from '../../store/useSolutionStore';
import { useTaskStore } from '../../store/useTaskStore';
import type { Evaluation } from '../../types/evaluation';

function StarRating({ rating, max = 5 }: { rating: number; max?: number }) {
  return (
    <div style={{ display: 'flex', gap: 2 }}>
      {Array.from({ length: max }, (_, i) => (
        <span key={i} style={{
          fontSize: 14, color: i < rating ? '#fbbf24' : 'rgba(255,255,255,0.15)',
        }}>
          {i < rating ? '★' : '☆'}
        </span>
      ))}
    </div>
  );
}

function _confDisplay(conf: number | null): { text: string; color: string } {
  if (conf === null) return { text: '未评估', color: 'var(--text-tertiary)' };
  if (conf >= 0.7) return { text: `${(conf * 100).toFixed(0)}%`, color: '#4CAF50' };
  if (conf >= 0.4) return { text: `${(conf * 100).toFixed(0)}%`, color: '#FF9800' };
  return { text: `${(conf * 100).toFixed(0)}%`, color: '#D32F2F' };
}

function _verdictColor(verdict: string): string {
  return verdict === 'passed' ? '#5B8C5A' : '#D32F2F';
}

function _ifrColor(distance: string): string {
  return { close: '#4CAF50', medium: '#FF9800', far: '#D32F2F' }[distance] || 'var(--text-tertiary)';
}

const _IFR_DISTANCE_LABEL: Record<string, string> = { close: '较近', medium: '一般', far: '较远' };

// 评估详情弹窗
function EvaluationDetailModal({ evaluation, onClose }: { evaluation: Evaluation; onClose: () => void }) {
  const confDisplay = _confDisplay(evaluation.confidence);
  const verdictColor = _verdictColor(evaluation.overallVerdict);
  const ifrColor = _ifrColor(evaluation.ifrDistance);

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', zIndex: 100,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
        width: '90%', maxWidth: 600, maxHeight: '80vh', overflow: 'auto',
        padding: 20,
      }} onClick={(e) => e.stopPropagation()}>
        {/* 头部 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
            方案评估详情
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--text-tertiary)',
            cursor: 'pointer', fontSize: 18,
          }}>
            <i className="fa-solid fa-xmark" />
          </button>
        </div>

        {/* 状态概览 */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 16,
        }}>
          <div style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
            border: '1px solid var(--border-light)', textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>整体裁决</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: verdictColor }}>
              {evaluation.overallVerdict === 'passed' ? '✓ 通过' : '✗ 未通过'}
            </div>
          </div>
          <div style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
            border: '1px solid var(--border-light)', textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>成熟度</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
              {evaluation.maturity || '概念阶段'}
            </div>
          </div>
          <div style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
            border: '1px solid var(--border-light)', textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>置信度</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: confDisplay.color }}>
              {confDisplay.text}
            </div>
          </div>
        </div>

        {/* 评估维度 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* 逻辑检验 */}
          <div style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
              <i className="fa-solid fa-link" style={{ marginRight: 6, color: 'var(--accent-blue)' }} />
              逻辑检验
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: evaluation.rootCauseCut ? '#4CAF50' : '#D32F2F',
                }} />
                因果链切断：{evaluation.rootCauseCut ? '是' : '否'}
              </div>
            </div>
          </div>

          {/* 矛盾检验 */}
          <div style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
              <i className="fa-solid fa-scale-balanced" style={{ marginRight: 6, color: 'var(--accent-yellow)' }} />
              矛盾检验
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: evaluation.originalContradictionResolved ? '#4CAF50' : '#D32F2F',
                }} />
                原矛盾消除：{evaluation.originalContradictionResolved ? '是' : '否'}
              </div>
              {evaluation.newContradictions && evaluation.newContradictions.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ color: 'var(--accent-red)', marginBottom: 2 }}>新引入矛盾：</div>
                  {evaluation.newContradictions.map((c, i) => (
                    <div key={i} style={{ paddingLeft: 16 }}>• {c}</div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 功能检验 */}
          <div style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
              <i className="fa-solid fa-gears" style={{ marginRight: 6, color: 'var(--accent-cyan)' }} />
              功能检验
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {evaluation.functionDeficitsFilled && evaluation.functionDeficitsFilled.length > 0 ? (
                <div style={{ marginBottom: 4 }}>
                  <div style={{ color: 'var(--accent-green)', marginBottom: 2 }}>补足功能缺失：</div>
                  {evaluation.functionDeficitsFilled.map((f, i) => (
                    <div key={i} style={{ paddingLeft: 16 }}>• {f}</div>
                  ))}
                </div>
              ) : (
                <div style={{ color: 'var(--text-tertiary)' }}>无补足功能缺失</div>
              )}
              {evaluation.newHarmfulInteractions && evaluation.newHarmfulInteractions.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ color: 'var(--accent-red)', marginBottom: 2 }}>新有害作用：</div>
                  {evaluation.newHarmfulInteractions.map((h, i) => (
                    <div key={i} style={{ paddingLeft: 16 }}>• {h}</div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* IFR距离 */}
          <div style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
              <i className="fa-solid fa-bullseye" style={{ marginRight: 6, color: 'var(--accent-purple)' }} />
              IFR距离（理想最终解）
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{
                  padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                  background: `${ifrColor}20`, color: ifrColor,
                  border: `1px solid ${ifrColor}40`,
                }}>
                  {_IFR_DISTANCE_LABEL[evaluation.ifrDistance] || evaluation.ifrDistance}
                </span>
              </div>
              {evaluation.ifrGapDescription && (
                <div style={{ marginTop: 4 }}>{evaluation.ifrGapDescription}</div>
              )}
              {evaluation.ifrParametersAchieved && evaluation.ifrParametersAchieved.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ color: 'var(--text-tertiary)', marginBottom: 2 }}>关键参数达成：</div>
                  {evaluation.ifrParametersAchieved.map((p, i) => (
                    <div key={i} style={{ paddingLeft: 16 }}>• {p}</div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 进化趋势 */}
          <div style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
              <i className="fa-solid fa-arrow-trend-up" style={{ marginRight: 6, color: 'var(--accent-green)' }} />
              进化趋势对齐
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>对齐度：</span>
                <div style={{
                  width: 100, height: 6, borderRadius: 3,
                  background: 'rgba(0,0,0,0.3)', overflow: 'hidden',
                }}>
                  <div style={{
                    width: `${(evaluation.evolutionAlignment || 0) * 100}%`, height: '100%',
                    background: evaluation.evolutionAlignment >= 0.7 ? '#4CAF50' : evaluation.evolutionAlignment >= 0.4 ? '#FF9800' : '#D32F2F',
                    borderRadius: 3,
                  }} />
                </div>
                <span style={{
                  fontSize: 11, fontWeight: 600,
                  color: evaluation.evolutionAlignment >= 0.7 ? '#4CAF50' : evaluation.evolutionAlignment >= 0.4 ? '#FF9800' : '#D32F2F',
                }}>
                  {((evaluation.evolutionAlignment || 0) * 100).toFixed(0)}%
                </span>
              </div>
              {evaluation.alignedLaws && evaluation.alignedLaws.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ color: 'var(--accent-green)', marginBottom: 2 }}>已对齐法则：</div>
                  {evaluation.alignedLaws.map((l, i) => (
                    <div key={i} style={{ paddingLeft: 16 }}>• {l}</div>
                  ))}
                </div>
              )}
              {evaluation.misalignedLaws && evaluation.misalignedLaws.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ color: 'var(--accent-red)', marginBottom: 2 }}>未对齐法则：</div>
                  {evaluation.misalignedLaws.map((l, i) => (
                    <div key={i} style={{ paddingLeft: 16 }}>• {l}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// 评估卡片
function EvaluationCard({ evaluation }: { evaluation: Evaluation }) {
  const confDisplay = _confDisplay(evaluation.confidence);
  const verdictColor = _verdictColor(evaluation.overallVerdict);
  const [showDetail, setShowDetail] = useState(false);

  return (
    <>
      <div style={{
        background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
        border: '1px solid var(--border-light)', marginBottom: 8,
        cursor: 'pointer',
      }} onClick={() => setShowDetail(true)}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontSize: 14, fontWeight: 600,
              color: verdictColor,
            }}>
              {evaluation.overallVerdict === 'passed' ? '✓ 通过' : '✗ 未通过'}
            </span>
            <span style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 4,
              background: `${confDisplay.color}20`, color: confDisplay.color,
              border: `1px solid ${confDisplay.color}40`,
            }}>
              {confDisplay.text}
            </span>
          </div>
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
            {evaluation.maturity || '概念阶段'}
          </span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: evaluation.rootCauseCut ? '#4CAF50' : '#D32F2F',
            }} />
            因果链：{evaluation.rootCauseCut ? '已切断' : '未切断'}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: evaluation.originalContradictionResolved ? '#4CAF50' : '#D32F2F',
            }} />
            矛盾：{evaluation.originalContradictionResolved ? '已消除' : '未消除'}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: evaluation.ifrDistance === 'close' ? '#4CAF50' : evaluation.ifrDistance === 'medium' ? '#FF9800' : '#D32F2F',
            }} />
            IFR距离：{_IFR_DISTANCE_LABEL[evaluation.ifrDistance] || evaluation.ifrDistance}
          </div>
        </div>
      </div>
      {showDetail && <EvaluationDetailModal evaluation={evaluation} onClose={() => setShowDetail(false)} />}
    </>
  );
}

export function SolutionGeneration() {
  const solutions = useSolutionStore((s) => s.solutions);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const loading = useSolutionStore((s) => s.loading);

  const emptyPanel = (msg: string) => (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', width: '100%', minHeight: 200 }}>
      <div className="card-title">
        创新方案生成与评估
      </div>
      <div style={{ padding: '30px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>{msg}</div>
    </div>
  );

  if (!selectedTaskId) return emptyPanel('选择一个任务查看创新方案');
  if (loading && solutions.length === 0) return emptyPanel('加载中...');
  if (solutions.length === 0) return emptyPanel('暂无方案数据');

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', width: '100%', minHeight: 300 }}>
      <div className="card-title">
        创新方案生成与评估
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {/* 推荐创新方向 */}
        <div style={{
          background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, marginBottom: 12,
          border: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
            推荐创新方向
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {solutions.slice(0, 3).map((sol, i) => (
              <div key={sol.id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 10px', borderRadius: 6,
                background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)',
              }}>
                <div>
                  <span style={{ fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600 }}>
                    方向{i + 1}：
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{sol.title}</span>
                </div>
                <StarRating rating={Math.round(sol.confidenceScore / 20)} />
              </div>
            ))}
          </div>
        </div>

        {/* 方案评估结果 */}
        <div style={{
          background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, marginBottom: 12,
          border: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
            <i className="fa-solid fa-clipboard-check" style={{ marginRight: 6, color: 'var(--accent-green)' }} />
            方案评估结果
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.5 }}>
            点击卡片查看详细评估结果
          </div>
          {/* 示例评估卡片 - 实际应从API获取 */}
          <EvaluationCard evaluation={{
            id: '1',
            solutionId: '1',
            dimension: 'comprehensive',
            score: 85,
            details: {},
            status: 'completed',
            createdAt: new Date().toISOString(),
            rootCauseCut: true,
            originalContradictionResolved: true,
            newContradictions: [],
            functionDeficitsFilled: ['功能A', '功能B'],
            newHarmfulInteractions: [],
            ifrDistance: 'close',
            ifrGapDescription: '已接近理想最终解',
            ifrParametersAchieved: ['参数1', '参数2'],
            overallVerdict: 'passed',
            evolutionAlignment: 0.85,
            alignedLaws: ['动态化法则', '子系统不均衡进化法则'],
            misalignedLaws: [],
            maturity: '可直接实施',
            confidence: 0.85,
          }} />
        </div>

        {/* 方案概述 */}
        <div style={{
          background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
          border: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <i className="fa-regular fa-lightbulb" style={{ color: 'var(--accent-yellow)' }} />
              方案概述
            </div>
            <i className="fa-solid fa-chevron-right" style={{ fontSize: 10, color: 'var(--text-tertiary)', cursor: 'pointer' }} />
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {solutions[0]?.description ? (
              <>
                {solutions[0].description.slice(0, 120)}
                {solutions[0].description.length > 120 ? '...' : ''}
              </>
            ) : (
              <span style={{ color: 'var(--text-tertiary)' }}>暂无方案概述</span>
            )}
          </div>
        </div>

        {/* View full solution button */}
        <button style={{
          width: '100%', marginTop: 12, padding: '10px 0',
          background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
          borderRadius: 8, color: 'var(--accent-blue)', fontSize: 13, fontWeight: 500,
          cursor: 'pointer', fontFamily: 'inherit',
        }}>
          查看完整方案 <i className="fa-solid fa-arrow-right" style={{ fontSize: 11, marginLeft: 4 }} />
        </button>
      </div>
    </div>
  );
}
