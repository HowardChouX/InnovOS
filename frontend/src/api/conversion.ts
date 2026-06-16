import { apiRequest } from './client';

export interface PatentInfo {
  id?: number;
  title?: string;
  _title?: string;
  abstract?: string;
  description?: string;
  patent_number?: string;
  applicants?: string;
  relevance?: number;
}

export interface SolutionWithEval {
  id: string;
  title: string;
  description: string;
  principles: string[];
  confidenceScore: number;
  patentReferences: string[];
  refPatents: PatentInfo[];
  rating: number;
  evaluation: Record<string, number>;
}

export interface ConversionData {
  taskId: string;
  taskTitle: string;
  taskDescription: string;
  solutions: SolutionWithEval[];
}

export interface InfringementResult {
  riskLevel: string;
  riskScore: number;
  analysisSummary: string;
  claimOverlaps: Array<{
    feature: string;
    patentClaim: string;
    risk: string;
    suggestion: string;
  }>;
  designArounds: string[];
  keyRecommendations: string[];
}

export const conversionApi = {
  async getData(taskId: string): Promise<ConversionData> {
    const res = await apiRequest<{ data: ConversionData }>(`/api/conversion/${taskId}`);
    return res.data;
  },

  async checkInfringement(solutionId: string): Promise<InfringementResult> {
    const res = await apiRequest<{ data: InfringementResult }>(
      `/api/conversion/${solutionId}/check-infringement`,
      { method: 'POST' },
    );
    return res.data;
  },
};
