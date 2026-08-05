export interface Patent {
  id: string;
  title: string;
  summary: string;
  applicant: string;
  inventor: string;
  applicationDate: string;
  documentDate: string;
  mainIpc: string;
  ipc: string;
  legalStatus: string;
  type: string;
  documentNumber: string;
  relevance_score?: number;
  source_innovation?: string;
  search_query?: string;

  // 兼容旧字段
  abstract?: string;
  applicants?: string[];
  inventors?: string[];
  filingDate?: string;
  publicationDate?: string;
  patentNumber?: string;
  ipcCodes?: string[];
}

export interface PatentSearchQuery {
  q: string;
  page?: number;
  size?: number;
}
