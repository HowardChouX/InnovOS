import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';

vi.mock('../../../api/auth', () => ({
  authApi: {
    register: vi.fn().mockResolvedValue({ id: 1, phone: '13800000000' }),
  },
}));

import { RegisterPage } from '../RegisterPage';

test('注册成功跳 /verify-phone', async () => {
  render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-phone" element={<div>VERIFY</div>} />
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByPlaceholderText('11 位手机号'), {
    target: { value: '13800000000' },
  });
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
    target: { value: 'a@b.com' },
  });
  fireEvent.change(screen.getByPlaceholderText('至少 8 个字符'), {
    target: { value: 'password123' },
  });
  fireEvent.change(screen.getByPlaceholderText('再次输入密码'), {
    target: { value: 'password123' },
  });
  fireEvent.click(screen.getByRole('button', { name: '注册' }));
  await waitFor(() => expect(screen.getByText('VERIFY')).toBeInTheDocument());
});
