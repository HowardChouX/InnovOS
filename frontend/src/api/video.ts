// 视频生成 API 客户端（多供应商异步任务）。
//
// 端点契约（见 backend/app/api/video.py）：
// - GET    /api/video/options       → {data: VideoOptions}（当前用户已开通供应商能力）
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
  resolution: string;
  duration: number;
  ratio: string;
}

export interface VideoCapabilities {
  resolutions: string[];
  duration: { min: number; max: number };
  ratios: string[];
}

export interface VideoOptions {
  providerId: string;
  providerName: string;
  protocol: string;
  model: string;
  capabilities: VideoCapabilities;
}

interface Envelope<T> {
  data: T;
  message?: string;
  code: number;
}

export const videoApi = {
  getOptions(): Promise<Envelope<VideoOptions>> {
    return apiRequest('/api/video/options');
  },

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
