import { useMemo } from 'react';

interface ConflictDimension {
  id: string;
  label: string;
  icon: string;
  color: string;
  contradiction: string;
  example: string;
  severity: number;
}

interface ConflictGraphProps {
  centerConflict: string;
  dimensions: ConflictDimension[];
}

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

export function ConflictGraph({ centerConflict, dimensions }: ConflictGraphProps) {
  const nodes = useMemo(() => dimensions.slice(0, 4), [dimensions]);

  const viewBoxW = 600;
  const viewBoxH = 340;
  const CX = viewBoxW / 2;
  const CY = viewBoxH / 2;
  const ORBIT_R = 130;
  const CENTER_R = 42;
  const NODE_W = 140;
  const NODE_H = 72;

  const positions = useMemo(
    () => computePositions(nodes.length, CX, CY, ORBIT_R),
    [nodes.length, CX, CY, ORBIT_R],
  );

  const labelStyle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 600,
    textAlign: 'center',
    lineHeight: 1.3,
    wordBreak: 'break-word',
    overflow: 'hidden',
  };

  const severityColors = (n: number) => {
    if (n >= 4) return '#ef4444';
    if (n >= 3) return '#f97316';
    return '#eab308';
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
            0%, 100% { filter: drop-shadow(0 0 6px rgba(96,165,250,0.2)); }
            50%      { filter: drop-shadow(0 0 14px rgba(96,165,250,0.35)); }
          }
        `}</style>

        {/* 轨道圈 */}
        <circle
          cx={CX}
          cy={CY}
          r={ORBIT_R}
          fill="none"
          stroke="var(--border)"
          strokeWidth="1"
          strokeDasharray="5 5"
          opacity="0.4"
        />

        {/* 连线 */}
        {positions.map((pos, i) => (
          <line
            key={`line-${i}`}
            x1={CX}
            y1={CY}
            x2={pos.cx}
            y2={pos.cy}
            stroke={nodes[i].color}
            strokeWidth="1.5"
            opacity="0.4"
            strokeDasharray="200"
            style={{
              strokeDashoffset: 200,
              animation: `line-draw 0.5s ease-out ${0.2 + i * 0.12}s forwards`,
            }}
          />
        ))}

        {/* 中心节点 */}
        <g style={{ animation: 'center-pulse 3s ease-in-out infinite' }}>
          <circle
            cx={CX}
            cy={CY}
            r={CENTER_R}
            fill="rgba(59,130,246,0.12)"
            stroke="var(--accent)"
            strokeWidth="2"
            opacity="0.9"
          />
          <foreignObject x={CX - CENTER_R + 4} y={CY - 20} width={CENTER_R * 2 - 8} height={40}>
            <div
              style={{
                ...labelStyle,
                color: 'var(--accent)',
                fontSize: 13,
              }}
            >
              {centerConflict.length > 12
                ? centerConflict.slice(0, 12) + '…'
                : centerConflict || '核心冲突'}
            </div>
          </foreignObject>
        </g>

        {/* 卫星节点 */}
        {nodes.map((dim, i) => {
          const pos = positions[i];
          const color = dim.color;
          const sevColor = severityColors(dim.severity);
          return (
            <g
              key={`node-${i}`}
              style={{
                opacity: 0,
                animation: `node-pop 0.35s ease-out ${0.3 + i * 0.12}s forwards`,
              }}
            >
              {/* 卡片背景 */}
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

              {/* 左侧色条 */}
              <rect
                x={pos.cx - NODE_W / 2}
                y={pos.cy - NODE_H / 2}
                width={3}
                height={NODE_H}
                rx={1.5}
                fill={color}
                opacity={0.7}
              />

              {/* 图标 */}
              <foreignObject
                x={pos.cx - NODE_W / 2 + 10}
                y={pos.cy - 20}
                width={16}
                height={16}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <i className={`fa-solid ${dim.icon}`} style={{ fontSize: 10, color }} />
                </div>
              </foreignObject>

              {/* 标签 */}
              <foreignObject
                x={pos.cx - NODE_W / 2 + 28}
                y={pos.cy - 22}
                width={NODE_W - 38}
                height={NODE_H - 10}
              >
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ ...labelStyle, color, fontSize: 11 }}>
                    {dim.label}
                  </div>
                  <div
                    style={{
                      fontSize: 9,
                      color: 'var(--text-tertiary)',
                      lineHeight: 1.3,
                      marginTop: 2,
                    }}
                  >
                    {dim.contradiction.length > 20
                      ? dim.contradiction.slice(0, 20) + '…'
                      : dim.contradiction}
                  </div>
                </div>
              </foreignObject>

              {/* 严重度指示 */}
              <foreignObject
                x={pos.cx - NODE_W / 2 + 10}
                y={pos.cy + NODE_H / 2 - 14}
                width={NODE_W - 20}
                height={10}
              >
                <div style={{ display: 'flex', gap: 2, alignItems: 'center', justifyContent: 'center' }}>
                  {Array.from({ length: 5 }, (_, j) => (
                    <span
                      key={j}
                      style={{
                        width: 4,
                        height: 4,
                        borderRadius: '50%',
                        background: j < dim.severity ? sevColor : 'rgba(255,255,255,0.1)',
                      }}
                    />
                  ))}
                  <span style={{ fontSize: 8, color: 'var(--text-tertiary)', marginLeft: 2 }}>
                    {dim.severity}/5
                  </span>
                </div>
              </foreignObject>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
