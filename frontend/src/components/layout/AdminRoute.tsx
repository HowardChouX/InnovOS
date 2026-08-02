import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';

export function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore();

  if (!user || !user.is_superuser) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
