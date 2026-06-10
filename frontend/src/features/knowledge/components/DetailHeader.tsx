import { useState } from 'react';
import { createPortal } from 'react-dom';
import type { KnowledgeBase, KnowledgeBaseListItem } from '../../../types/knowledge';
import KnowledgeBaseIcon from './KnowledgeBaseIcon';

interface DetailHeaderProps {
  base: KnowledgeBaseListItem | KnowledgeBase;
  itemCount: number;
  searchQuery?: string;
  onSearchChange?: (value: string) => void;
  onOpenRagConfig?: () => void;
  onOpenRecallTest?: () => void;
  onRenameBase?: (base: Pick<KnowledgeBase, 'id' | 'name'>) => void;
  onDeleteBase?: (baseId: string) => void;
}

const DetailHeader = ({
  base,
  itemCount,
  searchQuery = '',
  onSearchChange,
  onOpenRagConfig,
  onOpenRecallTest,
  onRenameBase,
  onDeleteBase,
}: DetailHeaderProps) => {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  const isFailed = base.status === 'failed';
  const hasSearch = Boolean(onSearchChange);
  const isSearchVisible = isSearchOpen || searchQuery.length > 0;

  const formattedDate = base.updatedAt
    ? new Date(base.updatedAt).toLocaleDateString('zh-CN')
    : '';

  const handleDelete = async () => {
    await onDeleteBase?.(base.id);
    setIsDeleteDialogOpen(false);
  };

  const statusBadge = isFailed
    ? 'badge-danger'
    : 'badge-success';

  return (
    <>
      <header className="shrink-0 px-3 py-3.5">
        <div className="flex min-w-0 items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <KnowledgeBaseIcon status={base.status} />
            <div className="flex min-w-0 flex-col gap-1.5">
              <div className="flex min-w-0 items-center gap-2">
                <h1 className="min-w-0 truncate font-bold text-2xl text-foreground leading-8">
                  {base.name}
                </h1>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${statusBadge}`}>
                  {isFailed ? '失败' : '正常'}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-foreground-muted leading-4">
                <span>{itemCount} 个数据源</span>
                <span aria-hidden="true">·</span>
                <span>更新于 {formattedDate}</span>
              </div>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            {hasSearch && (
              isSearchVisible ? (
                <div className="w-36 shrink-0">
                  <input
                    autoFocus
                    value={searchQuery}
                    onChange={(e) => onSearchChange?.(e.target.value)}
                    onBlur={() => { if (searchQuery.length === 0) setIsSearchOpen(false); }}
                    placeholder="搜索数据源..."
                    className="h-7 w-full rounded-md border border-border bg-background-muted px-2 text-xs text-foreground outline-none placeholder:text-foreground-muted/50 focus:ring-1 focus:ring-ring"
                  />
                </div>
              ) : (
                <button
                  onClick={() => setIsSearchOpen(true)}
                  title="搜索"
                  className="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-accent"
                >
                  <i className="fa-solid fa-magnifying-glass text-sm" />
                </button>
              )
            )}
            {onOpenRagConfig && (
              <button
                onClick={onOpenRagConfig}
                title="RAG 配置"
                className="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-accent"
              >
                <i className="fa-solid fa-sliders text-sm" />
              </button>
            )}
            {onOpenRecallTest && (
              <button
                onClick={onOpenRecallTest}
                title="召回测试"
                className="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-accent"
              >
                <i className="fa-solid fa-magnifying-glass text-sm" />
              </button>
            )}
            <div className="relative">
              <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                title="更多"
                className="flex h-8 w-8 items-center justify-center rounded-md text-foreground-muted hover:bg-accent"
              >
                <i className="fa-solid fa-ellipsis-h text-sm" />
              </button>
              {isMenuOpen && (
                <div
                  className="absolute right-0 top-full z-50 mt-1 w-36 rounded-lg border border-border bg-popover p-1 shadow-md"
                  onMouseLeave={() => setIsMenuOpen(false)}
                >
                  {onRenameBase && (
                    <button
                      onClick={() => { setIsMenuOpen(false); onRenameBase({ id: base.id, name: base.name }); }}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent"
                    >
                      <i className="fa-solid fa-pen text-[10px]" />
                      重命名
                    </button>
                  )}
                  {onDeleteBase && (
                    <button
                      onClick={() => { setIsMenuOpen(false); setIsDeleteDialogOpen(true); }}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10"
                    >
                      <i className="fa-solid fa-trash-can text-[10px]" />
                      删除
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {isDeleteDialogOpen && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={() => setIsDeleteDialogOpen(false)}>
          <div className="w-[360px] rounded-xl border border-border bg-card p-5" onClick={e => e.stopPropagation()}>
            <div className="mb-2 text-base font-semibold text-foreground">确认删除</div>
            <div className="mb-4 text-xs text-foreground-muted">
              确定要删除知识库「{base.name}」吗？该操作不可恢复。
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setIsDeleteDialogOpen(false)} className="rounded-md border border-border px-3.5 py-1.5 text-xs text-foreground-secondary hover:bg-accent">取消</button>
              <button onClick={handleDelete} className="rounded-md bg-[var(--accent-red)] px-3.5 py-1.5 text-xs text-white hover:opacity-90">删除</button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
};

export default DetailHeader;
