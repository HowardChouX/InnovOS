import type { RouteObject } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { ProtectedRoute } from '../components/layout/ProtectedRoute';
import { AdminRoute } from '../components/layout/AdminRoute';
import { lazyPage } from '../components/common/LazyPage';

const DashboardPage = lazyPage(() => import('../features/dashboard/DashboardPage'));
const LoginPage = lazyPage(() => import('../features/auth/LoginPage'));
const RegisterPage = lazyPage(() => import('../features/auth/RegisterPage'));
const PlaceholderPage = lazyPage(() => import('../features/PlaceholderPage'));
const PatentSearchPage = lazyPage(() => import('../features/patents/PatentSearchPage'));
const KnowledgeBasePage = lazyPage(() => import('../features/knowledge/KnowledgeBasePage'));
const KeyManagementPage = lazyPage(() => import('../features/admin/KeyManagementPage'));
const UserManagementPage = lazyPage(() => import('../features/admin/UserManagementPage'));
const PatentDbPage = lazyPage(() => import('../features/admin/PatentDbPage'));
const PatentConversionPage = lazyPage(
  () => import('../features/patent_conversion/PatentConversionPage'),
);
const GuidePage = lazyPage(() => import('../features/guide/GuidePage'));
const ProfilePage = lazyPage(() => import('../features/profile/ProfilePage'));
const NotFoundPage = lazyPage(() => import('../features/NotFoundPage'));

export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  {
    path: '/',
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: 'patents', element: <PatentSearchPage /> },
          { path: 'knowledge', element: <KnowledgeBasePage /> },
          { path: 'history', element: <PatentConversionPage /> },
          { path: 'history-solutions', element: <PatentConversionPage /> },
          { path: 'workflow/demand', element: <PlaceholderPage title="需求画像" /> },
          { path: 'workflow/modeling', element: <PlaceholderPage title="问题建模" /> },
          { path: 'guide', element: <GuidePage /> },
          { path: 'profile', element: <ProfilePage /> },
          {
            path: 'admin/keys',
            element: (
              <AdminRoute>
                <KeyManagementPage />
              </AdminRoute>
            ),
          },
          {
            path: 'admin/users',
            element: (
              <AdminRoute>
                <UserManagementPage />
              </AdminRoute>
            ),
          },
          {
            path: 'admin/patents',
            element: (
              <AdminRoute>
                <PatentDbPage />
              </AdminRoute>
            ),
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
];
