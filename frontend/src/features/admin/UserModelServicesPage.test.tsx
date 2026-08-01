import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { UserModelServicesPage } from './UserModelServicesPage';
import { userModelServicesApi } from '../../api/admin/userModelServices';

vi.mock('../../api/admin/userModelServices', () => ({
  userModelServicesApi: {
    list: vi.fn().mockImplementation((_userId: number, capability: string = 'chat') => {
      if (capability === 'embedding') {
        return Promise.resolve({
          data: [
            {
              provider_id: 'ep1',
              capability: 'embedding',
              name: 'Embed One',
              api_host: 'https://embed-a',
              api_model: 'em1',
              failover_order: 1,
              is_enabled: true,
              is_healthy: true,
            },
          ],
        });
      }
      if (capability === 'rerank') {
        return Promise.resolve({
          data: [
            {
              provider_id: 'rp1',
              capability: 'rerank',
              name: 'Rerank One',
              api_host: 'https://rerank-a',
              api_model: 'rm1',
              failover_order: 1,
              is_enabled: true,
              is_healthy: true,
            },
          ],
        });
      }
      // default: chat
      return Promise.resolve({
        data: [
          {
            provider_id: 'p1',
            capability: 'chat',
            name: 'Provider One',
            api_host: 'https://a',
            api_model: 'm1',
            failover_order: 1,
            is_enabled: true,
            is_healthy: true,
          },
          {
            provider_id: 'p2',
            capability: 'chat',
            name: 'Provider Two',
            api_host: 'https://b',
            api_model: 'm2',
            failover_order: 2,
            is_enabled: true,
            is_healthy: true,
          },
        ],
      });
    }),
    listAvailable: vi.fn().mockImplementation((_userId: number, capability: string = 'chat') => {
      if (capability === 'embedding') {
        return Promise.resolve({
          data: [
            {
              provider_id: 'ep2',
              name: 'Embed Two (available)',
              api_host: 'https://embed-b',
              api_model: 'em2',
              already_enabled: false,
              is_healthy: true,
            },
          ],
        });
      }
      if (capability === 'rerank') {
        return Promise.resolve({
          data: [
            {
              provider_id: 'rp2',
              name: 'Rerank Two (available)',
              api_host: 'https://rerank-b',
              api_model: 'rm2',
              already_enabled: false,
              is_healthy: true,
            },
          ],
        });
      }
      // default: chat
      return Promise.resolve({
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
      });
    }),
    add: vi.fn().mockResolvedValue({ data: [] }),
    remove: vi.fn().mockResolvedValue(undefined),
    toggle: vi.fn().mockResolvedValue({ data: { is_enabled: true } }),
    reorder: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

describe('UserModelServicesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all 4 capability sections', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('文本模型')).toBeInTheDocument();
      expect(screen.getByText('嵌入模型')).toBeInTheDocument();
      expect(screen.getByText('重排模型')).toBeInTheDocument();
      expect(screen.getByText('图片/视频模型')).toBeInTheDocument();
    });
  });

  it('renders chat capability providers', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Provider One')).toBeInTheDocument();
      expect(screen.getByText('Provider Two')).toBeInTheDocument();
      expect(screen.getByText('Provider Three (not enabled)')).toBeInTheDocument();
    });
  });

  it('renders embedding capability providers', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Embed One')).toBeInTheDocument();
      expect(screen.getByText('Embed Two (available)')).toBeInTheDocument();
    });
  });

  it('renders rerank capability providers', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Rerank One')).toBeInTheDocument();
      expect(screen.getByText('Rerank Two (available)')).toBeInTheDocument();
    });
  });

  it('shows coming soon placeholder for image capability', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/图片生成、视频生成（即将支持）/)).toBeInTheDocument();
    });
  });

  it('shows priority markers across sections', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      // #1 appears in all 3 active sections (chat, embedding, rerank)
      expect(screen.getAllByText('#1').length).toBe(3);
      // #2 only appears in chat section (2 providers)
      expect(screen.getByText('#2')).toBeInTheDocument();
    });
  });

  it('calls list with correct capability for each active section', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/users/1/model-services']}>
        <Routes>
          <Route path="/admin/users/:userId/model-services" element={<UserModelServicesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('文本模型')).toBeInTheDocument();
    });
    expect(userModelServicesApi.list).toHaveBeenCalledWith(1, 'chat');
    expect(userModelServicesApi.list).toHaveBeenCalledWith(1, 'embedding');
    expect(userModelServicesApi.list).toHaveBeenCalledWith(1, 'rerank');
    // image capability is coming_soon, so list should not be called for it
    expect(userModelServicesApi.list).not.toHaveBeenCalledWith(1, 'image');
  });
});
