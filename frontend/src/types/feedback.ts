export interface Feedback {
  id: string;
  solutionId: string;
  rating: number;
  feedbackType: string;
  comments: string;
  createdAt: string;
}

export interface FeedbackCreate {
  solution_id: number;
  rating: number;
  feedback_type?: string;
  comments?: string;
}
