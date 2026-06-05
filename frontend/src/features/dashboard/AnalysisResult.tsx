import { useState } from 'react';
import { useAnalysisStore } from '../../store/useAnalysisStore';
import { useTaskStore } from '../../store/useTaskStore';

const tabs = ['问题建模', '冲突分析', '技术矛盾', '物理矛盾', '创新方向'];

function ConflictDiagram() {
  const analysis = useAnalysisStore((s) => s.analysis);

  if (!analysis) return null;

  return (
    <div style={{ position: 'relative', width: '100%', height: 240, marginTop: 10 }}>
      <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0 }}>
        {/* Dashed circle */}
        <circle cx="50%" cy="50%" r="80" stroke="rgba(59,130,246,0.2)" strokeWidth="1" fill="none" strokeDasharray="4 4" />
        {/* Connection lines */}
        {analysis.edges.map((edge, i) => {
          const source = analysis.satelliteNodes.find((n) => n.id === edge.sourceId);
          const target = analysis.satelliteNodes.find((n) => n.id === edge.targetId);
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
      {analysis.satelliteNodes.map((node) => {
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

export function AnalysisResult() {
  const [active, setActive] = useState('问题建模');
  const analysis = useAnalysisStore((s) => s.analysis);
  const loading = useAnalysisStore((s) => s.loading);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);

  return (
    <div className="card" style={{ height: '100%', minHeight: 300, display: 'flex', flexDirection: 'column' }}>
      <div className="card-title">
        <i className="fa-solid fa-chart-bar" style={{ fontSize: 12, color: 'var(--accent-blue)' }} />
        问题分析结果
      </div>

      <div style={{ display: 'flex', gap: 20, borderBottom: '1px solid var(--border)', marginBottom: 15 }}>
        {tabs.map((t) => (
          <div key={t} onClick={() => setActive(t)}
            style={{
              paddingBottom: 10, fontSize: 13, cursor: 'pointer', position: 'relative',
              color: active === t ? 'var(--text-primary)' : 'var(--text-secondary)',
              borderBottom: active === t ? '2px solid var(--accent-blue)' : 'none',
            }}>
            {t}
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
        ) : !analysis ? (
          <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
            暂无分析数据
          </div>
        ) : active === '冲突分析' || active === '问题建模' ? (
          <div style={{ display: 'flex', gap: 20 }}>
            {/* Left: Diagram */}
            <div style={{ flex: 1 }}>
              <ConflictDiagram />
            </div>

            {/* Right: Details */}
            <div style={{ width: 200, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{
                background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
                border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 6 }}>
                  问题描述
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  {analysis.centerNode.description || '在提升电池能量密度的过程中，往往伴随发热增加导致安全性下降，同时加速电池老化，缩短循环寿命。'}
                </div>
              </div>

              <div style={{
                background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
                border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-green)', marginBottom: 6 }}>
                  期望目标
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                  <div>• 提高能量密度</div>
                  <div>• 提升安全性</div>
                  <div>• 延长循环寿命</div>
                </div>
              </div>

              <div style={{
                background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
                border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-yellow)', marginBottom: 6 }}>
                  关键约束
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                  <div>• 成本可控</div>
                  <div>• 工艺可行</div>
                  <div>• 材料可获得</div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
            {active} — 功能开发中
          </div>
        )}
      </div>
    </div>
  );
}
