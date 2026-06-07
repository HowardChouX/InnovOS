export interface Evaluation {
  id: string;
  solutionId: string;
  dimension: string;
  score: number;
  details: Record<string, unknown>;
  status: string;
  createdAt: string;
  // 智枢评估维度
  rootCauseCut: boolean;
  originalContradictionResolved: boolean;
  newContradictions: string[];
  functionDeficitsFilled: string[];
  newHarmfulInteractions: string[];
  ifrDistance: string;
  ifrGapDescription: string;
  ifrParametersAchieved: string[];
  overallVerdict: string;
  evolutionAlignment: number;
  alignedLaws: string[];
  misalignedLaws: string[];
  maturity: string;
  confidence: number | null;
}

export interface EvaluationSummary {
  id: string;
  solutionId: string;
  score: number;
  dimension: string;
  status: string;
  evaluatedAt: string;
  overallVerdict: string;
  maturity: string;
  confidence: number | null;
}
