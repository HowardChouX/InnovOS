export interface Patent {
  id: string;
  title: string;
  abstract: string;
  applicants: string[];
  inventors: string[];
  filingDate: string;
  publicationDate: string;
  patentNumber: string;
  ipcCodes: string[];
  relevanceScore: number;
}

export interface PatentStats {
  totalCount: number;
  relatedCount: number;
  coreCount: number;
  analyzedCount: number;
  topPatents: Patent[];
}

export interface PatentSearchQuery {
  q: string;
  page?: number;
  size?: number;
}
