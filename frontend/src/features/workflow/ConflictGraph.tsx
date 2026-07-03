import { useMemo } from 'react';

interface ConflictGraphProps {
  centerConflict: string;
  nodes: { label: string; sublabel?: string; description?: string }[];
}

const COLORS = [
  'var(--accent-blue)',
  'var(--accent-green)',
  'var(--accent-purple)',
  'var(--accent-yellow)',
];

/** 计算 n 个节点在正多边形上的坐标 */
function computePositions(
  count: number,
  cx: number,
  cy: number,
  radius: number,
): Array<{ cx: number; cy: number }> {
  if (count === 1) return [{ cx: cx + radius, cy }];
  return Array.from({ length: count }, (_, i) => {
    const angle = (Math.PI * 2 / count) * i - Math.PI / 2;
    return { cx: cx + Math.cos(angle) * radius, cy: cy + Math.sin(angle) * radius };
  });
}

export function ConflictGraph({ centerConflict, nodes }: ConflictGraphProps) {
  const satelliteNodes = useMemo(() => nodes.slice(0, 4), [nodes]);

  // 自适应尺寸
  const viewBoxW = 600;
  const viewBoxH = Math.max(280, satelliteNodes.length === 1 ? 220 : 300);
  const CX = viewBoxW / 2;
  const CY = viewBoxH / 2;
  const ORBIT_R = Math.min(140, Math.min(viewBoxW, viewBoxH) * 0.38);
  const CENTER_R = 46;
  const NODE_W = 136;
  const NODE_H = 52;

  const positions = useMemo(
    () => computePositions(satelliteNodes.length, CX, CY, ORBIT_R),
    [satelliteNodes.length, CX, CY, ORBIT_R],
  );

  const labelStyle: React.CSSProperties = {
    fontSize: 13,
    fontWeight: 600,
    textAlign: 'center',
    lineHeight: 1.3,
    wordBreak: 'break-word',
    overflow: 'hidden',
  };

  return (
    <div
      style={{
        width: '100%',
        margin: '12px 0',
        opacity: 0,
        animation: 'graph-fadein 0.6s ease-out forwards',
      }}
    >
      <svg viewBox={`0 0 ${viewBoxW} ${viewBoxH}`} width="100%" style={{ display: 'block' }}>
        <style>{`
          @keyframes graph-fadein {
            0%   { opacity: 0; transform: scale(0.96); }
            100% { opacity: 1; transform: scale(1); }
          }
          @keyframes line-draw {
            0%   { stroke-dashoffset: 200; }
            100% { stroke-dashoffset: 0; }
          }
          @keyframes node-pop {
            0%   { opacity: 0; transform: scale(0.7); }
            100% { opacity: 1; transform: scale(1); }
          }
          @keyframes center-pulse {
            0%, 100% { filter: drop-shadow(0 0 8px rgba(96,165,250,0.2)); }
            50%      { filter: drop-shadow(0 0 18px rgba(96,165,250,0.4)); }
          }
        `}</style>

        {/* ═══ 轨道圈 ═══ */}
        <circle
          cx={CX}
          cy={CY}
          r={ORBIT_R}
          fill="none"
          stroke="var(--border)"
          strokeWidth="1"
          strokeDasharray="5 5"
          opacity="0.5"
        />

        {/* ═══ 连线（带绘制动画） ═══ */}
        {positions.map((pos, i) => {
          return (
            <line
              key={`line-${i}`}
              x1={CX}
              y1={CY}
              x2={pos.cx}
              y2={pos.cy}
              stroke={COLORS[i]}
              strokeWidth="1.5"
              opacity="0.45"
              strokeDasharray="200"
              style={{
                strokeDashoffset: 200,
                animation: `line-draw 0.5s ease-out ${0.2 + i * 0.15}s forwards`,
              }}
            />
          );
        })}

        {/* ═══ 中心节点 ═══ */}
        <g style={{ animation: 'center-pulse 3s ease-in-out infinite' }}>
          <circle
            cx={CX}
            cy={CY}
            r={CENTER_R}
            fill="var(--accent-dim, rgba(59,130,246,0.12))"
            stroke="var(--accent)"
            strokeWidth="2"
            opacity="0.9"
          />
          <foreignObject x={CX - CENTER_R + 4} y={CY - 20} width={CENTER_R * 2 - 8} height={40}>
            <div
              style={{
                ...labelStyle,
                color: 'var(--accent)',
                fontSize: 14,
              }}
            >
              {centerConflict.length > 14
                ? centerConflict.slice(0, 14) + '…'
                : centerConflict || '核心冲突'}
            </div>
          </foreignObject>
        </g>

        {/* ═══ 卫星节点（逐个动画弹入） ═══ */}
        {satelliteNodes.map((node, i) => {
          const pos = positions[i];
          const color = COLORS[i];
          return (
            <g
              key={`node-${i}`}
              style={{
                opacity: 0,
                animation: `node-pop 0.35s ease-out ${0.3 + i * 0.15}s forwards`,
              }}
            >
              {/* 节点卡片 */}
              <rect
                x={pos.cx - NODE_W / 2}
                y={pos.cy - NODE_H / 2}
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill={`${color}10`}
                stroke={`${color}40`}
                strokeWidth="1.5"
              />
              {/* 标签 */}
              <foreignObject
                x={pos.cx - NODE_W / 2 + 6}
                y={pos.cy - NODE_H / 2 + 5}
                width={NODE_W - 12}
                height={NODE_H - 10}
              >
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ ...labelStyle, color, fontSize: 12 }}>
                    {node.label.length > 16
                      ? node.label.slice(0, 16) + '…'
                      : node.label}
                  </div>
                  {(node.sublabel || node.description) && (
                    <div
                      style={{
                        fontSize: 10,
                        color: 'var(--text-tertiary)',
                        textAlign: 'center',
                        lineHeight: 1.3,
                        marginTop: 3,
                      }}
                    >
                      {(node.sublabel || node.description || '').slice(0, 20)}
                    </div>
                  )}
                </div>
              </foreignObject>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
