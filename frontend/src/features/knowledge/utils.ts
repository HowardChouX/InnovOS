import type { KnowledgeBaseListItem, KnowledgeGroup } from '../../types/knowledge';

interface Section {
  groupId: string | null;
  groupName: string;
  items: KnowledgeBaseListItem[];
}

export function buildKnowledgeBaseGroupSections(
  bases: KnowledgeBaseListItem[],
  groups: KnowledgeGroup[],
  searchValue: string
): Section[] {
  const filtered = searchValue
    ? bases.filter(b => b.name.toLowerCase().includes(searchValue.toLowerCase()))
    : bases;

  const groupMap = new Map<string, KnowledgeBaseListItem[]>();
  const ungrouped: KnowledgeBaseListItem[] = [];

  for (const base of filtered) {
    if (base.groupId) {
      const list = groupMap.get(base.groupId) || [];
      list.push(base);
      groupMap.set(base.groupId, list);
    } else {
      ungrouped.push(base);
    }
  }

  const sections: Section[] = [];

  // Grouped sections
  for (const group of groups) {
    const items = groupMap.get(group.id) || [];
    if (items.length > 0 || !searchValue) {
      sections.push({
        groupId: group.id,
        groupName: group.name,
        items,
      });
    }
  }

  // Ungrouped section
  if (ungrouped.length > 0 || !searchValue) {
    sections.push({
      groupId: null,
      groupName: '未分组',
      items: ungrouped,
    });
  }

  return sections;
}
