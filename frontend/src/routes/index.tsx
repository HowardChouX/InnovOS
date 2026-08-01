import type { RouteObject } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { ProtectedRoute } from '../components/layout/ProtectedRoute';
import { AdminRoute } from '../components/layout/AdminRoute';
import { lazyPage } from '../components/common/LazyPage';

const DashboardPage = lazyPage(() => import('../features/dashboard/DashboardPage'));
const LoginPage = lazyPage(() => import('../features/auth/LoginPage'));
const RegisterPage = lazyPage(() => import('../features/auth/RegisterPage'));
const VerifyPhonePage = lazyPage(() => import('../features/auth/VerifyPhonePage'));
const ForgotPasswordPage = lazyPage(() => import('../features/auth/ForgotPasswordPage'));
const VerifyResetOtpPage = lazyPage(() => import('../features/auth/VerifyResetOtpPage'));
const ResetPasswordPage = lazyPage(() => import('../features/auth/ResetPasswordPage'));
const PlaceholderPage = lazyPage(() => import('../features/PlaceholderPage'));
void PlaceholderPage;
const PatentSearchPage = lazyPage(() => import('../features/patents/PatentSearchPage'));
const KnowledgeBasePage = lazyPage(() => import('../features/knowledge/KnowledgeBasePage'));
const KeyManagementPage = lazyPage(() => import('../features/admin/KeyManagementPage'));
const UsageStatsPage = lazyPage(() => import('../features/admin/UsageStatsPage'));
const UserModelServicesPage = lazyPage(() => import('../features/admin/UserModelServicesPage'));
const UserManagementPage = lazyPage(() => import('../features/admin/UserManagementPage'));
const PatentDbPage = lazyPage(() => import('../features/admin/PatentDbPage'));
const PatentConversionPage = lazyPage(
  () => import('../features/patent_conversion/PatentConversionPage'),
);
const GuidePage = lazyPage(() => import('../features/guide/GuidePage'));
const ProfilePage = lazyPage(() => import('../features/profile/ProfilePage'));
const NotFoundPage = lazyPage(() => import('../features/NotFoundPage'));
const DemandMockPage = lazyPage(() => import('../features/workflow/DemandMockPage'));
const ProblemDefinitionMockPage = lazyPage(
  () => import('../features/workflow/ProblemDefinitionMockPage'),
);
const SolutionMockPage = lazyPage(() => import('../features/workflow/SolutionMockPage'));
const EvaluationMockPage = lazyPage(() => import('../features/workflow/EvaluationMockPage'));
const VideoDisplayMockPage = lazyPage(() => import('../features/workflow/VideoDisplayMockPage'));

export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/verify-phone', element: <VerifyPhonePage /> },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/verify-reset', element: <VerifyResetOtpPage /> },
  { path: '/reset-password', element: <ResetPasswordPage /> },
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
          { path: 'workflow/demand', element: <DemandMockPage /> },
          { path: 'workflow/problem', element: <ProblemDefinitionMockPage /> },
          { path: 'workflow/modeling', element: <ProblemDefinitionMockPage /> },
          { path: 'workflow/solution', element: <SolutionMockPage /> },
          { path: 'workflow/evaluation', element: <EvaluationMockPage /> },
          { path: 'workflow/video', element: <VideoDisplayMockPage /> },
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
            path: 'admin/users/:userId/model-services',
            element: (
              <AdminRoute>
                <UserModelServicesPage />
              </AdminRoute>
            ),
          },
          {
            path: 'admin/usage',
            element: (
              <AdminRoute>
                <UsageStatsPage />
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
