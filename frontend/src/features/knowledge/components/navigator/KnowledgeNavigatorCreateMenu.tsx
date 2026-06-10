interface CreateMenuProps {
  visible: boolean;
  menuRef: React.RefObject<HTMLDivElement | null>;
  onToggle: () => void;
  onClose: () => void;
  onCreateBase: () => void;
  onCreateGroup: () => void;
}

export function KnowledgeNavigatorCreateMenu({
  visible,
  menuRef,
  onToggle,
  onClose,
  onCreateBase,
  onCreateGroup,
}: CreateMenuProps) {
  return (
    <div className="relative">
      <button
        onClick={onToggle}
        className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-foreground-muted hover:bg-accent hover:text-foreground"
        title="新建"
      >
        <i className="fa-solid fa-plus text-xs" />
      </button>
      {visible && (
        <div
          ref={menuRef}
          className="absolute right-0 top-full z-50 mt-1 w-40 rounded-lg border border-border bg-popover p-1 shadow-md"
          onMouseLeave={onClose}
        >
          <button
            onClick={() => { onClose(); onCreateBase(); }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent"
          >
            <i className="fa-solid fa-book text-[10px]" />
            新建知识库
          </button>
          <button
            onClick={() => { onClose(); onCreateGroup(); }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent"
          >
            <i className="fa-solid fa-folder-plus text-[10px]" />
            新建分组
          </button>
        </div>
      )}
    </div>
  );
}
