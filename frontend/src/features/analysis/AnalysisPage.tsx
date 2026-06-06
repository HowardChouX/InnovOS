import { useState, useEffect } from 'react';
import { useTaskStore } from '../../store/useTaskStore';
import { useAnalysisStore } from '../../store/useAnalysisStore';
import { GlassPanel } from '../../components/ui/GlassPanel';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';

const tabs = ['问题建模', '冲突分析', '技术矛盾', '物理矛盾', '创新方向'];

function ConflictDiagram() {
  const analysis = useAnalysisStore((s) => s.analysis);

  if (!analysis) return null;

  return (
    <div style={{ position: 'relative', width: '100%', height: 240, marginTop: 10 }}>
      <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0 }}>
        <circle cx="50%" cy="50%" r="80" stroke="rgba(59,130,246,0.2)" strokeWidth="1" fill="none" strokeDasharray="4 4" />
        {analysis.edges.map((edge, i) => {
          const source = analysis.satelliteNodes.find((n) => n.id === edge.sourceId);
          if (!source) return null;
          const positions: Record<string, { x: number; y: number }> = {
            top: { x: 160, y: 15 },
            right: { x: 300, y: 110 },
            bottom: { x: 160, y: 210 },
            left: { x: 20, y: 110 },
          };
          const sp = positions[source.position || 'right'];
          return (
            <line key={i} x1={sp.x} y1={sp.y} x2="160" y2="120"
              stroke="rgba(59,130,246,0.15)" strokeWidth={1} strokeDasharray="4 2" />
          );
        })}
      </svg>
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

export function AnalysisPage() {
  const tasks = useTaskStore((s) => s.tasks);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const selectTask = useTaskStore((s) => s.selectTask);
  const analysis = useAnalysisStore((s) => s.analysis);
  const loading = useAnalysisStore((s) => s.loading);
  const analyzing = useAnalysisStore((s) => s.analyzing);
  const fetchAnalysis = useAnalysisStore((s) => s.fetchAnalysis);
  const triggerAnalysis = useAnalysisStore((s) => s.triggerAnalysis);
  const [activeTab, setActiveTab] = useState('问题建模');

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    if (selectedTaskId) {
      fetchAnalysis(selectedTaskId);
    }
  }, [selectedTaskId, fetchAnalysis]);

  const handleStartAnalysis = async () => {
    if (!selectedTaskId) return;
    await triggerAnalysis(selectedTaskId);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <GlassPanel style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <div className="card-title">
          <i className="fa-solid fa-chart-bar" style={{ color: 'var(--accent-blue)' }} />
          问题分析
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
          <select
            value={selectedTaskId || ''}
            onChange={(e) => selectTask(e.target.value)}
            style={{
              flex: 1, padding: '8px 12px', borderRadius: 6,
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: 13, fontFamily: 'inherit',
            }}
          >
            <option value="">选择任务...</option>
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>{task.title}</option>
            ))}
          </select>
          <button
            onClick={handleStartAnalysis}
            disabled={!selectedTaskId || analyzing}
            className="btn-primary"
            style={{ opacity: (!selectedTaskId || analyzing) ? 0.5 : 1 }}
          >
            {analyzing ? '分析中...' : '开始分析'}
          </button>
        </div>

        {selectedTaskId && (
          <>
            <div style={{ display: 'flex', gap: 20, borderBottom: '1px solid var(--border)', marginBottom: 15 }}>
              {tabs.map((t) => (
                <div key={t} onClick={() => setActiveTab(t)}
                  style={{
                    paddingBottom: 10, fontSize: 13, cursor: 'pointer', position: 'relative',
                    color: activeTab === t ? 'var(--text-primary)' : 'var(--text-secondary)',
                    borderBottom: activeTab === t ? '2px solid var(--accent-blue)' : 'none',
                  }}>
                  {t}
                </div>
              ))}
            </div>

            {loading ? (
              <div style={{ padding: 40, textAlign: 'center' }}>
                <LoadingSpinner />
              </div>
            ) : !analysis ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
                点击"开始分析"按钮触发AI分析
              </div>
            ) : activeTab === '冲突分析' || activeTab === '问题建模' ? (
              <div style={{ display: 'flex', gap: 20 }}>
                <div style={{ flex: 1 }}>
                  <ConflictDiagram />
                </div>
                <div style={{ width: 240, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{
                    background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
                    border: '1px solid var(--border)',
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 6 }}>
                      问题描述
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      {analysis.centerNode.description || '暂无描述'}
                    </div>
                  </div>

                  <div style={{
                    background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
                    border: '1px solid var(--border)',
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-green)', marginBottom: 6 }}>
                      冲突节点
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                      {analysis.satelliteNodes.map((node) => (
                        <div key={node.id}>• {node.label} {node.sublabel || ''}</div>
                      ))}
                    </div>
                  </div>

                  <div style={{
                    background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
                    border: '1px solid var(--border)',
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-yellow)', marginBottom: 6 }}>
                      推荐创新原理
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {analysis.principles.length === 0 ? (
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>暂无</span>
                      ) : (
                        analysis.principles.map((p, i) => (
                          <span key={i} style={{
                            padding: '3px 8px', borderRadius: 4, fontSize: 11,
                            background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                            color: 'var(--accent-blue)',
                          }}>
                            {p}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ padding: '40px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-tertiary)' }}>
                {activeTab} — 功能开发中
              </div>
            )}
          </>
        )}
      </GlassPanel>
    </div>
  );
}
