interface ResizeHandleProps {
  onMouseDown: (e: React.MouseEvent) => void;
}

export function KnowledgeNavigatorResizeHandle({ onMouseDown }: ResizeHandleProps) {
  return (
    <div
      onMouseDown={onMouseDown}
      className="absolute right-0 top-0 z-10 h-full w-1 cursor-col-resize hover:bg-border-hover"
    />
  );
}
