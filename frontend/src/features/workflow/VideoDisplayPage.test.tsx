import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VideoDisplayPage from './VideoDisplayPage';

const mockOptions = {
  data: {
    providerId: 'minimax',
    providerName: 'MiniMax',
    protocol: 'video_minimax',
    model: 'MiniMax-H3',
    capabilities: {
      resolutions: ['768P', '2K'],
      duration: { min: 4, max: 15 },
      ratios: ['16:9', '4:3', '1:1'],
    },
  },
};

vi.mock('../../api/video', () => ({
  videoApi: {
    getOptions: vi.fn(),
    listTasks: vi.fn().mockResolvedValue({ data: [] }),
    generate: vi.fn(),
  },
}));

describe('VideoDisplayPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows options from capabilities', async () => {
    const { videoApi } = await import('../../api/video');
    vi.mocked(videoApi.getOptions).mockResolvedValue(mockOptions);

    render(<VideoDisplayPage />);
    await waitFor(() => {
      expect(screen.getByText('768P')).toBeInTheDocument();
      expect(screen.getByText('2K')).toBeInTheDocument();
    });
  });

  it('shows 403 message when no video provider', async () => {
    const { videoApi } = await import('../../api/video');
    vi.mocked(videoApi.getOptions).mockRejectedValue(new Error('未开通视频生成服务，请联系管理员'));

    render(<VideoDisplayPage />);
    await waitFor(() => {
      expect(screen.getByText(/未开通视频生成服务/)).toBeInTheDocument();
    });
  });

  it('hides generate form when 403', async () => {
    const { videoApi } = await import('../../api/video');
    vi.mocked(videoApi.getOptions).mockRejectedValue(new Error('未开通视频生成服务，请联系管理员'));

    render(<VideoDisplayPage />);
    await waitFor(() => {
      expect(screen.queryByPlaceholderText(/描述你想生成/)).not.toBeInTheDocument();
    });
  });

  it('submits generate with selected options', async () => {
    const { videoApi } = await import('../../api/video');
    vi.mocked(videoApi.getOptions).mockResolvedValue(mockOptions);
    vi.mocked(videoApi.generate).mockResolvedValue({ data: { taskId: 'task-1' } });

    render(<VideoDisplayPage />);
    await waitFor(() => {
      expect(screen.getByText('768P')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/描述你想生成/), {
      target: { value: '一只猫在跑步' },
    });
    // 三个下拉：分辨率 / 时长 / 宽高比，第一个是分辨率
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '2K' } });
    fireEvent.click(screen.getByText('生成视频'));

    await waitFor(() => {
      expect(videoApi.generate).toHaveBeenCalledWith({
        prompt: '一只猫在跑步',
        resolution: '2K',
        duration: 4,
        ratio: '16:9',
      });
    });
  });
});
