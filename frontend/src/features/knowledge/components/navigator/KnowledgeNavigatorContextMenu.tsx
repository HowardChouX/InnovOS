import { createPortal } from 'react-dom';
import type { KnowledgeGroup } from '../../../../types/knowledge';
import type { CtxMenu } from './types';

interface ContextMenuProps {
  contextMenu: CtxMenu;
  groups: KnowledgeGroup[];
  menuRef: React.RefObject<HTMLDivElement | null>;
  onClose: () => void;
  onRenameBase: (id: string, name: string) => void;
  onMoveBase: (baseId: string, groupId: string | null) => void;
  onDeleteBase: (id: string) => void;
  onRenameGroup: (id: string, name: string) => void;
  onCreateBaseInGroup: (groupId: string) => void;
  onDeleteGroup: (id: string) => void;
}

export function KnowledgeNavigatorContextMenu({
  contextMenu,
  groups,
  menuRef,
  onClose,
  onRenameBase,
  onMoveBase,
  onDeleteBase,
  onRenameGroup,
  onCreateBaseInGroup,
  onDeleteGroup,
}: ContextMenuProps) {
  if (contextMenu.type === 'createMenu') return null;

  return createPortal(
    <div
      ref={menuRef}
      className="min-w-[140px] rounded-lg border border-border bg-popover p-1 shadow-md"
      style={{ position: 'fixed', left: contextMenu.x, top: contextMenu.y, zIndex: 9999 }}
    >
      {contextMenu.type === 'base' && (
        <>
          <button
            onClick={() => { const ctx = contextMenu as CtxMenu; onClose(); onRenameBase(ctx.baseId!, ctx.name); }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent"
          >
            <i className="fa-solid fa-pen text-[10px]" />重命名
          </button>
          <button
            onClick={async () => { const ctx = contextMenu as CtxMenu; await onMoveBase(ctx.baseId!, null); }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent"
          >
            <i className="fa-solid fa-arrow-right text-[10px]" />移至未分组
          </button>
          {groups.filter(g => g.id !== contextMenu.currentGroupId).map(g => (
            <button
              key={g.id}
              onClick={async () => { const ctx = contextMenu as CtxMenu; await onMoveBase(ctx.baseId!, g.id); }}
              className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent"
            >
              <i className="fa-solid fa-arrow-right text-[10px]" />移至 {g.name}
            </button>
          ))}
          <div className="my-1 border-t border-border-light" />
          <button
            onClick={async () => { const ctx = contextMenu as CtxMenu; await onDeleteBase(ctx.baseId!); onClose(); }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10"
          >
            <i className="fa-solid fa-trash-can text-[10px]" />删除
          </button>
        </>
      )}
      {contextMenu.type === 'group' && (
        <>
          <button
            onClick={() => { const ctx = contextMenu as CtxMenu; onClose(); onRenameGroup(ctx.groupId!, ctx.name); }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent"
          >
            <i className="fa-solid fa-pen text-[10px]" />重命名
          </button>
          <button
            onClick={() => { onClose(); onCreateBaseInGroup(contextMenu.groupId!); }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent"
          >
            <i className="fa-solid fa-plus text-[10px]" />在此分组创建
          </button>
          <div className="my-1 border-t border-border-light" />
          <button
            onClick={async () => { const ctx = contextMenu as CtxMenu; await onDeleteGroup(ctx.groupId!); onClose(); }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10"
          >
            <i className="fa-solid fa-trash-can text-[10px]" />删除分组
          </button>
        </>
      )}
    </div>,
    document.body
  );
}
