import { create } from 'zustand';
import type { Feedback, FeedbackCreate } from '../types/feedback';
import { feedbackApi } from '../api/feedback';

interface FeedbackStore {
  feedbacks: Feedback[];
  loading: boolean;
  submitFeedback: (body: FeedbackCreate) => Promise<void>;
  fetchFeedbacks: (solutionId: string) => Promise<void>;
}

export const useFeedbackStore = create<FeedbackStore>((set) => ({
  feedbacks: [],
  loading: false,
  submitFeedback: async (body) => {
    set({ loading: true });
    try {
      await feedbackApi.create(body);
      const feedbacks = await feedbackApi.getBySolution(String(body.solution_id));
      set({ feedbacks, loading: false });
    } catch {
      set({ loading: false });
    }
  },
  fetchFeedbacks: async (solutionId) => {
    set({ loading: true });
    try {
      const feedbacks = await feedbackApi.getBySolution(solutionId);
      set({ feedbacks, loading: false });
    } catch {
      set({ loading: false });
    }
  },
}));
