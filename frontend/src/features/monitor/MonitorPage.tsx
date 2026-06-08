import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMonitorStore } from '../../store/useMonitorStore';
import { useAuthStore } from '../../store/useAuthStore';
import { OverviewCards } from './OverviewCards';
import { TaskStatsChart } from './TaskStatsChart';
import { KeyUsageChart } from './KeyUsageChart';
import { SystemStatus } from './SystemStatus';
import { HealthCheckPanel } from './HealthCheckPanel';

export function MonitorPage() {
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const navigate = useNavigate();
  const { loading, error, fetchAll, fetchKeyStats, fetchSystemStatus, fetchHealth } = useMonitorStore();

  const loadAll = () => {
    fetchAll();
    fetchKeyStats();
    fetchSystemStatus();
    fetchHealth();
  };

  useEffect(() => {
    if (!isAdmin) {
      navigate('/', { replace: true });
      return;
    }
    loadAll();
  }, [isAdmin, navigate]);

  if (!isAdmin) return null;

  if (error && !loading) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: 60, color: 'var(--text-tertiary)',
      }}>
        <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: 32, marginBottom: 12, color: 'var(--accent-red)' }} />
        <div style={{ fontSize: 13, marginBottom: 16 }}>{error}</div>
        <button onClick={loadAll} style={{
          padding: '8px 20px', borderRadius: 6, fontSize: 13,
          background: 'var(--accent)', border: 'none', color: '#fff',
          cursor: 'pointer', fontFamily: 'inherit',
        }}>重试</button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <OverviewCards />
      <TaskStatsChart />
      <KeyUsageChart />
      <SystemStatus />
      <HealthCheckPanel />
    </div>
  );
}
