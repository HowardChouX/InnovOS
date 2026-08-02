import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('videoApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('generate posts prompt + params to /api/video/generate', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ data: { taskId: 't1' }, code: 200 })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { videoApi } = await import('../video');
    const res = await videoApi.generate({
      prompt: '一只猫',
      resolution: '768P',
      duration: 5,
      ratio: '16:9',
    });

    expect(res.data.taskId).toBe('t1');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/video/generate'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          prompt: '一只猫',
          resolution: '768P',
          duration: 5,
          ratio: '16:9',
        }),
      }),
    );
  });

  it('listTasks calls GET /api/video/tasks', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: () =>
        Promise.resolve(JSON.stringify({ data: [{ id: 't1', status: 'succeeded' }], code: 200 })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { videoApi } = await import('../video');
    const res = await videoApi.listTasks();

    expect(res.data[0].id).toBe('t1');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/video/tasks'),
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('deleteTask calls DELETE /api/video/tasks/{id}', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ code: 200 })),
    });
    vi.stubGlobal('fetch', mockFetch);

    const { videoApi } = await import('../video');
    await videoApi.deleteTask('t1');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/video/tasks/t1'),
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});
