// 视频生成 API 客户端（MiniMax 文生视频，异步任务）。
//
// 端点契约（见 backend/app/api/video.py）：
// - POST   /api/video/generate      {prompt, resolution, duration, ratio} → {data:{taskId}}
// - GET    /api/video/tasks         → {data: VideoTask[]}
// - GET    /api/video/tasks/{id}    → {data: VideoTask}
// - DELETE /api/video/tasks/{id}    → {code}
import { apiRequest } from './client';

export type VideoStatus = 'pending' | 'queued' | 'running' | 'succeeded' | 'failed' | 'expired';

export interface VideoTask {
  id: string;
  userId: number;
  providerId: string;
  model: string;
  prompt: string;
  resolution: string;
  duration: number;
  ratio: string;
  remoteTaskId: string | null;
  status: VideoStatus;
  videoUrl: string | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GenerateInput {
  prompt: string;
  resolution: '768P' | '2K';
  duration: number;
  ratio: '21:9' | '16:9' | '4:3' | '1:1' | '3:4' | '9:16';
}

interface Envelope<T> {
  data: T;
  message?: string;
  code: number;
}

export const videoApi = {
  generate(input: GenerateInput): Promise<Envelope<{ taskId: string }>> {
    return apiRequest('/api/video/generate', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },

  listTasks(): Promise<Envelope<VideoTask[]>> {
    return apiRequest('/api/video/tasks');
  },

  getTask(id: string): Promise<Envelope<VideoTask>> {
    return apiRequest(`/api/video/tasks/${id}`);
  },

  deleteTask(id: string): Promise<Envelope<unknown>> {
    return apiRequest(`/api/video/tasks/${id}`, { method: 'DELETE' });
  },
};
