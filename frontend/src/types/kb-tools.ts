/**
 * AI Agent KB Tools 类型定义
 *
 * 参考 CherryStudio KnowledgeSearchTool / KnowledgeListTool 的数据合约。
 * 与后端 /api/kb-tools/* 端点对应。
 */

// ── kb__list ──────────────────────────────────────────────────────

export interface KbListInput {
  query?: string;
  groupId?: string;
}

export interface KbListOutputItem {
  id: string;
  name: string;
  groupId: string | null;
  status: "completed" | "failed";
  documentCount: number;
  itemCount: number;
  sampleSources: string[];
}

export type KbListOutput = KbListOutputItem[];

// ── kb__search ────────────────────────────────────────────────────

export interface KbSearchInput {
  query: string;
  baseIds: string[];
}

export interface KbSearchOutputItem {
  id: number;
  content: string;
  score: number;
  source: string;
}

export type KbSearchOutput = KbSearchOutputItem[];
