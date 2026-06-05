export interface ConflictNode {
  id: string;
  label: string;
  description: string;
  type: 'center' | 'satellite';
  color?: string;
  sublabel?: string;
  position?: 'top' | 'right' | 'bottom' | 'left';
}

export interface ConflictEdge {
  sourceId: string;
  targetId: string;
  label: string;
}

export interface ConflictAnalysis {
  id: string;
  taskId: string;
  centerNode: ConflictNode;
  satelliteNodes: ConflictNode[];
  edges: ConflictEdge[];
  principles: string[];
}
