import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';

const loginMock = vi.fn();
vi.mock('../../../store/useAuthStore', () => ({
  useAuthStore: (selector: (s: { login: typeof loginMock }) => unknown) =>
    selector({ login: loginMock }),
}));

import { LoginPage } from '../LoginPage';

test('未验证用户登录 → 跳 /verify-email', async () => {
  loginMock.mockRejectedValueOnce(
    Object.assign(new Error('Request failed'), {
      detail: 'LOGIN_USER_NOT_VERIFIED',
    }),
  );
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/verify-email" element={<div>VERIFY_PAGE</div>} />
        <Route path="/" element={<div>HOME</div>} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
    target: { value: 'a@b.com' },
  });
  fireEvent.change(screen.getByPlaceholderText('输入密码'), {
    target: { value: 'password123' },
  });
  fireEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() => expect(screen.getByText('VERIFY_PAGE')).toBeInTheDocument());
});
