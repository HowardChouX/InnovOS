export interface KnowledgeDoc {
  id: string;
  title: string;
  content: string;
  category: string;
  tags: string[];
  source: string;
  docType: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeCategory {
  name: string;
  count: number;
}
