export interface CtxMenu {
  x: number;
  y: number;
  type: 'base' | 'group' | 'createMenu';
  baseId?: string;
  groupId?: string;
  name: string;
  currentGroupId?: string | null;
}
