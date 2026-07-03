/**
 * 流水线各阶段运行中动画
 *
 * 每个阶段有独立的视觉语义：
 *   demand_portrait  → A 波纹脉冲（发散搜索）
 *   problem_modeling  → C 六边形网络（结构分析）
 *   patent_search     → B 点阵呼吸（多源检索）
 *   solution_gen      → D 环形进度条（推进式生成）
 *   evaluation        → E 雷达扫描（多维度评估）
 *   conversion        → F 数据流聚合（收敛输出）
 */

import { memo } from 'react';

interface Props {
  phaseId: string;
  size?: number;
  color?: string;
}

function StepRunningIndicatorRaw({ phaseId, size = 20, color = 'var(--accent-blue)' }: Props) {
  const anim = ANIMATIONS[phaseId] || ANIMATIONS.default;
  return (
    <div
      style={{
        width: size,
        height: size,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {anim(size, color)}
    </div>
  );
}

export const StepRunningIndicator = memo(StepRunningIndicatorRaw);

const ANIMATIONS: Record<string, (s: number, c: string) => React.ReactNode> = {
  // ═══ A 波纹脉冲 ═══
  demand_portrait: (s, c) => (
    <svg viewBox="0 0 40 40" width={s} height={s}>
      <circle cx="20" cy="20" r="4" fill={c} />
      <circle cx="20" cy="20" r="4" fill="none" stroke={c} strokeWidth="1.5">
        <animate attributeName="r" values="5;18;5" dur="1.6s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.6;0;0.6" dur="1.6s" repeatCount="indefinite" />
      </circle>
      <circle cx="20" cy="20" r="4" fill="none" stroke={c} strokeWidth="1">
        <animate attributeName="r" values="5;18;5" dur="1.6s" begin="0.5s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.4;0;0.4" dur="1.6s" begin="0.5s" repeatCount="indefinite" />
      </circle>
      <circle cx="20" cy="20" r="4" fill="none" stroke={c} strokeWidth="0.8">
        <animate attributeName="r" values="5;18;5" dur="1.6s" begin="1s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.3;0;0.3" dur="1.6s" begin="1s" repeatCount="indefinite" />
      </circle>
    </svg>
  ),

  // ═══ B 点阵呼吸 ═══
  patent_search: (s, c) => (
    <svg viewBox="0 0 40 40" width={s} height={s}>
      {[0, 1, 2, 3, 4].map((i) => (
        <circle
          key={i}
          cx={6 + i * 7}
          cy="20"
          r="3"
          fill={c}
          opacity="0.2"
        >
          <animate
            attributeName="opacity"
            values="0.2;1;0.2"
            dur="1.4s"
            begin={`${i * 0.14}s`}
            repeatCount="indefinite"
          />
          <animate
            attributeName="r"
            values="2;4;2"
            dur="1.4s"
            begin={`${i * 0.14}s`}
            repeatCount="indefinite"
          />
        </circle>
      ))}
    </svg>
  ),

  // ═══ C 六边形网络脉冲 ═══
  problem_modeling: (s, c) => {
    const R = s * 0.38;
    const cx = s / 2;
    const cy = s / 2;
    const nodes = Array.from({ length: 6 }, (_, i) => {
      const a = (Math.PI * 2 / 6) * i - Math.PI / 2;
      return { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R };
    });
    return (
      <svg viewBox={`0 0 ${s} ${s}`} width={s} height={s}>
        {nodes.map((_, i) => {
          const j = (i + 1) % 6;
          return (
            <line
              key={`l${i}`}
              x1={nodes[i].x} y1={nodes[i].y}
              x2={nodes[j].x} y2={nodes[j].y}
              stroke={c}
              strokeWidth="0.8"
              opacity="0.25"
            />
          );
        })}
        {nodes.map((n, i) => (
          <circle key={`n${i}`} cx={n.x} cy={n.y} r="2" fill={c} opacity="0.15">
            <animate
              attributeName="opacity"
              values="0.15;1;0.15"
              dur="1.8s"
              begin={`${i * 0.2}s`}
              repeatCount="indefinite"
            />
            <animate
              attributeName="r"
              values="1.5;3.5;1.5"
              dur="1.8s"
              begin={`${i * 0.2}s`}
              repeatCount="indefinite"
            />
          </circle>
        ))}
      </svg>
    );
  },

  // ═══ D 环形进度条 ═══
  solution_gen: (s, c) => {
    const r = s * 0.42;
    const cx = s / 2;
    const cy = s / 2;
    return (
      <svg viewBox={`0 0 ${s} ${s}`} width={s} height={s}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--border)" strokeWidth="2.5" />
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={c}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray="30 80"
        >
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`0 ${cx} ${cy}`}
            to={`360 ${cx} ${cy}`}
            dur="1.2s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="stroke-dasharray"
            values="10 80;50 80;10 80"
            dur="1.5s"
            repeatCount="indefinite"
          />
        </circle>
        <circle cx={cx} cy={cy} r="2.5" fill={c} opacity="0.6" />
      </svg>
    );
  },

  // ═══ E 雷达扫描 ═══
  evaluation: (s, c) => {
    const cx = s / 2;
    const cy = s / 2;
    const R = s * 0.43;
    return (
      <svg viewBox={`0 0 ${s} ${s}`} width={s} height={s}>
        <circle cx={cx} cy={cy} r={R} fill="none" stroke="var(--border)" strokeWidth="0.8" />
        <circle cx={cx} cy={cy} r={R * 0.65} fill="none" stroke="var(--border)" strokeWidth="0.8" />
        <circle cx={cx} cy={cy} r={R * 0.35} fill="none" stroke="var(--border)" strokeWidth="0.8" />
        <line
          x1={cx} y1={cy}
          x2={cx} y2={cy - R}
          stroke={c}
          strokeWidth="1.2"
          opacity="0.7"
        >
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`0 ${cx} ${cy}`}
            to={`360 ${cx} ${cy}`}
            dur="2s"
            repeatCount="indefinite"
          />
        </line>
        <circle cx={cx} cy={cy} r="2" fill={c} opacity="0.6" />
      </svg>
    );
  },

  // ═══ F 数据流聚合 ═══
  conversion: (s, c) => {
    const cx = s / 2;
    const cy = s / 2;
    const R = s * 0.45;
    const green = 'var(--accent-green, #4ade80)';
    return (
      <svg viewBox={`0 0 ${s} ${s}`} width={s} height={s}>
        {/* 左→中 汇入 */}
        <path d={`M${cx - R} ${cy - R * 0.5} Q${cx - R * 0.3} ${cy - R * 0.5} ${cx} ${cy}`} fill="none" stroke={c} strokeWidth="1.2" opacity="0.25">
          <animate attributeName="stroke-dasharray" values="0 60;40 60;0 60" dur="2s" repeatCount="indefinite" />
        </path>
        <path d={`M${cx - R} ${cy} Q${cx - R * 0.3} ${cy} ${cx} ${cy}`} fill="none" stroke={c} strokeWidth="1.2" opacity="0.4">
          <animate attributeName="stroke-dasharray" values="0 60;40 60;0 60" dur="2s" begin="0.25s" repeatCount="indefinite" />
        </path>
        <path d={`M${cx - R} ${cy + R * 0.5} Q${cx - R * 0.3} ${cy + R * 0.5} ${cx} ${cy}`} fill="none" stroke={c} strokeWidth="1.2" opacity="0.25">
          <animate attributeName="stroke-dasharray" values="0 60;40 60;0 60" dur="2s" begin="0.5s" repeatCount="indefinite" />
        </path>
        {/* 中→右 散出 */}
        <path d={`M${cx} ${cy} Q${cx + R * 0.3} ${cy - R * 0.5} ${cx + R} ${cy - R * 0.5}`} fill="none" stroke={green} strokeWidth="1.2" opacity="0.25">
          <animate attributeName="stroke-dasharray" values="0 60;40 60;0 60" dur="2s" begin="0.9s" repeatCount="indefinite" />
        </path>
        <path d={`M${cx} ${cy} Q${cx + R * 0.3} ${cy} ${cx + R} ${cy}`} fill="none" stroke={green} strokeWidth="1.2" opacity="0.4">
          <animate attributeName="stroke-dasharray" values="0 60;40 60;0 60" dur="2s" begin="1.15s" repeatCount="indefinite" />
        </path>
        <path d={`M${cx} ${cy} Q${cx + R * 0.3} ${cy + R * 0.5} ${cx + R} ${cy + R * 0.5}`} fill="none" stroke={green} strokeWidth="1.2" opacity="0.25">
          <animate attributeName="stroke-dasharray" values="0 60;40 60;0 60" dur="2s" begin="1.4s" repeatCount="indefinite" />
        </path>
        <circle cx={cx} cy={cy} r="3" fill={c} opacity="0.7" />
      </svg>
    );
  },

  // ═══ 默认 fallback ═══
  default: (s, c) => {
    const r = s * 0.42;
    return (
      <svg viewBox={`0 0 ${s} ${s}`} width={s} height={s}>
        <circle cx={s / 2} cy={s / 2} r={r} fill="none" stroke="var(--border)" strokeWidth="2" />
        <circle
          cx={s / 2} cy={s / 2} r={r}
          fill="none"
          stroke={c}
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="30 80"
        >
          <animateTransform
            attributeName="transform"
            type="rotate"
            from={`0 ${s / 2} ${s / 2}`}
            to={`360 ${s / 2} ${s / 2}`}
            dur="1s"
            repeatCount="indefinite"
          />
        </circle>
      </svg>
    );
  },
};

// ═══ 新阶段 ID 别名（重命名后兼容） ═══
ANIMATIONS.demand_analysis = ANIMATIONS.demand_portrait;
ANIMATIONS.problem_definition = ANIMATIONS.problem_modeling;
ANIMATIONS.video_display = ANIMATIONS.conversion;
