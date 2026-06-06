import { AppLayout } from '../components/layout/AppLayout';
import { ProtectedRoute } from '../components/layout/ProtectedRoute';
import { DashboardPage } from '../features/dashboard/DashboardPage';

import { LoginPage } from '../features/auth/LoginPage';
import { RegisterPage } from '../features/auth/RegisterPage';
import { PlaceholderPage } from '../features/PlaceholderPage';
import { PatentSearchPage } from '../features/patents/PatentSearchPage';
import { KnowledgeBasePage } from '../features/knowledge/KnowledgeBasePage';
import { KeyManagementPage } from '../features/admin/KeyManagementPage';
import { UserManagementPage } from '../features/admin/UserManagementPage';
import { MonitorPage } from '../features/monitor/MonitorPage';

export const routes = [
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'patents', element: <PatentSearchPage /> },
      { path: 'solutions', element: <PlaceholderPage title="方案生成" /> },
      { path: 'evaluation', element: <PlaceholderPage title="方案评估" /> },
      { path: 'results', element: <PlaceholderPage title="成果管理" /> },
      { path: 'knowledge', element: <KnowledgeBasePage /> },
      { path: 'monitor', element: <MonitorPage /> },
      { path: 'admin/keys', element: <KeyManagementPage /> },
      { path: 'admin/users', element: <UserManagementPage /> },
    ],
  },
];
