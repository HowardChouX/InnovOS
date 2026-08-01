import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('../../../api/auth', () => ({
  authApi: { requestPasswordResetSms: vi.fn() },
}));

import { VerifyResetOtpPage } from '../VerifyResetOtpPage';

describe('VerifyResetOtpPage', () => {
  it('redirects to /forgot-password if phone is missing in location state', () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/verify-reset' }]}>
        <Routes>
          <Route path="/verify-reset" element={<VerifyResetOtpPage />} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('FORGOT')).toBeInTheDocument();
  });

  it('navigates to /reset-password carrying phone + code after 6 digits entered', async () => {
    render(
      <MemoryRouter
        initialEntries={[{ pathname: '/verify-reset', state: { phone: '13800000000' } }]}
      >
        <Routes>
          <Route path="/verify-reset" element={<VerifyResetOtpPage />} />
          <Route path="/reset-password" element={<div>RESET_PAGE</div>} />
          <Route path="/forgot-password" element={<div>FORGOT</div>} />
        </Routes>
      </MemoryRouter>,
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
