export interface Solution {
  id: string;
  taskId: string;
  title: string;
  description: string;
  principles: string[];
  confidenceScore: number;
  patentReferences: string[];
  rating: number;
}
