import { create } from 'zustand';
import type { Feedback, FeedbackCreate } from '../types/feedback';
import { feedbackApi } from '../api/feedback';

interface FeedbackStore {
  feedbacks: Feedback[];
  loading: boolean;
  error: string | null;
  submitFeedback: (body: FeedbackCreate) => Promise<void>;
  fetchFeedbacks: (solutionId: string) => Promise<void>;
}

export const useFeedbackStore = create<FeedbackStore>((set) => ({
  feedbacks: [],
  loading: false,
  error: null,
  submitFeedback: async (body) => {
    set({ loading: true });
    try {
      await feedbackApi.create(body);
      const feedbacks = await feedbackApi.getBySolution(String(body.solution_id));
      set({ feedbacks, loading: false });
    } catch (e) {
      console.error('[useFeedbackStore] submitFeedback failed:', e);
      set({ loading: false, error: e instanceof Error ? e.message : '提交反馈失败' });
    }
  },
  fetchFeedbacks: async (solutionId) => {
    set({ loading: true });
    try {
      const feedbacks = await feedbackApi.getBySolution(solutionId);
      set({ feedbacks, loading: false });
    } catch (e) {
      console.error('[useFeedbackStore] fetchFeedbacks failed:', e);
      set({ loading: false, error: e instanceof Error ? e.message : '获取反馈列表失败' });
    }
  },
}));
