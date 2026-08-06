import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ModelServiceForm } from './ModelServiceForm';

vi.mock('../../api/admin/providers', () => ({
  providersApi: {
    detect: vi.fn().mockResolvedValue({
      data: { models: [{ id: 'gpt-4o-mini', name: 'gpt-4o-mini' }] },
    }),
    add: vi.fn().mockResolvedValue({ data: {} }),
    update: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

describe('ModelServiceForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders add mode with 5 fields', () => {
    render(<ModelServiceForm open mode="add" onClose={() => {}} onSave={() => {}} />);
    expect(screen.getByPlaceholderText('例如 my-deepseek')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('https://api.example.com/v1')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('sk-...')).toBeInTheDocument();
    expect(screen.getByText('添加模型服务')).toBeInTheDocument();
  });

  it('shows validation error when required fields missing', async () => {
    const onSave = vi.fn();
    render(<ModelServiceForm open mode="add" onClose={() => {}} onSave={onSave} />);
    // Click 保存 without filling fields
    fireEvent.click(screen.getByText('保存'));
    await waitFor(() => {
      expect(screen.getByText(/供应商 ID、名称、API 地址、API Key 都是必填/)).toBeInTheDocument();
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  it('calls detect endpoint and populates detected models', async () => {
    const { providersApi } = await import('../../api/admin/providers');
    render(<ModelServiceForm open mode="add" onClose={() => {}} onSave={() => {}} />);

    fireEvent.change(screen.getByPlaceholderText('https://api.example.com/v1'), {
      target: { value: 'https://api.example.com/v1' },
    });
    fireEvent.change(screen.getByPlaceholderText('sk-...'), {
      target: { value: 'sk-test-key' },
    });

    fireEvent.click(screen.getByText('检测模型'));

    await waitFor(() => {
      expect(providersApi.detect).toHaveBeenCalledWith('https://api.example.com/v1', 'sk-test-key');
    });
  });

  it('renders protocol dropdown with video options', () => {
    render(<ModelServiceForm open mode="add" onClose={() => {}} onSave={() => {}} />);
    expect(screen.getByText('openai（文本/通用）')).toBeInTheDocument();
    expect(screen.getByText('video_minimax（MiniMax 视频）')).toBeInTheDocument();
    expect(screen.getByText('video_dashscope（百炼 Wan 视频）')).toBeInTheDocument();
  });

  it('submits protocol with add request', async () => {
    const { providersApi } = await import('../../api/admin/providers');
    render(<ModelServiceForm open mode="add" onClose={() => {}} onSave={() => {}} />);

    fireEvent.change(screen.getByPlaceholderText('例如 my-deepseek'), {
      target: { value: 'my-video' },
    });
    fireEvent.change(screen.getByPlaceholderText('DeepSeek (生产)'), {
      target: { value: 'My Video' },
    });
    fireEvent.change(screen.getByPlaceholderText('https://api.example.com/v1'), {
      target: { value: 'https://api.test.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('sk-...'), { target: { value: 'sk-test' } });

    // 选择 video_minimax
    fireEvent.change(screen.getByRole('combobox', { name: '协议' }), {
      target: { value: 'video_minimax' },
    });

    fireEvent.click(screen.getByText('保存'));
    await waitFor(() => {
      expect(providersApi.add).toHaveBeenCalledWith(
        expect.objectContaining({ protocol: 'video_minimax' }),
      );
    });
  });
});
