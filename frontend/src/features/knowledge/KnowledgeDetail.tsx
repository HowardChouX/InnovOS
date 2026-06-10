import { useState, useCallback, useRef, useEffect } from 'react';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import type { KnowledgeItem, KnowledgeTabKey } from '../../types/knowledge';
import NoteEditorDialog from './NoteEditorDialog';
import { AddUrlDialog } from './AddUrlDialog';
import { STATUS_MAP, TYPE_ICON_MAP, getItemTitle } from './utils/statusStyles';

const SOURCE_TABS: { key: KnowledgeTabKey; label: string; icon: string }[] = [
  { key: 'file', label: '文件', icon: 'fa-regular fa-file-lines' },
  { key: 'note', label: '笔记', icon: 'fa-regular fa-note-sticky' },
  { key: 'url', label: '网址', icon: 'fa-solid fa-link' },
];

export function KnowledgeDetail() {
  const { bases, selectedBaseId, items, loading, activeTab, setActiveTab, tabCounts,
    searchQuery, setSearchQuery,
    openRecallTest, openItemChunks, deleteItem, uploadFile, addItem, fetchItems,
    reindexItem,
  } = useKnowledgeStore();
  const base = bases.find(b => b.id === selectedBaseId);

  // Refs for file/folder inputs
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [fileInputKey, setFileInputKey] = useState(0);
  const [noteEditorOpen, setNoteEditorOpen] = useState(false);
  const [urlDialogOpen, setUrlDialogOpen] = useState(false);


  // ── Polling for in-progress items ──
  const hasActiveItems = items.some(item =>
    ['idle', 'preparing', 'processing', 'reading', 'embedding', 'deleting'].includes(item.status)
  );
  useEffect(() => {
    if (!hasActiveItems || !selectedBaseId) return;
    const interval = setInterval(() => {
      fetchItems(selectedBaseId, 1, true);
    }, 3000);
    return () => clearInterval(interval);
  }, [hasActiveItems, selectedBaseId, fetchItems]);

  if (!base) return null;

  // ── 客户端搜索过滤 ──
  const filteredItems = items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const title = getItemTitle(item).toLowerCase();
    return title.includes(q);
  });

  // ── File tab: directly open OS file picker ──
  const triggerFilePicker = () => fileInputRef.current?.click();
  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    for (const file of Array.from(e.target.files || [])) await uploadFile(file);
    setFileInputKey(k => k + 1);
  }, [uploadFile]);



  // ── URL tab: open dialog ──
  const openUrlDialog = () => setUrlDialogOpen(true);

  // ── Note tab: open NoteEditorDialog ──
  const openNoteEditor = () => setNoteEditorOpen(true);

  // ── Drag-drop for file tab ──
  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    for (const file of Array.from(e.dataTransfer.files)) await uploadFile(file);
  }, [uploadFile]);

  // ── Determine the add button label and action ──
  const addButtonLabel = activeTab === 'file' ? '添加文件'
    : activeTab === 'note' ? '添加笔记'
    : '添加网址';

  const handleAddClick = () => {
    if (activeTab === 'file') triggerFilePicker();
    else if (activeTab === 'note') openNoteEditor();
    else if (activeTab === 'url') openUrlDialog();
  };

  return (
    <main className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
      <header className="shrink-0 px-3 py-3.5">
        <div className="flex min-w-0 items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <i className="fa-solid fa-book text-lg text-primary" />
            </div>
            <div className="flex min-w-0 flex-col gap-1.5">
              <div className="flex min-w-0 items-center gap-2">
                <h1 className="min-w-0 truncate font-bold text-2xl text-foreground leading-8">{base.name}</h1>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${base.status === 'completed' ? 'badge-success' : 'badge-danger'}`}>
                  {base.status === 'completed' ? '正常' : '失败'}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-foreground-muted leading-4">
                <span>{base.itemCount} 个数据源</span><span aria-hidden="true">·</span><span>更新于 {new Date(base.updatedAt).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button onClick={openRecallTest} title="召回测试" className="flex h-8 items-center justify-center rounded-md text-foreground-muted hover:bg-accent"><i className="fa-solid fa-magnifying-glass text-sm" /></button>
          </div>
        </div>
      </header>

      <div className="flex items-center gap-0 border-b border-border-muted px-3 shrink-0">
        {SOURCE_TABS.map(tab => {
          const isActive = activeTab === tab.key;
          return (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 border-b-2 px-3.5 py-3 text-sm font-medium transition-colors ${isActive ? 'border-primary text-foreground' : 'border-transparent text-foreground-muted hover:text-foreground'}`}>
              <i className={`${tab.icon} text-xs`} />{tab.label}
              <span className={`rounded-full px-1.5 py-0.5 text-[10px] min-w-[16px] text-center ${isActive ? 'bg-primary/15 text-primary' : 'bg-background-muted text-foreground-muted'}`}>{tabCounts[tab.key]}</span>
            </button>
          );
        })}
        <div className="flex-1" />
        <button onClick={handleAddClick} className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:bg-primary/90">
          <i className="fa-solid fa-plus" style={{ fontSize: 10 }} />{addButtonLabel}
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {/* 搜索输入 */}
        <div className="mb-3">
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="搜索知识项..."
            className="w-full rounded-md border border-border bg-background-muted px-3 py-1.5 text-sm text-foreground outline-none placeholder:text-foreground-muted/50 focus:ring-1 focus:ring-ring"
          />
        </div>

        {loading ? (
          <div className="py-8 text-center text-xs text-foreground-muted"><i className="fa-solid fa-circle-notch fa-spin mr-1.5" />加载中...</div>
        ) : filteredItems.length === 0 && searchQuery.trim() ? (
          <div className="py-16 text-center">
            <i className="fa-solid fa-search mb-2 block text-2xl text-foreground-muted opacity-30" />
            <div className="text-sm text-foreground-muted">未找到匹配 "{searchQuery}" 的结果</div>
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            activeTab={activeTab}
            onDrop={handleDrop}
            onTriggerFilePicker={triggerFilePicker}
            onOpenUrlDialog={openUrlDialog}
          />
        ) : (
          <div className="flex flex-col gap-1.5">
            {filteredItems.map(item => <DocRow key={item.id} doc={item} onDelete={() => deleteItem(item.id)} onClick={() => openItemChunks(item.id)} />)}
          </div>
        )}
      </div>

      {/* Hidden file input (also used by directory tab) */}
      <input key={fileInputKey} ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileSelect} />

      {/* NoteEditorDialog */}
      <NoteEditorDialog open={noteEditorOpen} onClose={() => setNoteEditorOpen(false)} />

      {/* AddUrlDialog */}
      <AddUrlDialog open={urlDialogOpen} onClose={() => setUrlDialogOpen(false)} />
    </main>
  );
}

function EmptyState({
  activeTab, onDrop,
  onTriggerFilePicker, onOpenUrlDialog,
}: {
  activeTab: KnowledgeTabKey;
  onDrop: (e: React.DragEvent) => void;
  onTriggerFilePicker: () => void;
  onOpenUrlDialog: () => void;
}) {
  const [dragOver, setDragOver] = useState(false);

  // ── File tab: drag-drop + click-to-upload ──
  if (activeTab === 'file') {
    return (
      <div className="flex flex-col items-center gap-4">
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={onTriggerFilePicker}
          className={`w-full cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-all ${dragOver ? 'border-primary bg-primary/5' : 'border-border bg-background-muted/50 hover:border-border-hover'}`}
        >
          <i className="fa-solid fa-cloud-arrow-up mb-3 block text-3xl text-foreground-muted" />
          <div className="mb-1 text-sm text-foreground">拖拽文件到这里</div>
          <div className="text-xs text-foreground-muted">支持 TXT, MD, HTML, PDF, DOCX, PPTX, XLSX, EPUB ... 格式</div>
        </div>
        <div className="text-xs text-foreground-muted">暂无数据</div>
      </div>
    );
  }

  // ── Note tab ──
  if (activeTab === 'note') {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <i className="fa-regular fa-note-sticky mb-2 block text-4xl text-foreground-muted opacity-40" />
        <div className="text-sm text-foreground-muted">暂无笔记</div>
        <div className="text-xs text-foreground-muted">点击右上角"添加笔记"按钮创建笔记</div>
      </div>
    );
  }

  // ── URL tab ──
  if (activeTab === 'url') {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <i className="fa-solid fa-link mb-2 block text-4xl text-foreground-muted opacity-40" />
        <div className="text-sm text-foreground-muted">暂无网址</div>
        <button
          onClick={onOpenUrlDialog}
          className="rounded-md bg-primary px-5 py-2 text-sm text-primary-foreground hover:bg-primary/90"
        >
          添加网址
        </button>
        <div className="text-xs text-foreground-muted">支持批量添加，每行一个网址</div>
      </div>
    );
  }

  // ── Website tab (placeholder) ──
  return (
    <div className="py-16 text-center">
      <i className="fa-regular fa-folder-open mb-3 block text-4xl text-foreground-muted opacity-40" />
      <div className="text-sm text-foreground-muted">暂无数据</div>
    </div>
  );
}

function DocRow({ doc, onDelete, onClick }: { doc: KnowledgeItem; onDelete: () => void; onClick: () => void }) {
  const iconClass = TYPE_ICON_MAP[doc.type] || 'fa-regular fa-file';
  const status = STATUS_MAP[doc.status] || STATUS_MAP.idle;
  const [hover, setHover] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const canReindex = doc.status === 'completed' || doc.status === 'failed';
  const { reindexItem } = useKnowledgeStore();
  const handleReindex = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setReindexing(true);
    try {
      await reindexItem(doc.id);
    } catch {
      // error handled by store
    } finally {
      setReindexing(false);
    }
  };
  const showActions = hover && !reindexing;
  return (
    <div onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} onClick={onClick}
      className={`flex cursor-pointer items-center gap-2.5 rounded-lg border border-border-muted px-3 py-2.5 transition-colors ${hover ? 'bg-accent/50' : 'bg-background-muted/30'}`}>
      <i className={`${iconClass} text-base text-accent-info`} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-foreground">{getItemTitle(doc)}</div>
        <div className="mt-0.5 flex gap-2 text-[10px] text-foreground-muted"><span>{doc.type.toUpperCase()}</span><span>{new Date(doc.updatedAt).toLocaleDateString()}</span></div>
      </div>
      <span className={`inline-flex w-[5em] items-center justify-center gap-1 text-xs ${status.color}`}><i className={`${status.icon} text-[10px]`} />{status.label}</span>
      {reindexing ? (
        <span className="flex h-7 w-7 items-center justify-center"><i className="fa-solid fa-spinner fa-spin text-xs text-foreground-muted" /></span>
      ) : (
        <>
          {canReindex ? (
            <button onClick={handleReindex} title="重新索引"
              className={`rounded p-1 text-foreground-muted transition-opacity hover:text-primary ${showActions ? 'opacity-70' : 'opacity-0'}`}>
              <i className="fa-solid fa-rotate text-xs" />
            </button>
          ) : null}
          <button onClick={e => { e.stopPropagation(); onDelete(); }} title="删除"
            className={`rounded p-1 text-foreground-muted transition-opacity hover:bg-destructive/10 hover:text-destructive ${showActions ? 'opacity-70' : 'opacity-0'}`}>
            <i className="fa-solid fa-trash-can text-xs" />
          </button>
        </>
      )}
    </div>
  );
}
