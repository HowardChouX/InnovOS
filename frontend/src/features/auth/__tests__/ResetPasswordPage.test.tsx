import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../../../api/auth', () => ({
  authApi: { resetPasswordWithSms: vi.fn() },
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
      </MemoryRouter>,
    );
    expect(screen.getByText('FORGOT')).toBeInTheDocument();
  });

  it('submits resetPasswordWithSms with state.phone + code + new_password', async () => {
    vi.mocked(authApi.resetPasswordWithSms).mockResolvedValue({ reset: true });
    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: '/reset-password',
            state: { phone: '13800000000', code: '123456' },
          },
        ]}
      >
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<div>LOGIN</div>} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>,
    );
    const inputs = screen.getAllByPlaceholderText(/至少 8 个字符|再次输入/);
    fireEvent.change(inputs[0], { target: { value: 'newpass1234' } });
    fireEvent.change(inputs[1], { target: { value: 'newpass1234' } });
    fireEvent.click(screen.getByRole('button', { name: /重置密码/ }));
    await waitFor(() => {
      expect(authApi.resetPasswordWithSms).toHaveBeenCalledWith(
        '13800000000',
        '123456',
        'newpass1234',
      );
    });
  });
});
