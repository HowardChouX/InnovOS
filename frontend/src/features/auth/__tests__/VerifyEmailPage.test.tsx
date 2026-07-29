import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';

const verifyMock = vi.fn();
vi.mock('../../../api/auth', () => ({
  authApi: {
    verifyEmailOtp: (...args: unknown[]) => verifyMock(...args),
    resendEmailOtp: vi.fn().mockResolvedValue({ expires_in: 600, next_resend_in: 60 }),
  },
}));

import { VerifyEmailPage } from '../VerifyEmailPage';

test('满 6 位自动 verify 并跳 /login', async () => {
  render(
    <MemoryRouter initialEntries={['/verify-email?email=a@b.com']}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>
  );
  verifyMock.mockResolvedValue({ verified: true });
  const inputs = screen.getAllByLabelText(/验证码第/);
  for (let i = 0; i < 6; i++) {
    fireEvent.change(inputs[i], { target: { value: String(i + 1) } });
  }
  await waitFor(() => expect(verifyMock).toHaveBeenCalledWith('a@b.com', '123456'));
  await waitFor(() => expect(screen.getByText('LOGIN')).toBeInTheDocument());
});

test('错误时回到首位并显示提示', async () => {
  render(
    <MemoryRouter initialEntries={['/verify-email?email=a@b.com']}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/login" element={<div>LOGIN</div>} />
      </Routes>
    </MemoryRouter>
  );
  verifyMock.mockRejectedValue(new Error('验证码错误（剩余 4 次）'));
  const inputs = screen.getAllByLabelText(/验证码第/);
  for (let i = 0; i < 6; i++) fireEvent.change(inputs[i], { target: { value: '0' } });
  await waitFor(() => expect(screen.getByText(/验证码错误/)).toBeInTheDocument());
});
