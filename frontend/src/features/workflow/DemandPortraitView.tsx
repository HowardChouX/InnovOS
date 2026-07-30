import { useState } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTaskStore } from '../../store/useTaskStore';
import { workflowApi } from '../../api/workflow';
import { StepRunningIndicator } from '../../components/ui/StepRunningIndicator';

export interface Demand {
  id: string;
  source: string;
  category: string;
  description: string;
  priority: number;
  user_rating: number | null;
}

function StarInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div style={{ display: 'flex', gap: 2, cursor: 'pointer' }}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span
          key={star}
          onClick={(e) => {
            e.stopPropagation();
            onChange(star);
          }}
          style={{
            fontSize: 18,
            color: star <= value ? '#fbbf24' : 'rgba(255,255,255,0.15)',
            transition: 'color 0.1s',
          }}
        >
          <i className="fa-solid fa-star" />
        </span>
      ))}
    </div>
  );
}

export function DemandPortraitView({ output }: { output: unknown }) {
  return <DemandPortraitViewInner key={JSON.stringify(output)} output={output} />;
}

function DemandPortraitViewInner({ output }: { output: unknown }) {
  const workflow = useWorkflowStore((s) => s.workflow);
  const fetchWorkflow = useWorkflowStore((s) => s.fetchWorkflow);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);

  const initialRatings = (() => {
    if (output && typeof output === 'object' && 'ratings' in output) {
      const out = output as {
        ratings: Array<{ demandId?: string; demand_id?: string; score: number }>;
      };
      if (out.ratings) {
        const init: Record<string, number> = {};
        for (const r of out.ratings) {
          const key = r.demandId || r.demand_id;
          if (key) init[key] = r.score;
        }
        return init;
      }
    }
    return {};
  })();

  const [ratings, setRatings] = useState<Record<string, number>>(initialRatings);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(Object.keys(initialRatings).length > 0);

  // State resets via key remount — no useEffect needed
  const [error, setError] = useState('');
  const [manualDemands, setManualDemands] = useState<Demand[]>([]);
  const [newDesc, setNewDesc] = useState('');
  const [newCategory, setNewCategory] = useState('功能需求');

  const CATEGORY_OPTIONS = ['功能需求', '性能需求', '安全需求', '体验需求', '合规需求', '其他'];

  const demands: Demand[] = (() => {
    if (output && typeof output === 'object' && 'demands' in output) {
      return (output as { demands: Demand[] }).demands || [];
    }
    return [];
  })();
  const allDemands = [...demands, ...manualDemands];

  const addManualDemand = () => {
    const desc = newDesc.trim();
    if (!desc) return;
    const newDemand: Demand = {
      id: `manual_${Date.now()}`,
      source: '手动补充',
      category: newCategory,
      description: desc,
      priority: 0.5,
      user_rating: null,
    };
    setManualDemands((prev) => [...prev, newDemand]);
    setNewDesc('');
  };

  const removeManualDemand = (id: string) => {
    setManualDemands((prev) => prev.filter((d) => d.id !== id));
    setRatings((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  // 已确认 → 显示加载状态，直到组件因 phase 切换而卸载
  // 注意：这里不应该显示，因为 WorkflowStepResults 会自动切换到下一步骤的等待画面
  if (submitted) {
    return null;  // 不返回任何内容，让父组件的 WorkflowStepResults 处理
  }

  if (!workflow || allDemands.length === 0) {
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
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无需求数据</span>
      </div>
    );
  }

  const allRated = allDemands.every((d) => (ratings[d.id] ?? 0) > 0);

  const handleSubmit = async () => {
    if (!selectedTaskId || !allRated || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const ratingsPayload = allDemands.map((d) => ({
        demandId: d.id,
        score: ratings[d.id] || 0,
      }));
      await workflowApi.proceed(selectedTaskId, ratingsPayload);
      setSubmitted(true);
      // 立即刷新工作流状态，状态机同步更新
      fetchWorkflow(selectedTaskId);
    } catch (err: unknown) {
      console.error('提交评分失败:', err);
      const msg = err instanceof Error ? err.message : '提交失败，请重试';
      setError(msg.includes('不需要评分') ? '工作流状态异常，请刷新页面后重试' : msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
      <div className="card-title">
        需求洞察
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
        请对以下需求进行评分，评分后确认进入下一步
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {demands.map((demand) => (
          <div
            key={demand.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 14px',
              borderRadius: 8,
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  marginBottom: 2,
                }}
              >
                {demand.description}
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span
                  style={{
                    fontSize: 10,
                    padding: '1px 6px',
                    borderRadius: 3,
                    background: 'rgba(59,130,246,0.1)',
                    color: 'var(--accent-blue)',
                  }}
                >
                  {demand.category}
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{demand.source}</span>
              </div>
            </div>
            <StarInput
              value={ratings[demand.id] || 0}
              onChange={(v) => setRatings((prev) => ({ ...prev, [demand.id]: v }))}
            />
          </div>
        ))}
      </div>

      {/* 手动补充需求 */}
      {!submitted && (
        <div
          style={{
            borderTop: '1px solid var(--border)',
            paddingTop: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
            补充需求
          </div>

          {manualDemands.map((d) => (
            <div
              key={d.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '10px 14px',
                borderRadius: 8,
                background: 'rgba(139,92,246,0.06)',
                border: '1px solid rgba(139,92,246,0.2)',
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    marginBottom: 2,
                  }}
                >
                  {d.description}
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span
                    style={{
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 3,
                      background: 'rgba(139,92,246,0.1)',
                      color: 'var(--accent-purple)',
                    }}
                  >
                    {d.category}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{d.source}</span>
                </div>
              </div>
              <StarInput
                value={ratings[d.id] || 0}
                onChange={(v) => setRatings((prev) => ({ ...prev, [d.id]: v }))}
              />
              <button
                onClick={() => removeManualDemand(d.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-tertiary)',
                  fontSize: 14,
                  padding: '2px 4px',
                }}
                title="删除"
              >
                <i className="fa-solid fa-xmark" />
              </button>
            </div>
          ))}

          {/* 新增需求输入 */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 12px',
              borderRadius: 8,
              background: 'rgba(0,0,0,0.15)',
              border: '1px dashed var(--border-light)',
            }}
          >
            <input
              type="text"
              placeholder="输入补充需求描述..."
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') addManualDemand();
              }}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                fontSize: 13,
                color: 'var(--text-primary)',
                fontFamily: 'inherit',
              }}
            />
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              style={{
                padding: '4px 8px',
                borderRadius: 4,
                fontSize: 12,
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid var(--border-light)',
                color: 'var(--text-primary)',
                fontFamily: 'inherit',
                cursor: 'pointer',
              }}
            >
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <button
              onClick={addManualDemand}
              disabled={!newDesc.trim()}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '4px 10px',
                borderRadius: 4,
                fontSize: 12,
                background: newDesc.trim() ? 'var(--accent-purple)' : 'var(--text-tertiary)',
                border: 'none',
                color: '#fff',
                cursor: newDesc.trim() ? 'pointer' : 'not-allowed',
                fontFamily: 'inherit',
                whiteSpace: 'nowrap',
              }}
            >
              <i className="fa-solid fa-plus" /> 添加
            </button>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
        {error && (
          <div
            style={{
              flex: 1,
              fontSize: 12,
              color: 'var(--accent-red)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <i className="fa-solid fa-circle-exclamation" />
            {error}
          </div>
        )}
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
            transition: 'all 0.15s',
          }}
        >
          {submitting ? (
            <>
              <StepRunningIndicator phaseId="demand_analysis" size={16} color="#fff" /> 提交中...
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
