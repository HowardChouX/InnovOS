import type { KnowledgeGroup } from '../../../../types/knowledge';
import type { CtxMenu } from './types';

interface SectionHeaderProps {
  name: string;
  count: number;
  isExpanded: boolean;
  groupId?: string | null;
  group?: KnowledgeGroup | undefined;
  onToggle: () => void;
  onContextMenu: (e: React.MouseEvent, item: CtxMenu) => void;
}

export function KnowledgeNavigatorSectionHeader({
  name,
  count,
  isExpanded,
  group,
  onToggle,
  onContextMenu,
}: SectionHeaderProps) {
  return (
    <div
      className="group flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent/60"
      onClick={onToggle}
      onContextMenu={(e) => {
        if (group) {
          onContextMenu(e, { x: e.clientX, y: e.clientY, type: 'group', groupId: group.id, name: group.name });
        }
      }}
    >
      <i className={`fa-solid fa-chevron-right text-[9px] transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
      <span className="min-w-0 flex-1 truncate">{name}</span>
      <span className="rounded-full bg-background-muted px-1.5 py-0.5 text-[10px]">{count}</span>
      {group && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onContextMenu(e, { x: e.clientX, y: e.clientY, type: 'group', groupId: group.id, name: group.name });
          }}
          className="ml-0.5 flex h-5 w-5 items-center justify-center rounded text-foreground-muted opacity-0 hover:bg-accent group-hover:opacity-100"
        >
          <i className="fa-solid fa-ellipsis-h text-[9px]" />
        </button>
      )}
    </div>
  );
}
