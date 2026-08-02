import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';

const loginMock = vi.fn();
vi.mock('../../../store/useAuthStore', () => ({
  useAuthStore: (selector: (s: { login: typeof loginMock }) => unknown) =>
    selector({ login: loginMock }),
}));

import { LoginPage } from '../LoginPage';

test('未验证用户登录 → 跳 /verify-phone', async () => {
  loginMock.mockRejectedValueOnce(
    Object.assign(new Error('账号未验证，请先完成手机验证'), {
      code: 'LOGIN_USER_NOT_VERIFIED',
    }),
  );
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/verify-phone" element={<div>VERIFY_PAGE</div>} />
        <Route path="/" element={<div>HOME</div>} />
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByPlaceholderText('11 位手机号'), {
    target: { value: '13800000000' },
  });
  fireEvent.change(screen.getByPlaceholderText('输入密码'), {
    target: { value: 'password123' },
  });
  fireEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() => expect(screen.getByText('VERIFY_PAGE')).toBeInTheDocument());
});
