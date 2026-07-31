import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ModelServicePanel } from './ModelServicePanel';

vi.mock('../../api/admin/providers', () => ({
  providersApi: {
    list: vi.fn().mockResolvedValue({
      data: [
        {
          providerId: 'p1',
          name: 'P1',
          notes: 'first',
          apiHost: 'https://a',
          apiModel: 'm1',
          isEnabled: true,
          health: 'healthy',
        },
        {
          providerId: 'p2',
          name: 'P2',
          notes: 'second',
          apiHost: 'https://b',
          apiModel: 'm2',
          isEnabled: true,
          health: 'degraded',
        },
      ],
    }),
  },
}));

describe('ModelServicePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the catalog cards', async () => {
    render(
      <MemoryRouter>
        <ModelServicePanel />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('P1')).toBeInTheDocument();
      expect(screen.getByText('P2')).toBeInTheDocument();
    });
    expect(screen.getByText('first')).toBeInTheDocument();
    expect(screen.getByText('正常')).toBeInTheDocument();
    expect(screen.getByText('降级')).toBeInTheDocument();
  });

  it('renders the + add button', async () => {
    render(
      <MemoryRouter>
        <ModelServicePanel />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/\+ 添加/)).toBeInTheDocument();
    });
  });

  it('shows empty state when no providers', async () => {
    const { providersApi } = await import('../../api/admin/providers');
    (providersApi.list as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: [] });
    render(
      <MemoryRouter>
        <ModelServicePanel />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/还没有任何模型服务，点右上角"添加"创建第一条/)).toBeInTheDocument();
    });
  });
});
