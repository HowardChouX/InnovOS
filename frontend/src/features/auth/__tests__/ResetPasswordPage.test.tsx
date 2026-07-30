import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../../../api/auth', () => ({
  authApi: { setNewPassword: vi.fn() },
}));

import { authApi } from '../../../api/auth';
import { ResetPasswordPage } from '../ResetPasswordPage';

describe('ResetPasswordPage', () => {
  it('redirects to /forgot-password if state is missing', () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/reset-password' }]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('FORGOT')).toBeInTheDocument();
  });

  it('submits setNewPassword with state.reset_token + new_password', async () => {
    (authApi.setNewPassword as any).mockResolvedValue({ reset: true });
    render(
      <MemoryRouter initialEntries={[{
        pathname: '/reset-password',
        state: { email: 'a@b.com', reset_token: 'jwt-xxx' },
      }]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<div>LOGIN</div>} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>
    );
    const inputs = screen.getAllByPlaceholderText(/至少 8 个字符|再次输入/);
    fireEvent.change(inputs[0], { target: { value: 'newpass1234' } });
    fireEvent.change(inputs[1], { target: { value: 'newpass1234' } });
    fireEvent.click(screen.getByRole('button', { name: /重置密码/ }));
    await waitFor(() => {
      expect(authApi.setNewPassword).toHaveBeenCalledWith('jwt-xxx', 'newpass1234');
    });
  });
});
