/**
 * 视频展示阶段 — Mock 视图
 *
 * 第 7 阶段：创新方案视频化展示。
 * 当前为 Mock 实现，使用图片占位，后续替换为真实视频/图片资源。
 */

interface VideoItem {
  id: string;
  title: string;
  duration: string;
  thumbnail?: string; // 后续可填图片路径
  description: string;
}

const MOCK_VIDEOS: VideoItem[] = [
  {
    id: 'v1',
    title: '方案原理动画演示',
    duration: '03:24',
    description: '双金属活性中心协同催化机理动画，展示 Zr/Ce 位点协同作用与低温活性来源',
  },
  {
    id: 'v2',
    title: '催化剂结构 3D 展示',
    duration: '02:15',
    description: '多级孔 SAPO-34 分子筛骨架结构 3D 旋转展示，突出介孔-微孔协同扩散优势',
  },
  {
    id: 'v3',
    title: '工艺流程图解',
    duration: '04:30',
    description: 'MTO 工艺全流程动画：甲醇进料 → 催化反应 → 产物分离 → 循环再生',
  },
  {
    id: 'v4',
    title: '技术对比分析',
    duration: '01:45',
    description: '本方案与传统催化剂在活性、选择性、抗毒性维度的动态对比图表',
  },
];

export function VideoDisplayView({ output: _output }: { output: unknown }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '20px 0' }}>
      {/* ─── 主视频播放区（Mock 边框，图片占位） ─── */}
      <div
        style={{
          background: 'var(--bg-card)',
          borderRadius: 12,
          border: '1px solid var(--border)',
          overflow: 'hidden',
        }}
      >
        {/* 播放器标题栏 */}
        <div
          style={{
            padding: '12px 18px',
            background: 'rgba(0,0,0,0.2)',
            borderBottom: '1px solid var(--border-light)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <i className="fa-solid fa-circle-play" style={{ color: '#f97316', fontSize: 14 }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
            方案原理动画演示
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
            03:24 / 05:00
          </span>
        </div>

        {/* 视频画面占位区 — 后续替换为图片/视频 */}
        <div
          style={{
            height: 320,
            background:
              'radial-gradient(circle at 50% 45%, rgba(249,115,22,0.06) 0%, rgba(0,0,0,0.35) 100%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            borderBottom: '1px solid var(--border-light)',
          }}
        >
          {/* 占位提示 */}
          <div style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
            <i
              className="fa-solid fa-image"
              style={{ fontSize: 40, marginBottom: 12, opacity: 0.3 }}
            />
            <div style={{ fontSize: 13, marginBottom: 4 }}>视频画面占位区</div>
            <div style={{ fontSize: 11, opacity: 0.6 }}>后续替换为方案演示图片/视频</div>
          </div>

          {/* 播放按钮 */}
          <div
            style={{
              position: 'absolute',
              width: 56,
              height: 56,
              borderRadius: '50%',
              background: 'rgba(249,115,22,0.9)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 4px 20px rgba(249,115,22,0.3)',
              transition: 'transform 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.transform = 'scale(1.1)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = 'scale(1)';
            }}
          >
            <i className="fa-solid fa-play" style={{ color: '#fff', fontSize: 18, marginLeft: 3 }} />
          </div>
        </div>

        {/* 进度条 */}
        <div style={{ height: 3, background: 'rgba(0,0,0,0.3)' }}>
          <div style={{ width: '68%', height: '100%', background: '#f97316', opacity: 0.8 }} />
        </div>

        {/* 控制栏 */}
        <div
          style={{
            padding: '10px 18px',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            fontSize: 12,
            color: 'var(--text-tertiary)',
          }}
        >
          <i className="fa-solid fa-backward-step" style={{ cursor: 'pointer' }} />
          <i className="fa-solid fa-play" style={{ cursor: 'pointer', color: '#f97316' }} />
          <i className="fa-solid fa-forward-step" style={{ cursor: 'pointer' }} />
          <i className="fa-solid fa-volume-high" style={{ cursor: 'pointer', marginLeft: 'auto' }} />
          <i className="fa-solid fa-expand" style={{ cursor: 'pointer' }} />
        </div>
      </div>

      {/* ─── 视频列表 ─── */}
      <div
        style={{
          background: 'var(--bg-card)',
          borderRadius: 12,
          border: '1px solid var(--border)',
          padding: 20,
        }}
      >
        <div
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--text-primary)',
            marginBottom: 14,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <i className="fa-solid fa-film" style={{ color: '#f97316' }} />
          方案视频资源
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 12,
          }}
        >
          {MOCK_VIDEOS.map((video, idx) => (
            <div
              key={video.id}
              style={{
                borderRadius: 10,
                overflow: 'hidden',
                border: '1px solid var(--border-light)',
                background: 'rgba(0,0,0,0.15)',
                cursor: 'pointer',
                transition: 'border-color 0.2s',
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.borderColor = '#f9731680';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-light)';
              }}
            >
              {/* 缩略图占位 */}
              <div
                style={{
                  height: 100,
                  background:
                    idx === 0
                      ? 'radial-gradient(circle at 50% 50%, rgba(249,115,22,0.1) 0%, rgba(0,0,0,0.3) 100%)'
                      : 'rgba(0,0,0,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  position: 'relative',
                }}
              >
                <i
                  className="fa-solid fa-image"
                  style={{ fontSize: 24, color: 'var(--text-tertiary)', opacity: 0.3 }}
                />
                <span
                  style={{
                    position: 'absolute',
                    bottom: 6,
                    right: 8,
                    fontSize: 10,
                    padding: '1px 6px',
                    borderRadius: 4,
                    background: 'rgba(0,0,0,0.6)',
                    color: '#fff',
                  }}
                >
                  {video.duration}
                </span>
                {idx === 0 && (
                  <div
                    style={{
                      position: 'absolute',
                      top: 6,
                      left: 8,
                      fontSize: 9,
                      padding: '1px 6px',
                      borderRadius: 4,
                      background: '#f97316',
                      color: '#fff',
                      fontWeight: 600,
                    }}
                  >
                    正在播放
                  </div>
                )}
              </div>

              {/* 文字信息 */}
              <div style={{ padding: '10px 12px' }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'var(--text-primary)',
                    marginBottom: 4,
                  }}
                >
                  {video.title}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--text-tertiary)',
                    lineHeight: 1.4,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}
                >
                  {video.description}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ─── Mock 提示 ─── */}
      <div
        style={{
          padding: '10px 14px',
          borderRadius: 8,
          background: 'rgba(249,115,22,0.06)',
          border: '1px solid rgba(249,115,22,0.15)',
          fontSize: 11,
          color: 'var(--text-tertiary)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <i className="fa-solid fa-circle-info" style={{ color: '#f97316' }} />
        视频展示为 Mock 演示阶段，画面区域后续将替换为实际方案演示素材。
      </div>
    </div>
  );
}