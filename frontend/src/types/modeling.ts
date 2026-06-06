export interface ProblemElement {
  coreGoal: string;
  techObject: string;
  constraints: string[];
  potentialConflicts: Array<{
    id: string;
    label: string;
    description?: string;
  }>;
}

export interface Conflict {
  type: string;
  description: string;
  parameters: Array<{
    name: string;
    direction?: string;
    requirement?: string;
  }>;
  severity: string;
}

export interface InnovationDirection {
  direction: string;
  description: string;
  confidence: number;
}

export interface ModelStructure {
  problemType: string;
  complexity: string;
  keyFactors: string[];
  rootCause: string;
  solutionSpace: string;
}

export interface ProblemModeling {
  id: string;
  taskId: string;
  problemElements: ProblemElement;
  conflicts: Conflict[];
  recommendedPrinciples: string[];
  innovationDirections: InnovationDirection[];
  modelStructure: ModelStructure;
}
