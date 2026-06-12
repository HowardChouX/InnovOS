interface SummaryStats {
  totalSteps?: number;
  completedSteps?: number;
  duration?: string;
  phases?: Array<{ label: string; status: string }>;
}

function SummaryItem({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
  return (
    <div style={{
      background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: '10px 16px',
      border: '1px solid var(--border-light)', display: 'flex', alignItems: 'center', gap: 10,
    }}>
      <i className={icon} style={{ fontSize: 14, color }} />
      <div>
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 1 }}>{label}</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{value}</div>
      </div>
    </div>
  );
}

function parseOutput(output: any): SummaryStats {
  if (!output) return {};
  if (typeof output === 'object') {
    return {
      totalSteps: output.totalSteps,
      completedSteps: output.completedSteps,
      duration: output.duration,
      phases: output.phases,
    };
  }
  return {};
}

export function CompletedView({ output }: { output: any }) {
  const stats = parseOutput(output);

  return (
    <div className="card" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      minHeight: 280, gap: 20, padding: 40,
    }}>
      <div style={{
        width: 64, height: 64, borderRadius: '50%',
        background: 'rgba(74,222,128,0.15)', border: '2px solid rgba(74,222,128,0.3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <i className="fa-solid fa-check" style={{ fontSize: 28, color: 'var(--accent-green)' }} />
      </div>

      <div style={{ textAlign: 'center' }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 8px' }}>分析完成</h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6, maxWidth: 360 }}>
          所有分析步骤已完成，系统已生成需求洞察、问题建模、专利检索、方案生成及评估的完整结果。
        </p>
      </div>

      {(stats.totalSteps || stats.duration) && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
          {stats.totalSteps && (
            <SummaryItem
              icon="fa-solid fa-list-check"
              label="完成步骤"
              value={`${stats.completedSteps ?? stats.totalSteps}/${stats.totalSteps}`}
              color="var(--accent-green)"
            />
          )}
          {stats.duration && (
            <SummaryItem
              icon="fa-solid fa-clock"
              label="总耗时"
              value={stats.duration}
              color="var(--accent-blue)"
            />
          )}
        </div>
      )}

      <button style={{
        padding: '10px 24px', borderRadius: 8, border: 'none',
        background: 'var(--accent)', color: '#fff', fontSize: 13, fontWeight: 500,
        cursor: 'pointer', fontFamily: 'inherit',
      }}>
        <i className="fa-solid fa-file-lines" style={{ marginRight: 6 }} />
        查看完整报告
      </button>
    </div>
  );
}
