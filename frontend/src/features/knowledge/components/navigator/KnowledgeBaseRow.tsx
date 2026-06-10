import type { KnowledgeBaseListItem } from '../../../../types/knowledge';
import type { CtxMenu } from './types';

interface KnowledgeBaseRowProps {
  base: KnowledgeBaseListItem;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onContextMenu: (e: React.MouseEvent, item: CtxMenu) => void;
}

export function KnowledgeBaseRow({ base, isSelected, onSelect, onContextMenu }: KnowledgeBaseRowProps) {
  return (
    <div
      key={base.id}
      onClick={() => onSelect(base.id)}
      onContextMenu={(e) => onContextMenu(e, {
        x: e.clientX, y: e.clientY, type: 'base',
        baseId: base.id, name: base.name, currentGroupId: base.groupId,
      })}
      className={`group/kb flex cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-sm ${
        isSelected
          ? 'bg-accent font-medium text-accent-foreground'
          : 'text-foreground-secondary hover:bg-accent/50'
      }`}
    >
      <i className="fa-regular fa-file-lines text-xs text-foreground-muted shrink-0" />
      <span className="min-w-0 flex-1 truncate">{base.name}</span>
      <span className="shrink-0 rounded-full bg-background-muted px-1.5 py-0.5 text-[10px] text-foreground-muted">
        {base.itemCount}
      </span>
      {isSelected && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onContextMenu(e, {
              x: e.clientX, y: e.clientY, type: 'base',
              baseId: base.id, name: base.name, currentGroupId: base.groupId,
            });
          }}
          className="ml-0.5 flex h-5 w-5 items-center justify-center rounded text-foreground-muted opacity-0 hover:bg-accent group-hover/kb:opacity-100"
        >
          <i className="fa-solid fa-ellipsis-h text-[9px]" />
        </button>
      )}
    </div>
  );
}
