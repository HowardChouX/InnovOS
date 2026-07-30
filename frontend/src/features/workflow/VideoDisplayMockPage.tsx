import { useState } from 'react';

interface VideoItem {
  id: string;
  title: string;
  duration: string;
  description: string;
  status: '已生成' | '生成中' | '待生成';
  resolution: string;
  fileSize: string;
  createdAt: string;
}

const MOCK_VIDEOS: VideoItem[] = [
  {
    id: 'v1',
    title: '多层石墨烯-VC 均热板复合散热方案演示',
    duration: '03:24',
    description: '手机散热结构分层爆炸图动画，展示 VC 均热板 + 石墨烯 + 相变材料的协同散热路径',
    status: '已生成',
    resolution: '1920×1080',
    fileSize: '48.2 MB',
    createdAt: '2026-07-04 10:30',
  },
  {
    id: 'v2',
    title: '芯片热流分布 3D 可视化',
    duration: '02:15',
    description: '骁龙 8 Gen3 芯片在高负载场景下的热流分布热力图 3D 旋转展示',
    status: '已生成',
    resolution: '1920×1080',
    fileSize: '32.7 MB',
    createdAt: '2026-07-04 10:32',
  },
  {
    id: 'v3',
    title: '散热性能对比测试',
    duration: '04:30',
    description: '本方案与传统石墨片、铜管散热方案的温升曲线对比，峰值降温 10°C',
    status: '生成中',
    resolution: '1280×720',
    fileSize: '—',
    createdAt: '2026-07-04 10:35',
  },
  {
    id: 'v4',
    title: '量产工艺流程演示',
    duration: '01:45',
    description: '石墨烯薄膜制备 → VC 均热板焊接 → 多层贴合组装的全流程动画',
    status: '待生成',
    resolution: '—',
    fileSize: '—',
    createdAt: '—',
  },
];

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  '已生成': { bg: 'rgba(34,197,94,0.1)', color: 'var(--accent-green)' },
  '生成中': { bg: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)' },
  '待生成': { bg: 'rgba(255,255,255,0.05)', color: 'var(--text-tertiary)' },
};

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

function parseDuration(s: string): number {
  const [m, sec] = s.split(':').map(Number);
  return m * 60 + sec;
}

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function VideoDisplayMockPage() {
  const [playing, setPlaying] = useState(false);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [progress, setProgress] = useState(68);
  const [speed, setSpeed] = useState(1);
  const [volume, setVolume] = useState(80);
  const [muted, setMuted] = useState(false);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);

  const video = MOCK_VIDEOS[currentIdx];
  const totalSec = parseDuration(video.duration);
  const currentSec = (progress / 100) * totalSec;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
      <div className="card-title">视频展示</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>当前任务的方案视频化展示</div>

      {/* 主播放器 */}
      <div
        style={{
          borderRadius: 8,
          overflow: 'hidden',
          border: '1px solid var(--border)',
          background: 'rgba(0,0,0,0.2)',
        }}
        onClick={() => {
          if (video.status === '已生成') setPlaying(!playing);
        }}
      >
        {/* 标题栏 */}
        <div
          style={{
            padding: '10px 14px',
            borderBottom: '1px solid var(--border-light)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <i className="fa-solid fa-circle-play" style={{ color: '#f97316', fontSize: 13 }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
            {video.title}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
            {video.resolution}
          </span>
        </div>

        {/* 画面区 — 手机散热结构可视化 */}
        <div
          style={{
            height: 340,
            background: 'linear-gradient(180deg, #0a0e1a 0%, #0f1729 50%, #0a0e1a 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            overflow: 'hidden',
            cursor: 'pointer',
          }}
        >
          {/* 背景热力网格 */}
          <div style={{
            position: 'absolute', inset: 0,
            backgroundImage: 'linear-gradient(rgba(249,115,22,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(249,115,22,0.03) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }} />

          {/* 左侧: 手机散热截面分层图 */}
          <div style={{ position: 'relative', width: 260, height: 280 }}>
            {/* 手机轮廓 */}
            <div style={{
              position: 'absolute', left: 30, top: 10, width: 200, height: 260,
              border: '2px solid rgba(255,255,255,0.12)',
              borderRadius: 24,
            }} />

            {/* 散热层 — 从下到上逐层展开 */}
            {[
              { label: 'VC 均热板', color: 'rgba(59,130,246,0.6)', border: 'rgba(59,130,246,0.8)', y: 200, icon: 'fa-water', temp: '85°C → 42°C' },
              { label: '石墨烯导热层', color: 'rgba(139,92,246,0.5)', border: 'rgba(139,92,246,0.8)', y: 160, icon: 'fa-layer-group', temp: '导热系数 1500W/mK' },
              { label: '相变材料层', color: 'rgba(34,197,94,0.45)', border: 'rgba(34,197,94,0.8)', y: 120, icon: 'fa-droplet', temp: '潜热 180J/g' },
              { label: '石墨烯散热膜', color: 'rgba(249,115,22,0.5)', border: 'rgba(249,115,22,0.8)', y: 80, icon: 'fa-wind', temp: '厚度 0.1mm' },
              { label: '外壳散热涂层', color: 'rgba(236,72,153,0.4)', border: 'rgba(236,72,153,0.7)', y: 40, icon: 'fa-shield', temp: '辐射散热 +15%' },
            ].map((layer, i) => (
              <div key={i} style={{
                position: 'absolute', left: 50, top: layer.y, width: 160, height: 28,
                borderRadius: 4,
                background: layer.color,
                border: `1px solid ${layer.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                gap: 6,
                fontSize: 10, fontWeight: 600, color: '#fff',
                boxShadow: `0 0 12px ${layer.color}`,
                transition: 'transform 0.3s',
              }}
              onMouseOver={(e) => { e.currentTarget.style.transform = 'scale(1.05) translateX(6px)'; }}
              onMouseOut={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
              >
                <i className={`fa-solid ${layer.icon}`} style={{ fontSize: 9 }} />
                {layer.label}
              </div>
            ))}

            {/* 左侧连线标注 */}
            {[
              { y: 214, text: '85°C → 42°C', color: '#3b82f6' },
              { y: 174, text: '1500 W/mK', color: '#8b5cf6' },
              { y: 134, text: '180 J/g', color: '#22c55e' },
              { y: 94, text: '0.1mm', color: '#f97316' },
              { y: 54, text: '+15%', color: '#ec4899' },
            ].map((ann, i) => (
              <div key={i} style={{
                position: 'absolute', left: 218, top: ann.y, fontSize: 9,
                color: ann.color, fontFamily: 'monospace', fontWeight: 600,
                whiteSpace: 'nowrap',
              }}>
                {ann.text}
              </div>
            ))}
          </div>

          {/* 右侧: 散热数据面板 */}
          <div style={{ marginLeft: 32, display: 'flex', flexDirection: 'column', gap: 10, width: 180 }}>
            {[
              { label: '芯片温度', value: '42°C', bar: 42, max: 100, color: '#3b82f6' },
              { label: '散热效率', value: '96.2%', bar: 96, max: 100, color: '#22c55e' },
              { label: '均温性', value: '±1.5°C', bar: 85, max: 100, color: '#8b5cf6' },
              { label: '功耗控制', value: '3.8W', bar: 38, max: 10, color: '#f97316' },
            ].map((stat, i) => (
              <div key={i}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3 }}>
                  <span>{stat.label}</span>
                  <span style={{ color: stat.color, fontWeight: 600, fontFamily: 'monospace' }}>{stat.value}</span>
                </div>
                <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)' }}>
                  <div style={{
                    width: `${stat.bar}%`, height: '100%', borderRadius: 2,
                    background: `linear-gradient(90deg, ${stat.color}88, ${stat.color})`,
                    boxShadow: `0 0 6px ${stat.color}44`,
                  }} />
                </div>
              </div>
            ))}

            {/* 热流箭头指示 */}
            <div style={{
              marginTop: 4, padding: '8px 10px', borderRadius: 6,
              background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.15)',
              fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                <i className="fa-solid fa-arrow-up" style={{ color: '#f97316', fontSize: 9 }} />
                <span style={{ fontWeight: 600, color: '#f97316' }}>热流路径</span>
              </div>
              芯片 → VC均热板 → 石墨烯 → 相变层 → 外壳
            </div>
          </div>

          {/* 右上角时间叠加 */}
          <div
            style={{
              position: 'absolute',
              top: 10,
              right: 12,
              fontSize: 11,
              padding: '3px 8px',
              borderRadius: 4,
              background: 'rgba(0,0,0,0.6)',
              color: '#fff',
              fontFamily: 'monospace',
            }}
          >
            {formatTime(currentSec)} / {video.duration}
          </div>

          {/* 播放状态指示 */}
          {playing && (
            <div
              style={{
                position: 'absolute',
                top: 10,
                left: 12,
                fontSize: 10,
                padding: '3px 8px',
                borderRadius: 4,
                background: 'rgba(249,115,22,0.9)',
                color: '#fff',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff' }} />
              播放中
            </div>
          )}
        </div>

        {/* 进度条（可点击） */}
        <div
          style={{
            height: 4,
            background: 'rgba(255,255,255,0.1)',
            cursor: 'pointer',
            position: 'relative',
          }}
          onClick={(e) => {
            e.stopPropagation();
            const rect = e.currentTarget.getBoundingClientRect();
            const pct = ((e.clientX - rect.left) / rect.width) * 100;
            setProgress(Math.max(0, Math.min(100, pct)));
          }}
        >
          <div
            style={{
              width: `${progress}%`,
              height: '100%',
              background: '#f97316',
              position: 'relative',
              transition: 'width 0.1s',
            }}
          >
            {/* 拖拽手柄 */}
            <div
              style={{
                position: 'absolute',
                right: -5,
                top: -3,
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: '#f97316',
                boxShadow: '0 0 4px rgba(249,115,22,0.5)',
              }}
            />
          </div>
        </div>

        {/* 控制栏 */}
        <div
          style={{
            padding: '8px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            color: 'var(--text-tertiary)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* 上一个 */}
          <button
            onClick={() => setCurrentIdx(Math.max(0, currentIdx - 1))}
            style={ctrlBtnStyle}
            title="上一个"
          >
            <i className="fa-solid fa-backward-step" />
          </button>

          {/* 播放/暂停 */}
          <button
            onClick={() => {
              if (video.status === '已生成') setPlaying(!playing);
            }}
            style={{
              ...ctrlBtnStyle,
              width: 36,
              height: 36,
              borderRadius: '50%',
              background: 'rgba(249,115,22,0.15)',
              color: '#f97316',
              fontSize: 14,
            }}
            title={playing ? '暂停' : '播放'}
          >
            <i className={`fa-solid ${playing ? 'fa-pause' : 'fa-play'}`} style={{ marginLeft: playing ? 0 : 2 }} />
          </button>

          {/* 下一个 */}
          <button
            onClick={() => setCurrentIdx(Math.min(MOCK_VIDEOS.length - 1, currentIdx + 1))}
            style={ctrlBtnStyle}
            title="下一个"
          >
            <i className="fa-solid fa-forward-step" />
          </button>

          {/* 时间 */}
          <span style={{ fontSize: 11, fontFamily: 'monospace', marginLeft: 4, color: 'var(--text-secondary)' }}>
            {formatTime(currentSec)} / {video.duration}
          </span>

          {/* 倍速 */}
          <div style={{ position: 'relative', marginLeft: 8 }}>
            <button
              onClick={() => setShowSpeedMenu(!showSpeedMenu)}
              style={{
                ...ctrlBtnStyle,
                fontSize: 11,
                fontWeight: 600,
                padding: '0 6px',
                width: 'auto',
                background: speed !== 1 ? 'rgba(249,115,22,0.1)' : undefined,
                color: speed !== 1 ? '#f97316' : undefined,
              }}
            >
              {speed}x
            </button>
            {showSpeedMenu && (
              <div
                style={{
                  position: 'absolute',
                  bottom: '100%',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  marginBottom: 6,
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '4px 0',
                  zIndex: 10,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                }}
              >
                {SPEEDS.map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setSpeed(s);
                      setShowSpeedMenu(false);
                    }}
                    style={{
                      display: 'block',
                      width: '100%',
                      padding: '4px 16px',
                      fontSize: 11,
                      textAlign: 'center',
                      background: s === speed ? 'rgba(249,115,22,0.1)' : 'transparent',
                      color: s === speed ? '#f97316' : 'var(--text-secondary)',
                      border: 'none',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 右侧控制 */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* 音量 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <button
                onClick={() => setMuted(!muted)}
                style={ctrlBtnStyle}
                title={muted ? '取消静音' : '静音'}
              >
                <i className={`fa-solid ${muted || volume === 0 ? 'fa-volume-xmark' : volume < 50 ? 'fa-volume-low' : 'fa-volume-high'}`} />
              </button>
              <input
                type="range"
                min={0}
                max={100}
                value={muted ? 0 : volume}
                onChange={(e) => {
                  setVolume(Number(e.target.value));
                  if (muted) setMuted(false);
                }}
                style={{
                  width: 60,
                  height: 3,
                  accentColor: '#f97316',
                  cursor: 'pointer',
                }}
              />
            </div>

            {/* 画中画 */}
            <button style={ctrlBtnStyle} title="画中画">
              <i className="fa-solid fa-window-restore" />
            </button>

            {/* 全屏 */}
            <button style={ctrlBtnStyle} title="全屏">
              <i className="fa-solid fa-expand" />
            </button>
          </div>
        </div>
      </div>

      {/* 视频列表 */}
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
          方案视频资源
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 4 }}>
            共 {MOCK_VIDEOS.length} 个
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {MOCK_VIDEOS.map((v, idx) => {
            const st = STATUS_STYLE[v.status];
            const active = idx === currentIdx;
            return (
              <div
                key={v.id}
                onClick={() => {
                  if (v.status === '已生成') {
                    setCurrentIdx(idx);
                    setProgress(0);
                    setPlaying(true);
                  }
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: active ? 'rgba(249,115,22,0.06)' : 'rgba(0,0,0,0.2)',
                  border: `1px solid ${active ? 'rgba(249,115,22,0.2)' : 'var(--border)'}`,
                  cursor: v.status === '已生成' ? 'pointer' : 'default',
                  opacity: v.status === '待生成' ? 0.5 : 1,
                }}
              >
                {/* 序号 / 播放图标 */}
                <span
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    background: active ? '#f97316' : 'rgba(255,255,255,0.08)',
                    color: active ? '#fff' : 'var(--text-tertiary)',
                    fontSize: 11,
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  {active && playing ? (
                    <i className="fa-solid fa-volume-high" style={{ fontSize: 10 }} />
                  ) : (
                    idx + 1
                  )}
                </span>

                {/* 信息 */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {v.title}
                    </span>
                    {active && (
                      <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: '#f97316', color: '#fff', fontWeight: 600 }}>
                        当前
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {v.description}
                  </div>
                </div>

                {/* 元数据 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, fontSize: 11, color: 'var(--text-tertiary)' }}>
                  <span style={{ fontFamily: 'monospace' }}>{v.duration}</span>
                  <span>{v.resolution}</span>
                  <span>{v.fileSize}</span>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      background: st.bg,
                      color: st.color,
                      fontSize: 10,
                    }}
                  >
                    {v.status}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const ctrlBtnStyle: React.CSSProperties = {
  width: 28,
  height: 28,
  borderRadius: 4,
  background: 'transparent',
  border: 'none',
  color: 'var(--text-tertiary)',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 13,
  padding: 0,
  fontFamily: 'inherit',
};
