import { AppLayout } from '../components/layout/AppLayout';
import { ProtectedRoute } from '../components/layout/ProtectedRoute';
import { DashboardPage } from '../features/dashboard/DashboardPage';

import { LoginPage } from '../features/auth/LoginPage';
import { RegisterPage } from '../features/auth/RegisterPage';
import { PlaceholderPage } from '../features/PlaceholderPage';

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
      { path: 'tasks', element: <PlaceholderPage title="创新任务" /> },
      { path: 'analysis', element: <PlaceholderPage title="问题分析" /> },
      { path: 'patents', element: <PlaceholderPage title="专利检索" /> },
      { path: 'solutions', element: <PlaceholderPage title="方案生成" /> },
      { path: 'evaluation', element: <PlaceholderPage title="方案评估" /> },
      { path: 'results', element: <PlaceholderPage title="成果管理" /> },
      { path: 'knowledge', element: <PlaceholderPage title="知识库管理" /> },
      { path: 'settings', element: <PlaceholderPage title="系统设置" /> },
    ],
  },
];
