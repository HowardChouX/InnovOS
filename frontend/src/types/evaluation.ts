export interface Evaluation {
  id: string;
  solutionId: string;
  dimension: string;
  score: number;
  details: Record<string, unknown>;
  status: string;
  createdAt: string;
}

export interface EvaluationSummary {
  id: string;
  solutionId: string;
  score: number;
  dimension: string;
  status: string;
  evaluatedAt: string;
}
