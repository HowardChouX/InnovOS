import { useState, useEffect, useRef } from 'react';
import { useTaskStore } from '../../store/useTaskStore';
import { useAnalysisStore } from '../../store/useAnalysisStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { knowledgeApi } from '../../api/knowledge';
import type { KnowledgeBaseListItem } from '../../types/knowledge';

export function TaskInputPanel() {
  const [description, setDescription] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [bases, setBases] = useState<KnowledgeBaseListItem[]>([]);
  const [selectedBaseIds, setSelectedBaseIds] = useState<Set<string>>(new Set());
  const [showKbSelector, setShowKbSelector] = useState(false);
  const [loadingBases, setLoadingBases] = useState(false);
  const [loadError, setLoadError] = useState('');
  const selectorRef = useRef<HTMLDivElement>(null);

  const createTask = useTaskStore((s) => s.createTask);
  const triggerAnalysis = useAnalysisStore((s) => s.triggerAnalysis);
  const stopPolling = useWorkflowStore((s) => s.stopPolling);
  const workflow = useWorkflowStore((s) => s.workflow);

  // 加载知识库列表
  useEffect(() => {
    setLoadingBases(true);
    setLoadError('');
    knowledgeApi.listBases(1, 100)
      .then((res) => {
        const items = res.data?.items ?? [];
        setBases(items);
        if (items.length === 0) {
          setLoadError('暂无知识库，请先在知识库页面创建');
        }
      })
      .catch((err) => {
        console.error('Failed to load knowledge bases:', err);
        setBases([]);
        setLoadError('加载知识库失败');
      })
      .finally(() => setLoadingBases(false));
  }, []);

  // 点击外部关闭选择器
  useEffect(() => {
    if (!showKbSelector) return;
    const handler = (e: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setShowKbSelector(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showKbSelector]);

  // 根据工作流状态更新分析按钮
  useEffect(() => {
    if (!workflow) {
      setIsAnalyzing(false);
      return;
    }
    if (workflow.status === 'running') {
      setIsAnalyzing(true);
    } else if (workflow.status === 'completed' || workflow.status === 'failed') {
      setIsAnalyzing(false);
    }
  }, [workflow]);

  const toggleBase = (id: string) => {
    setSelectedBaseIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectedBases = bases.filter((b) => selectedBaseIds.has(b.id));

  const handleSubmit = async () => {
    if (!description.trim()) return;

    setIsAnalyzing(true);

    try {
      const task = await createTask({ title: description.slice(0, 50), description, tags: [] });
      if (!task) {
        setIsAnalyzing(false);
        return;
      }

      setDescription('');
      const kbIds = Array.from(selectedBaseIds);
      await triggerAnalysis(task.id, kbIds.length > 0 ? kbIds : undefined);
    } catch (error) {
      console.error('Failed to start analysis:', error);
      setIsAnalyzing(false);
    }
  };

  const handleCancel = () => {
    stopPolling();
    setIsAnalyzing(false);
  };

  return (
    <div className="card">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="card-title">创新任务输入</div>

        <div style={{ position: 'relative' }} ref={selectorRef}>
          <button
            onClick={() => setShowKbSelector(!showKbSelector)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 11, padding: '5px 12px',
              background: selectedBaseIds.size > 0 ? 'rgba(59,130,246,0.12)' : 'transparent',
              color: selectedBaseIds.size > 0 ? 'var(--accent)' : 'var(--text-secondary)',
              border: `1px solid ${selectedBaseIds.size > 0 ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
          >
            <i className="fa-solid fa-database" style={{ fontSize: 11 }} />
            导入知识库
            {selectedBaseIds.size > 0 && (
              <span style={{
                background: 'var(--accent)', color: '#fff',
                borderRadius: 10, padding: '0 6px',
                fontSize: 10, lineHeight: '16px',
              }}>
                {selectedBaseIds.size}
              </span>
            )}
            <i className="fa-solid fa-chevron-down" style={{
              fontSize: 8, marginLeft: 2,
              transform: showKbSelector ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.15s',
            }} />
          </button>

          {/* 知识库选择器下拉 */}
          {showKbSelector && (
            <div style={{
              position: 'absolute', top: '100%', right: 0, marginTop: 4,
              width: 280, maxHeight: 300, overflowY: 'auto',
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
              zIndex: 100, padding: 4,
            }}>
              {loadingBases ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
                  <i className="fa-solid fa-circle-notch fa-spin" style={{ display: 'block', fontSize: 20, marginBottom: 8 }} />
                  加载知识库...
                </div>
              ) : bases.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center' }}>
                  <i className="fa-solid fa-database" style={{ display: 'block', fontSize: 24, color: 'var(--text-tertiary)', marginBottom: 8 }} />
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    {loadError || '暂无知识库'}
                  </div>
                  <a href="/knowledge" style={{ fontSize: 11, color: 'var(--accent)' }}>
                    前往创建 →
                  </a>
                </div>
              ) : (
                <>
                  <div style={{ padding: '6px 10px', fontSize: 11, color: 'var(--text-tertiary)' }}>
                    选择知识库作为分析参考
                  </div>
                  {bases.map((base) => {
                    const active = selectedBaseIds.has(base.id);
                    return (
                      <div
                        key={base.id}
                        onClick={() => toggleBase(base.id)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          padding: '8px 10px', borderRadius: 6, cursor: 'pointer',
                          background: active ? 'rgba(59,130,246,0.1)' : 'transparent',
                          color: active ? 'var(--accent)' : 'var(--text-primary)',
                          fontSize: 13, transition: 'all 0.1s',
                        }}
                      >
                        <i
                          className={`fa-solid ${active ? 'fa-check-circle' : 'fa-circle'}`}
                          style={{ fontSize: 14, color: active ? 'var(--accent)' : 'var(--text-tertiary)' }}
                        />
                        <span style={{ flex: 1 }}>{base.name}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                          {base.itemCount ?? base.documentCount ?? 0}
                        </span>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 已选知识库芯片 */}
      {selectedBases.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {selectedBases.map((base) => (
            <span
              key={base.id}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                padding: '3px 10px 3px 8px', borderRadius: 14, fontSize: 12,
                background: 'var(--accent)', color: '#fff',
                userSelect: 'none',
              }}
            >
              <i className="fa-solid fa-check" style={{ fontSize: 10 }} />
              {base.name}
              <span style={{ fontSize: 10, opacity: 0.7 }}>
                ({base.itemCount ?? base.documentCount ?? 0})
              </span>
              <i
                className="fa-solid fa-xmark"
                style={{ fontSize: 11, cursor: 'pointer', opacity: 0.7, marginLeft: 2 }}
                onClick={(e) => { e.stopPropagation(); toggleBase(base.id); }}
              />
            </span>
          ))}
        </div>
      )}

      {/* Textarea */}
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="输入您的创新问题..."
        disabled={isAnalyzing}
        style={{
          width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 12, marginBottom: 12, minHeight: 60,
          fontSize: 14, color: 'var(--text-primary)',
          resize: 'vertical', outline: 'none', fontFamily: 'inherit',
          opacity: isAnalyzing ? 0.6 : 1,
        }}
      />

      {/* Buttons */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        {isAnalyzing && (
          <button
            onClick={handleCancel}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--accent-red)', border: 'none',
              color: '#fff', padding: '8px 20px', borderRadius: 6,
              cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
            }}
          >
            <i className="fa-solid fa-stop" style={{ fontSize: 11 }} />
            取消
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={isAnalyzing || !description.trim()}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: isAnalyzing ? 'var(--text-tertiary)' : 'var(--accent)',
            border: 'none',
            color: '#fff', padding: '8px 20px', borderRadius: 6,
            cursor: isAnalyzing ? 'not-allowed' : 'pointer', fontSize: 13, fontFamily: 'inherit',
          }}
        >
          {isAnalyzing ? (
            <>
              <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 11 }} />
              分析中...
            </>
          ) : (
            <>
              开始分析 <i className="fa-solid fa-arrow-right" style={{ fontSize: 11 }} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
