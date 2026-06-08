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
      { path: 'knowledge', element: <KnowledgeBasePage /> },
      { path: 'monitor', element: <MonitorPage /> },
      { path: 'history', element: <PlaceholderPage title="历史方案" /> },
      { path: 'patent-conversion', element: <PlaceholderPage title="专利转化" /> },
      { path: 'workflow/demand', element: <PlaceholderPage title="需求画像" /> },
      { path: 'workflow/modeling', element: <PlaceholderPage title="问题建模" /> },
      { path: 'admin/keys', element: <KeyManagementPage /> },
      { path: 'admin/users', element: <UserManagementPage /> },
    ],
  },
];
