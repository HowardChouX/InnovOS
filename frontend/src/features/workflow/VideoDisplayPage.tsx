/**
 * 视频展示阶段 — 真实实现（MiniMax-H3 文生视频）。
 *
 * 替换原 VideoDisplayMockPage：用户输入 prompt → 异步生成 → 后台轮询推进 →
 * 成功后原生 <video> 播放。历史列表 5s 轮询，直到无未终态任务。
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { videoApi, type GenerateInput, type VideoTask } from '../../api/video';

const RESOLUTIONS: GenerateInput['resolution'][] = ['768P', '2K'];
const RATIOS: GenerateInput['ratio'][] = ['21:9', '16:9', '4:3', '1:1', '3:4', '9:16'];
const DURATIONS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
const POLL_INTERVAL_MS = 5000;

const NON_TERMINAL = new Set(['pending', 'queued', 'running']);

const STATUS_BADGE: Record<string, { label: string; bg: string; color: string }> = {
  pending: { label: '生成中', bg: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)' },
  queued: { label: '生成中', bg: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)' },
  running: { label: '生成中', bg: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)' },
  succeeded: { label: '已生成', bg: 'rgba(34,197,94,0.1)', color: 'var(--accent-green)' },
  failed: { label: '失败', bg: 'rgba(239,68,68,0.1)', color: '#ef4444' },
  expired: { label: '失败', bg: 'rgba(239,68,68,0.1)', color: '#ef4444' },
};

export default function VideoDisplayPage() {
  const [tasks, setTasks] = useState<VideoTask[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [prompt, setPrompt] = useState('');
  const [resolution, setResolution] = useState<GenerateInput['resolution']>('768P');
  const [duration, setDuration] = useState(5);
  const [ratio, setRatio] = useState<GenerateInput['ratio']>('16:9');

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadTasks = useCallback(async () => {
    try {
      const res = await videoApi.listTasks();
      setTasks(res.data);
    } catch {
      /* 静默：下一轮重试 */
    }
  }, []);

  // 首次加载
  useEffect(() => {
    videoApi
      .listTasks()
      .then((res) => setTasks(res.data))
      .catch(() => {
        /* 静默：下一轮重试 */
      });
  }, []);

  // 轮询：有未终态任务时每 5s 刷新，否则停止
  useEffect(() => {
    const hasActive = tasks.some((t) => NON_TERMINAL.has(t.status));
    if (hasActive && timerRef.current === null) {
      timerRef.current = setInterval(loadTasks, POLL_INTERVAL_MS);
    } else if (!hasActive && timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [tasks, loadTasks]);

  const selected = tasks.find((t) => t.id === selectedId) ?? null;

  const handleGenerate = async () => {
    setFormError('');
    if (!prompt.trim()) {
      setFormError('请输入视频描述');
      return;
    }
    setSubmitting(true);
    try {
      const res = await videoApi.generate({ prompt: prompt.trim(), resolution, duration, ratio });
      setSelectedId(res.data.taskId);
      setPrompt('');
      await loadTasks();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : '生成失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="card"
      style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}
    >
      <div className="card-title">视频展示</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
        输入描述，用 MiniMax-H3 生成方案演示视频
      </div>

      {/* ── 生成表单 ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="描述你想生成的视频画面，例如：手机散热结构分层爆炸图动画"
          maxLength={7000}
          rows={3}
          style={{
            width: '100%',
            resize: 'vertical',
            padding: 10,
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            fontSize: 13,
            fontFamily: 'inherit',
          }}
        />
        <div
          style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', fontSize: 12 }}
        >
          <label style={{ color: 'var(--text-secondary)' }}>
            分辨率{' '}
            <select
              value={resolution}
              onChange={(e) => setResolution(e.target.value as GenerateInput['resolution'])}
            >
              {RESOLUTIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label style={{ color: 'var(--text-secondary)' }}>
            时长{' '}
            <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
              {DURATIONS.map((d) => (
                <option key={d} value={d}>
                  {d}s
                </option>
              ))}
            </select>
          </label>
          <label style={{ color: 'var(--text-secondary)' }}>
            宽高比{' '}
            <select
              value={ratio}
              onChange={(e) => setRatio(e.target.value as GenerateInput['ratio'])}
            >
              {RATIOS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={handleGenerate}
            disabled={submitting}
            style={{
              marginLeft: 'auto',
              padding: '8px 18px',
              borderRadius: 8,
              border: 'none',
              background: '#f97316',
              color: '#fff',
              fontSize: 13,
              fontWeight: 600,
              cursor: submitting ? 'not-allowed' : 'pointer',
              opacity: submitting ? 0.6 : 1,
            }}
          >
            {submitting ? '提交中…' : '生成视频'}
          </button>
        </div>
        {formError && <div style={{ fontSize: 12, color: '#ef4444' }}>{formError}</div>}
      </div>

      {/* ── 主播放区 ── */}
      <div
        style={{
          borderRadius: 8,
          overflow: 'hidden',
          border: '1px solid var(--border)',
          background: 'rgba(0,0,0,0.2)',
        }}
      >
        {!selected && (
          <div
            style={{
              height: 280,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-tertiary)',
              fontSize: 13,
            }}
          >
            选择下方任务以预览，或输入描述生成新视频
          </div>
        )}
        {selected && selected.status === 'succeeded' && selected.videoUrl && (
          <video
            key={selected.id}
            src={selected.videoUrl}
            controls
            style={{ width: '100%', display: 'block', maxHeight: 420, background: '#000' }}
          />
        )}
        {selected && NON_TERMINAL.has(selected.status) && (
          <div
            style={{
              height: 280,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
              color: 'var(--text-secondary)',
            }}
          >
            <i
              className="fa-solid fa-circle-notch fa-spin"
              style={{ fontSize: 32, color: '#f97316' }}
            />
            <div style={{ fontSize: 13 }}>
              视频生成中（{STATUS_BADGE[selected.status]?.label}）…
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              生成通常需要数十秒到数分钟，可离开本页，完成后自动出现在列表
            </div>
          </div>
        )}
        {selected && (selected.status === 'failed' || selected.status === 'expired') && (
          <div
            style={{
              height: 280,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              color: '#ef4444',
            }}
          >
            <i className="fa-solid fa-circle-exclamation" style={{ fontSize: 32 }} />
            <div style={{ fontSize: 13 }}>生成失败</div>
            {selected.error && (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{selected.error}</div>
            )}
          </div>
        )}
      </div>

      {/* ── 历史列表 ── */}
      <div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--text-primary)',
            marginBottom: 10,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <i className="fa-solid fa-film" style={{ color: '#f97316', fontSize: 12 }} />
          生成历史
          <span
            style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 4 }}
          >
            共 {tasks.length} 个
          </span>
        </div>
        {tasks.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', padding: '12px 0' }}>
            暂无生成记录
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {tasks.map((t) => {
            const badge = STATUS_BADGE[t.status] ?? STATUS_BADGE.pending;
            const active = t.id === selectedId;
            return (
              <div
                key={t.id}
                onClick={() => setSelectedId(t.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: active ? 'rgba(249,115,22,0.06)' : 'rgba(0,0,0,0.2)',
                  border: `1px solid ${active ? 'rgba(249,115,22,0.2)' : 'var(--border)'}`,
                  cursor: 'pointer',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {t.prompt}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {t.resolution} · {t.duration}s · {t.ratio} · {t.createdAt}
                  </div>
                </div>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: badge.bg,
                    color: badge.color,
                    fontSize: 10,
                    flexShrink: 0,
                  }}
                >
                  {badge.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
