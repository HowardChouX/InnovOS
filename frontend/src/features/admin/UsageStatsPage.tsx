import { useEffect, useState } from 'react';
import {
  usageApi,
  type UsageRange,
  type UsageSummary,
  type ProviderUsage,
  type ModelUsage,
  type CallLogRow,
} from '../../api/admin/usage';

const ranges: UsageRange[] = ['1d', '7d', '30d', '90d'];

export function UsageStatsPage() {
  const [range, setRange] = useState<UsageRange>('7d');
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [byProvider, setByProvider] = useState<ProviderUsage[]>([]);
  const [byModel, setByModel] = useState<ModelUsage[]>([]);
  const [recent, setRecent] = useState<CallLogRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      usageApi.summary(range),
      usageApi.byProvider(range),
      usageApi.byModel(range),
      usageApi.recent(50),
    ])
      .then(([s, p, m, r]) => {
        setSummary(s.data);
        setByProvider(p.data);
        setByModel(m.data);
        setRecent(r.data);
      })
      .catch((e) => console.error('usage load failed', e))
      .finally(() => setLoading(false));
  }, [range]);

  if (loading || !summary) return <div style={{ padding: 24 }}>加载中…</div>;

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">使用统计</h1>
        <div style={{ display: 'flex', gap: 4 }}>
          {ranges.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              style={{
                padding: '4px 12px',
                fontSize: 12,
                borderRadius: 4,
                background: range === r ? 'var(--accent)' : 'transparent',
                color: range === r ? '#fff' : 'var(--text-secondary)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 12,
        }}
      >
        {[
          { label: '总请求', value: summary.total_requests.toLocaleString() },
          { label: '总 Tokens', value: summary.total_tokens.toLocaleString() },
          { label: '平均延迟', value: `${summary.avg_latency_ms}ms` },
          {
            label: '成功率',
            value: `${(summary.success_rate * 100).toFixed(1)}%`,
            color:
              summary.success_rate >= 0.9
                ? '#22c55e'
                : summary.success_rate >= 0.5
                  ? '#f59e0b'
                  : '#ef4444',
          },
        ].map((c) => (
          <div
            key={c.label}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              padding: 16,
            }}
          >
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{c.label}</div>
            <div style={{ fontSize: 22, fontWeight: 600, color: c.color ?? 'var(--text-primary)' }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>按供应商</h2>
        <TableStyle>
          <thead>
            <tr>
              <Th>供应商</Th>
              <ThR>请求</ThR>
              <ThR>Tokens</ThR>
              <ThR>平均延迟</ThR>
              <ThR>成功率</ThR>
            </tr>
          </thead>
          <tbody>
            {byProvider.length === 0 ? (
              <tr>
                <Td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
                  暂无数据
                </Td>
              </tr>
            ) : (
              byProvider.map((p) => (
                <tr key={p.provider_id}>
                  <Td>{p.provider_id}</Td>
                  <TdR>{p.requests}</TdR>
                  <TdR>{p.total_tokens.toLocaleString()}</TdR>
                  <TdR>{p.avg_latency_ms}ms</TdR>
                  <TdR>{(p.success_rate * 100).toFixed(1)}%</TdR>
                </tr>
              ))
            )}
          </tbody>
        </TableStyle>
      </section>

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>按模型</h2>
        <TableStyle>
          <thead>
            <tr>
              <Th>模型</Th>
              <ThR>请求</ThR>
              <ThR>输入 Tokens</ThR>
              <ThR>输出 Tokens</ThR>
              <ThR>平均延迟</ThR>
            </tr>
          </thead>
          <tbody>
            {byModel.length === 0 ? (
              <tr>
                <Td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
                  暂无数据
                </Td>
              </tr>
            ) : (
              byModel.map((m) => (
                <tr key={m.model_id}>
                  <Td style={{ fontFamily: 'monospace' }}>{m.model_id}</Td>
                  <TdR>{m.requests}</TdR>
                  <TdR>{m.input_tokens.toLocaleString()}</TdR>
                  <TdR>{m.output_tokens.toLocaleString()}</TdR>
                  <TdR>{m.avg_latency_ms}ms</TdR>
                </tr>
              ))
            )}
          </tbody>
        </TableStyle>
      </section>

      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>最近 50 条调用</h2>
        <TableStyle>
          <thead>
            <tr>
              <Th>时间</Th>
              <Th>供应商</Th>
              <Th>模型</Th>
              <ThR>Tokens</ThR>
              <ThR>延迟</ThR>
              <Th>状态</Th>
              <Th>故障转移</Th>
            </tr>
          </thead>
          <tbody>
            {recent.length === 0 ? (
              <tr>
                <Td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
                  暂无数据
                </Td>
              </tr>
            ) : (
              recent.map((r) => (
                <tr key={r.id}>
                  <Td style={{ fontSize: 11 }}>{r.created_at}</Td>
                  <Td>{r.provider_id}</Td>
                  <Td style={{ fontFamily: 'monospace' }}>{r.model_id}</Td>
                  <TdR>{r.total_tokens}</TdR>
                  <TdR>{r.latency_ms}ms</TdR>
                  <Td>
                    <span style={{ color: r.is_success ? '#22c55e' : '#ef4444' }}>
                      {r.status_code}
                    </span>
                  </Td>
                  <Td>
                    {r.failover_attempt > 1
                      ? `从 ${r.failover_from_provider} (try #${r.failover_attempt})`
                      : '—'}
                  </Td>
                </tr>
              ))
            )}
          </tbody>
        </TableStyle>
      </section>
    </div>
  );
}

const TableStyle = ({ children }: { children: React.ReactNode }) => (
  <table
    style={{
      width: '100%',
      borderCollapse: 'collapse',
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      overflow: 'hidden',
    }}
  >
    {children}
  </table>
);
const Th = ({ children }: { children?: React.ReactNode }) => (
  <th
    style={{
      padding: '8px 12px',
      fontSize: 12,
      color: 'var(--text-tertiary)',
      textAlign: 'left',
      borderBottom: '1px solid var(--border)',
    }}
  >
    {children}
  </th>
);
const ThR = ({ children }: { children?: React.ReactNode }) => (
  <th
    style={{
      padding: '8px 12px',
      fontSize: 12,
      color: 'var(--text-tertiary)',
      textAlign: 'right',
      borderBottom: '1px solid var(--border)',
    }}
  >
    {children}
  </th>
);
const Td = ({
  children,
  style,
  colSpan,
}: {
  children?: React.ReactNode;
  style?: React.CSSProperties;
  colSpan?: number;
}) => (
  <td
    colSpan={colSpan}
    style={{
      padding: '6px 12px',
      fontSize: 12,
      color: 'var(--text-primary)',
      borderBottom: '1px solid var(--border)',
      ...style,
    }}
  >
    {children}
  </td>
);
const TdR = ({ children }: { children?: React.ReactNode }) => (
  <td
    style={{
      padding: '6px 12px',
      fontSize: 12,
      color: 'var(--text-primary)',
      textAlign: 'right',
      borderBottom: '1px solid var(--border)',
    }}
  >
    {children}
  </td>
);
