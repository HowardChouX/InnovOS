import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../../../api/auth', () => ({
  authApi: { verifyPasswordResetOtp: vi.fn(), requestPasswordResetOtp: vi.fn() },
}));

import { authApi } from '../../../api/auth';
import { VerifyResetOtpPage } from '../VerifyResetOtpPage';

describe('VerifyResetOtpPage', () => {
  it('redirects to /forgot-password if email is missing in location state', () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/verify-reset' }]}>
        <Routes>
          <Route path="/verify-reset" element={<VerifyResetOtpPage />} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('FORGOT')).toBeInTheDocument();
  });

  it('navigates to /reset-password with state after successful verify', async () => {
    (authApi.verifyPasswordResetOtp as any).mockResolvedValue({
      verified: true, reset_token: 'jwt-xxx',
    });
    render(
      <MemoryRouter initialEntries={[{ pathname: '/verify-reset', state: { email: 'a@b.com' } }]}>
        <Routes>
          <Route path="/verify-reset" element={<VerifyResetOtpPage />} />
          <Route path="/reset-password" element={<div>RESET_PAGE</div>} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>
    );
    const inputs = screen.getAllByRole('textbox');
    inputs.forEach((input, i) => {
      fireEvent.change(input, { target: { value: String(i + 1) } });
    });
    await waitFor(() => {
      expect(screen.getByText('RESET_PAGE')).toBeInTheDocument();
    });
  });
});
