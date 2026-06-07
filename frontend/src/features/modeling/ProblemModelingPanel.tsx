import { useState } from 'react';
import type { ProblemModeling } from '../../types/modeling';
import type { WorkflowState } from '../../types/workflow';

interface ProblemModelingPanelProps {
  modeling: ProblemModeling | null;
  loading: boolean;
  workflow: WorkflowState | null;
}

export function ProblemModelingPanel({ modeling, loading, workflow }: ProblemModelingPanelProps) {
  const [activeTab, setActiveTab] = useState('elements');

  // 获取每个步骤的状态
  const getStepStatus = (agentId: string) => {
    const step = workflow?.steps?.find((s) => s.agentId === agentId);
    return step?.status || 'pending';
  };

  // 步骤与标签映射
  const tabConfig = [
    { key: 'elements', label: '问题要素', icon: 'fa-list-check', agentId: 'agent1' },
    { key: 'conflicts', label: '冲突分析', icon: 'fa-bolt', agentId: 'agent2' },
    { key: 'principles', label: '推荐原理', icon: 'fa-lightbulb', agentId: 'agent5' },
    { key: 'directions', label: '创新方向', icon: 'fa-compass', agentId: 'agent3' },
    { key: 'structure', label: '模型结构', icon: 'fa-sitemap', agentId: 'agent4' },
  ];

  if (loading) {
    return (
      <div className="card" style={{ minHeight: 300 }}>
        <div className="card-title">问题建模</div>
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 24, color: 'var(--accent-blue)' }} />
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 8 }}>加载问题建模...</div>
        </div>
      </div>
    );
  }

  if (!modeling) {
    return (
      <div className="card" style={{ minHeight: 300 }}>
        <div className="card-title">问题建模</div>
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
          <i className="fa-solid fa-cube" style={{ fontSize: 32, marginBottom: 12, display: 'block', opacity: 0.3 }} />
          暂无问题建模数据，请先进行分析
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ minHeight: 300 }}>
      <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <i className="fa-solid fa-cube" style={{ marginRight: 8, color: 'var(--accent-purple)' }} />
          问题建模
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
          {modeling.modelStructure?.problemType || '未知'} · {modeling.modelStructure?.complexity || '未知'}
        </span>
      </div>

      {/* Tabs with step status */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--border-light)', paddingBottom: 8 }}>
        {tabConfig.map((tab) => {
          const status = getStepStatus(tab.agentId);
          const isActive = activeTab === tab.key;
          const isCompleted = status === 'completed';
          const isRunning = status === 'running';
          
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                padding: '6px 12px', borderRadius: 6, fontSize: 12,
                background: isActive ? 'rgba(59,130,246,0.15)' : 'transparent',
                border: isActive ? '1px solid rgba(59,130,246,0.3)' : '1px solid transparent',
                color: isActive ? 'var(--accent-blue)' : isCompleted ? 'var(--text-primary)' : 'var(--text-tertiary)',
                cursor: 'pointer', fontFamily: 'inherit',
                display: 'flex', alignItems: 'center', gap: 4,
                position: 'relative',
              }}
            >
              <i className={`fa-solid ${tab.icon}`} style={{ fontSize: 10 }} />
              {tab.label}
              {/* Step status indicator */}
              {isRunning && (
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: 'var(--accent-blue)', display: 'inline-block',
                  animation: 'pulse 1.5s infinite',
                }} />
              )}
              {isCompleted && (
                <i className="fa-solid fa-check" style={{ fontSize: 8, color: 'var(--accent-green)' }} />
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div style={{ minHeight: 200 }}>
        {activeTab === 'elements' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>核心目标</div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                {modeling.problemElements?.coreGoal || '暂无数据'}
              </div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>技术对象</div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                {modeling.problemElements?.techObject || '暂无数据'}
              </div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>约束条件</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {modeling.problemElements?.constraints?.map((c: string, i: number) => (
                  <span key={i} style={{
                    padding: '3px 10px', borderRadius: 4, fontSize: 11,
                    background: 'rgba(251,191,36,0.15)', color: 'var(--accent-yellow)',
                    border: '1px solid rgba(251,191,36,0.3)',
                  }}>
                    {c}
                  </span>
                )) || <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>暂无数据</span>}
              </div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>潜在冲突</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {modeling.problemElements?.potentialConflicts?.map((conflict: any) => (
                  <div key={conflict.id} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '6px 10px', borderRadius: 4,
                    background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.2)',
                  }}>
                    <span style={{ fontSize: 11, color: 'var(--accent-red)' }}>
                      <i className="fa-solid fa-triangle-exclamation" style={{ marginRight: 4 }} />
                      {conflict.label}
                    </span>
                    {conflict.description && (
                      <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                        {conflict.description}
                      </span>
                    )}
                  </div>
                )) || <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>暂无数据</span>}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'conflicts' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {modeling.conflicts?.length > 0 ? modeling.conflicts.map((conflict: any, index: number) => (
              <div key={index} style={{
                background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 14,
                border: '1px solid var(--border-light)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                    <i className="fa-solid fa-bolt" style={{ marginRight: 6, color: 'var(--accent-yellow)' }} />
                    {conflict.type}
                  </div>
                  <span style={{
                    fontSize: 10, padding: '2px 8px', borderRadius: 4,
                    background: conflict.severity === '高' ? 'rgba(248,113,113,0.15)' : 'rgba(251,191,36,0.15)',
                    color: conflict.severity === '高' ? 'var(--accent-red)' : 'var(--accent-yellow)',
                    border: `1px solid ${conflict.severity === '高' ? 'rgba(248,113,113,0.3)' : 'rgba(251,191,36,0.3)'}`,
                  }}>
                    {conflict.severity}优先级
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 10, lineHeight: 1.5 }}>
                  {conflict.description}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {conflict.parameters?.map((param: any, i: number) => (
                    <div key={i} style={{
                      padding: '4px 10px', borderRadius: 4,
                      background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                    }}>
                      <span style={{ fontSize: 11, color: 'var(--accent-blue)' }}>
                        {param.name}
                        {param.direction && <span style={{ marginLeft: 4, opacity: 0.7 }}>{param.direction}</span>}
                        {param.requirement && <span style={{ marginLeft: 4, opacity: 0.7 }}>{param.requirement}</span>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )) : (
              <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
                暂无冲突分析数据
              </div>
            )}
          </div>
        )}

        {activeTab === 'principles' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {modeling.recommendedPrinciples?.length > 0 ? modeling.recommendedPrinciples.map((principle: string, index: number) => (
              <div key={index} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 14px', borderRadius: 8,
                background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
              }}>
                <span style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 600, color: 'var(--accent-blue)', flexShrink: 0,
                }}>
                  {index + 1}
                </span>
                <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                  {principle}
                </div>
                <span style={{
                  marginLeft: 'auto', fontSize: 10, padding: '2px 8px', borderRadius: 4,
                  background: 'rgba(74,222,128,0.1)', color: 'var(--accent-green)',
                  border: '1px solid rgba(74,222,128,0.2)',
                }}>
                  推荐
                </span>
              </div>
            )) : (
              <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
                暂无推荐原理数据
              </div>
            )}
          </div>
        )}

        {activeTab === 'directions' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {modeling.innovationDirections?.length > 0 ? modeling.innovationDirections.map((dir: any, index: number) => (
              <div key={index} style={{
                background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 14,
                border: '1px solid var(--border-light)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                    <i className="fa-solid fa-compass" style={{ marginRight: 6, color: 'var(--accent-cyan)' }} />
                    {dir.direction}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{
                      width: 60, height: 6, borderRadius: 3, background: 'rgba(0,0,0,0.3)', overflow: 'hidden',
                    }}>
                      <div style={{
                        width: `${dir.confidence}%`, height: '100%',
                        background: 'var(--accent-green)', borderRadius: 3,
                      }} />
                    </div>
                    <span style={{ fontSize: 10, color: 'var(--accent-green)', fontWeight: 600 }}>
                      {dir.confidence}%
                    </span>
                  </div>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {dir.description}
                </div>
              </div>
            )) : (
              <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
                暂无创新方向数据
              </div>
            )}
          </div>
        )}

        {activeTab === 'structure' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>问题类型</div>
                <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                  {modeling.modelStructure?.problemType || '暂无数据'}
                </div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>复杂度</div>
                <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                  {modeling.modelStructure?.complexity || '暂无数据'}
                </div>
              </div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>关键因素</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {modeling.modelStructure?.keyFactors?.map((factor: string, i: number) => (
                  <span key={i} style={{
                    padding: '4px 10px', borderRadius: 4, fontSize: 11,
                    background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)',
                    border: '1px solid rgba(59,130,246,0.2)',
                  }}>
                    {factor}
                  </span>
                )) || <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>暂无数据</span>}
              </div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>根本原因</div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                {modeling.modelStructure?.rootCause || '暂无数据'}
              </div>
            </div>

            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>解决方案空间</div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                {modeling.modelStructure?.solutionSpace || '暂无数据'}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
