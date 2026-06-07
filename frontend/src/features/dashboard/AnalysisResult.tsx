import { useState } from 'react';
import { useAnalysisStore } from '../../store/useAnalysisStore';
import { useTaskStore } from '../../store/useTaskStore';
import type { ProblemModeling } from '../../types/modeling';

const tabs = [
  { key: '问题建模', label: '问题建模', agentId: 'agent1' },
  { key: '冲突分析', label: '冲突分析', agentId: 'agent2' },
  { key: '技术矛盾', label: '技术矛盾', agentId: 'agent2' },
  { key: '物理矛盾', label: '物理矛盾', agentId: 'agent2' },
  { key: '创新方向', label: '创新方向', agentId: 'agent3' },
];

interface AnalysisResultProps {
  modeling: ProblemModeling | null;
}

function ConflictDiagram({ modeling }: { modeling: ProblemModeling | null }) {
  const analysis = useAnalysisStore((s) => s.analysis);

  if (!analysis && !modeling) return null;

  // 使用analysis数据或modeling数据
  const satelliteNodes = analysis?.satelliteNodes || [];
  const edges = analysis?.edges || [];

  return (
    <div style={{ position: 'relative', width: '100%', height: 240, marginTop: 10 }}>
      <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0 }}>
        {/* Dashed circle */}
        <circle cx="50%" cy="50%" r="80" stroke="rgba(59,130,246,0.2)" strokeWidth="1" fill="none" strokeDasharray="4 4" />
        {/* Connection lines */}
        {edges.map((edge, i) => {
          const source = satelliteNodes.find((n: any) => n.id === edge.sourceId);
          const target = satelliteNodes.find((n: any) => n.id === edge.targetId);
          if (!source || !target) return null;
          const positions: Record<string, { x: number; y: number }> = {
            top: { x: 160, y: 15 },
            right: { x: 300, y: 110 },
            bottom: { x: 160, y: 210 },
            left: { x: 20, y: 110 },
          };
          const sp = positions[source.position || 'right'];
          const tp = positions[target.position || 'right'];
          return (
            <line key={i} x1={sp.x} y1={sp.y} x2={tp.x} y2={tp.y}
              stroke="rgba(59,130,246,0.15)" strokeWidth={1} strokeDasharray="4 2" />
          );
        })}
      </svg>

      {/* Center node */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
        width: 80, height: 80, borderRadius: '50%',
        background: 'rgba(59,130,246,0.15)', border: '2px solid rgba(59,130,246,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 600, color: 'var(--accent-blue)', textAlign: 'center',
        zIndex: 10,
      }}>
        核心<br />冲突
      </div>

      {/* Satellite nodes */}
      {satelliteNodes.map((node: any) => {
        const positions: Record<string, { top: string; left: string }> = {
          top: { top: '0px', left: '120px' },
          right: { top: '85px', left: '240px' },
          bottom: { top: '185px', left: '120px' },
          left: { top: '85px', left: '0px' },
        };
        const pos = positions[node.position || 'right'];
        return (
          <div key={node.id} style={{
            position: 'absolute', top: pos.top, left: pos.left,
            padding: '8px 12px', borderRadius: 8, fontSize: 11,
            background: node.color ? `${node.color}15` : 'rgba(59,130,246,0.1)',
            border: node.color ? `1px solid ${node.color}30` : '1px solid var(--border)',
            color: node.color || 'var(--text-secondary)',
            textAlign: 'center', minWidth: 80,
          }}>
            <div style={{ fontWeight: 600 }}>{node.label}</div>
            {node.sublabel && <div style={{ fontSize: 9, opacity: 0.7, marginTop: 2 }}>{node.sublabel}</div>}
          </div>
        );
      })}
    </div>
  );
}

function ProblemModelingView({ modeling }: { modeling: ProblemModeling | null }) {
  const analysis = useAnalysisStore((s) => s.analysis);

  if (!modeling && !analysis) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
        暂无问题建模数据
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 20 }}>
      <div style={{ flex: 1 }}>
        <ConflictDiagram modeling={modeling} />
      </div>
      <div style={{ width: 200, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 6 }}>
            问题描述
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {modeling?.problemElements?.coreGoal || analysis?.centerNode?.description || '暂无数据'}
          </div>
        </div>
        <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-green)', marginBottom: 6 }}>
            冲突节点
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            {modeling?.problemElements?.potentialConflicts && modeling?.problemElements?.potentialConflicts.length > 0 ? (
              modeling.problemElements.potentialConflicts.map((c: any) => (
                <div key={c.id}>• {c.label}</div>
              ))
            ) : analysis?.satelliteNodes && analysis?.satelliteNodes.length > 0 ? (
              analysis.satelliteNodes.map((node: any) => (
                <div key={node.id}>• {node.label} {node.sublabel || ''}</div>
              ))
            ) : (
              <div style={{ color: 'var(--text-tertiary)' }}>暂无数据</div>
            )}
          </div>
        </div>
        <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-yellow)', marginBottom: 6 }}>
            推荐原理
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            {modeling?.recommendedPrinciples && modeling?.recommendedPrinciples.length > 0 ? (
              modeling.recommendedPrinciples.map((p: string, i: number) => (
                <div key={i}>• {p}</div>
              ))
            ) : analysis?.principles && analysis?.principles.length > 0 ? (
              analysis.principles.map((p: string, i: number) => (
                <div key={i}>• {p}</div>
              ))
            ) : (
              <div style={{ color: 'var(--text-tertiary)' }}>暂无推荐原理</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ConflictsView({ conflicts, filter }: { conflicts: any[] | undefined, filter?: string }) {
  if (!conflicts || conflicts.length === 0) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
        暂无冲突分析数据
      </div>
    );
  }

  const filtered = filter ? conflicts.filter((c: any) => c.type === filter) : conflicts;

  if (filtered.length === 0) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
        暂无{filter}数据
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {filtered.map((conflict: any, index: number) => (
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
      ))}
    </div>
  );
}

function InnovationDirectionsView({ directions }: { directions: any[] | undefined }) {
  if (!directions || directions.length === 0) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
        暂无创新方向数据
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {directions.map((dir: any, index: number) => (
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
      ))}
    </div>
  );
}

export function AnalysisResult({ modeling }: AnalysisResultProps) {
  const [active, setActive] = useState('问题建模');
  const loading = useAnalysisStore((s) => s.loading);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);

  return (
    <div className="card" style={{ height: '100%', minHeight: 300, display: 'flex', flexDirection: 'column' }}>
      <div className="card-title">
        问题分析结果
      </div>

      <div style={{ display: 'flex', gap: 20, borderBottom: '1px solid var(--border)', marginBottom: 15 }}>
        {tabs.map((t) => (
          <div key={t.key} onClick={() => setActive(t.key)}
            style={{
              paddingBottom: 10, fontSize: 13, cursor: 'pointer', position: 'relative',
              color: active === t.key ? 'var(--text-primary)' : 'var(--text-secondary)',
              borderBottom: active === t.key ? '2px solid var(--accent-blue)' : 'none',
            }}>
            {t.label}
          </div>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {!selectedTaskId ? (
          <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
            选择任务查看分析结果
          </div>
        ) : loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
            加载中...
          </div>
        ) : active === '问题建模' ? (
          <ProblemModelingView modeling={modeling} />
        ) : active === '冲突分析' ? (
          <ConflictsView conflicts={modeling?.conflicts} />
        ) : active === '技术矛盾' ? (
          <ConflictsView conflicts={modeling?.conflicts} filter="技术矛盾" />
        ) : active === '物理矛盾' ? (
          <ConflictsView conflicts={modeling?.conflicts} filter="物理矛盾" />
        ) : active === '创新方向' ? (
          <InnovationDirectionsView directions={modeling?.innovationDirections} />
        ) : null}
      </div>
    </div>
  );
}
