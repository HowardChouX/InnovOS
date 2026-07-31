import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { UserModelServicesPage } from './UserModelServicesPage';

vi.mock('../../api/admin/userModelServices', () => ({
  userModelServicesApi: {
    list: vi.fn().mockResolvedValue({
      data: [
        {
          provider_id: 'p1',
          name: 'Provider One',
          api_host: 'https://a',
          api_model: 'm1',
          failover_order: 1,
          is_enabled: true,
          is_healthy: true,
        },
        {
          provider_id: 'p2',
          name: 'Provider Two',
          api_host: 'https://b',
          api_model: 'm2',
          failover_order: 2,
          is_enabled: true,
          is_healthy: true,
        },
      ],
    }),
    listAvailable: vi.fn().mockResolvedValue({
      data: [
        {
          provider_id: 'p3',
          name: 'Provider Three (not enabled)',
          api_host: 'https://c',
          api_model: 'm3',
          already_enabled: false,
          is_healthy: true,
        },
      ],
    }),
    remove: vi.fn().mockResolvedValue(undefined),
    toggle: vi.fn().mockResolvedValue({ data: { is_enabled: true } }),
    reorder: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

describe('UserModelServicesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders enabled and not-enabled sections', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/已开通/)).toBeInTheDocument();
    });
    expect(screen.getByText('Provider One')).toBeInTheDocument();
    expect(screen.getByText('Provider Two')).toBeInTheDocument();
    expect(screen.getByText('Provider Three (not enabled)')).toBeInTheDocument();
  });

  it('shows #1 and #2 priority markers', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
      expect(screen.getByText('#2')).toBeInTheDocument();
    });
  });
});
