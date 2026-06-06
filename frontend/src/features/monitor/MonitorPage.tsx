import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMonitorStore } from '../../store/useMonitorStore';
import { useAuthStore } from '../../store/useAuthStore';
import { OverviewCards } from './OverviewCards';
import { TaskStatsChart } from './TaskStatsChart';
import { KeyUsageChart } from './KeyUsageChart';
import { SystemStatus } from './SystemStatus';

export function MonitorPage() {
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const navigate = useNavigate();
  const fetchAll = useMonitorStore((s) => s.fetchAll);
  const fetchKeyStats = useMonitorStore((s) => s.fetchKeyStats);
  const fetchSystemStatus = useMonitorStore((s) => s.fetchSystemStatus);

  useEffect(() => {
    if (!isAdmin) {
      navigate('/', { replace: true });
      return;
    }
    fetchAll();
    fetchKeyStats();
    fetchSystemStatus();
  }, [isAdmin, navigate, fetchAll, fetchKeyStats, fetchSystemStatus]);

  if (!isAdmin) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <OverviewCards />
      <TaskStatsChart />
      <KeyUsageChart />
      <SystemStatus />
    </div>
  );
}
