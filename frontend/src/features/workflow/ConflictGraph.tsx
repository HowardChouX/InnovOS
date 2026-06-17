import { useMemo } from 'react';

interface ConflictGraphProps {
  centerConflict: string;
  nodes: { label: string; sublabel?: string; description?: string }[];
}

const POSITIONS: Array<{ cx: number; cy: number }> = [
  { cx: 200, cy: 40 },   // top
  { cx: 370, cy: 120 },  // right
  { cx: 200, cy: 200 },  // bottom
  { cx: 30, cy: 120 },   // left
];

const CENTER = { cx: 200, cy: 120 };
const COLORS = ['#60a5fa', '#4ade80', '#a78bfa', '#fbbf24'];

export function ConflictGraph({ centerConflict, nodes }: ConflictGraphProps) {
  const satelliteNodes = useMemo(() => nodes.slice(0, 4), [nodes]);

  return (
    <div style={{ width: '100%', margin: '8px 0' }}>
      <svg
        viewBox="0 0 400 240"
        width="100%"
        height="240"
        style={{ display: 'block' }}
      >
        {/* 虚线圆 */}
        <circle
          cx={CENTER.cx} cy={CENTER.cy} r={80}
          stroke="rgba(59,130,246,0.15)" strokeWidth="1" fill="none"
          strokeDasharray="4 4"
        />

        {/* 连线 */}
        {satelliteNodes.map((node, i) => {
          const pos = POSITIONS[i % POSITIONS.length];
          return (
            <line
              key={i}
              x1={pos.cx} y1={pos.cy}
              x2={CENTER.cx} y2={CENTER.cy}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={1}
              strokeDasharray="4 2"
              opacity={0.4}
            />
          );
        })}

        {/* 中心节点 */}
        <circle
          cx={CENTER.cx} cy={CENTER.cy} r={44}
          fill="rgba(59,130,246,0.12)"
          stroke="rgba(59,130,246,0.35)"
          strokeWidth={2}
        />
        <foreignObject x={CENTER.cx - 40} y={CENTER.cy - 20} width={80} height={40}>
          <div
            xmlns="http://www.w3.org/1999/xhtml"
            style={{
              fontSize: 12, fontWeight: 600, color: '#60a5fa',
              textAlign: 'center', lineHeight: 1.4,
              wordBreak: 'break-all', overflow: 'hidden',
            }}
          >
            {centerConflict.length > 12 ? centerConflict.slice(0, 12) + '...' : (centerConflict || '核心冲突')}
          </div>
        </foreignObject>

        {/* 卫星节点 */}
        {satelliteNodes.map((node, i) => {
          const pos = POSITIONS[i % POSITIONS.length];
          const color = COLORS[i % COLORS.length];
          return (
            <g key={i}>
              <rect
                x={pos.cx - 62} y={pos.cy - 26}
                width={124} height={52}
                rx={8}
                fill={`${color}15`}
                stroke={`${color}40`}
                strokeWidth={1}
              />
              <foreignObject x={pos.cx - 58} y={pos.cy - 24} width={116} height={48}>
                <div
                  xmlns="http://www.w3.org/1999/xhtml"
                  style={{
                    textAlign: 'center', overflow: 'hidden',
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 600, color, lineHeight: '16px' }}>
                    {node.label}
                  </div>
                  {(node.sublabel || node.description) && (
                    <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', lineHeight: '13px', marginTop: 2 }}>
                      {(node.sublabel || node.description || '').slice(0, 18)}
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
