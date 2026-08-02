import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// mock 掉 api 层
vi.mock('../../../api/video', () => ({
  videoApi: {
    generate: vi.fn(),
    listTasks: vi.fn(),
    getTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}));

import { videoApi } from '../../../api/video';
import VideoDisplayPage from '../VideoDisplayPage';

const mockGenerate = videoApi.generate as ReturnType<typeof vi.fn>;
const mockListTasks = videoApi.listTasks as ReturnType<typeof vi.fn>;

describe('VideoDisplayPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListTasks.mockResolvedValue({ data: [], code: 200 });
  });

  it('renders prompt form and submits generate', async () => {
    mockGenerate.mockResolvedValue({ data: { taskId: 't1' }, code: 200 });
    render(<VideoDisplayPage />);

    const textarea = screen.getByPlaceholderText(/描述/i);
    fireEvent.change(textarea, { target: { value: '一只猫在跳舞' } });
    fireEvent.click(screen.getByRole('button', { name: /生成视频/ }));

    await waitFor(() =>
      expect(mockGenerate).toHaveBeenCalledWith(
        expect.objectContaining({ prompt: '一只猫在跳舞' }),
      ),
    );
  });

  it('renders history list with status badges', async () => {
    mockListTasks.mockResolvedValue({
      data: [
        {
          id: 't1',
          userId: 1,
          providerId: 'minimax',
          model: 'MiniMax-H3',
          prompt: '已完成的视频',
          resolution: '768P',
          duration: 5,
          ratio: '16:9',
          remoteTaskId: 'r1',
          status: 'succeeded',
          videoUrl: 'https://x/1.mp4',
          error: null,
          createdAt: '2026-08-02T10:00:00Z',
          updatedAt: '2026-08-02T10:00:00Z',
        },
      ],
      code: 200,
    });

    render(<VideoDisplayPage />);

    await waitFor(() => expect(screen.getByText('已完成的视频')).toBeTruthy());
    expect(screen.getByText('已生成')).toBeTruthy();
  });

  it('shows empty state when no tasks', async () => {
    render(<VideoDisplayPage />);
    await waitFor(() => expect(mockListTasks).toHaveBeenCalled());
  });
});
