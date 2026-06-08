import { useState, useCallback } from 'react';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import type { KnowledgeItem, KnowledgeTabKey } from '../../types/knowledge';

const SOURCE_TABS: { key: KnowledgeTabKey; label: string; icon: string }[] = [
  { key: 'file', label: '文件', icon: 'fa-regular fa-file-lines' },
  { key: 'note', label: '笔记', icon: 'fa-regular fa-note-sticky' },
  { key: 'directory', label: '目录', icon: 'fa-regular fa-folder' },
  { key: 'url', label: '网址', icon: 'fa-solid fa-link' },
  { key: 'website', label: '网站', icon: 'fa-solid fa-globe' },
];

const STATUS_MAP: Record<string, { label: string; color: string; icon: string }> = {
  idle: { label: '待处理', color: 'text-foreground-muted', icon: 'fa-regular fa-circle' },
  preparing: { label: '准备中', color: 'text-yellow-500', icon: 'fa-solid fa-spinner fa-spin' },
  processing: { label: '处理中', color: 'text-yellow-500', icon: 'fa-solid fa-spinner fa-spin' },
  reading: { label: '读取中', color: 'text-blue-500', icon: 'fa-solid fa-book-open' },
  embedding: { label: '嵌入中', color: 'text-purple-500', icon: 'fa-solid fa-brain' },
  completed: { label: '已完成', color: 'text-green-500', icon: 'fa-solid fa-check' },
  failed: { label: '失败', color: 'text-red-500', icon: 'fa-solid fa-circle-exclamation' },
  deleting: { label: '删除中', color: 'text-foreground-muted', icon: 'fa-solid fa-trash-can' },
};

const TYPE_ICON_MAP: Record<string, string> = {
  file: 'fa-regular fa-file-lines', url: 'fa-solid fa-link', note: 'fa-regular fa-note-sticky', directory: 'fa-regular fa-folder',
};

function getItemTitle(item: KnowledgeItem): string {
  if (item.data && 'source' in item.data) return (item.data as any).source;
  return item.id.slice(0, 8);
}

export function KnowledgeDetail() {
  const { bases, selectedBaseId, items, loading, activeTab, setActiveTab, tabCounts, openAddSource, openRagConfig, openRecallTest, openItemChunks, deleteItem, uploadFile } = useKnowledgeStore();
  const base = bases.find(b => b.id === selectedBaseId);
  const [fileInputKey, setFileInputKey] = useState(0);
  if (!base) return null;

  const handleDrop = useCallback(async (e: React.DragEvent) => { e.preventDefault(); for (const file of Array.from(e.dataTransfer.files)) await uploadFile(file); }, [uploadFile]);
  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => { for (const file of Array.from(e.target.files || [])) await uploadFile(file); setFileInputKey(k => k + 1); }, [uploadFile]);
  const addButtonLabel = activeTab === 'file' ? '添加文件' : activeTab === 'note' ? '添加笔记' : activeTab === 'directory' ? '添加目录' : activeTab === 'url' ? '添加网址' : '添加网站';

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
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${base.status === 'completed' ? 'border-green-500/30 bg-green-500/10 text-green-500' : 'border-red-500/30 bg-red-500/10 text-red-500'}`}>
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
            <button onClick={openRagConfig} title="RAG 配置" className="flex h-8 items-center justify-center rounded-md text-foreground-muted hover:bg-accent"><i className="fa-solid fa-sliders text-sm" /></button>
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
        <button onClick={openAddSource} className="flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground hover:bg-primary/90">
          <i className="fa-solid fa-plus" style={{ fontSize: 10 }} />{addButtonLabel}
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="py-8 text-center text-xs text-foreground-muted"><i className="fa-solid fa-circle-notch fa-spin mr-1.5" />加载中...</div>
        ) : items.length === 0 ? (
          <EmptyState activeTab={activeTab} onDrop={handleDrop} onFileSelect={handleFileSelect} fileInputKey={fileInputKey} />
        ) : (
          <div className="flex flex-col gap-1.5">
            {items.map(item => <DocRow key={item.id} doc={item} onDelete={() => deleteItem(item.id)} onClick={() => openItemChunks(item.id)} />)}
          </div>
        )}
      </div>
    </main>
  );
}

function EmptyState({ activeTab, onDrop, onFileSelect, fileInputKey }: { activeTab: KnowledgeTabKey; onDrop: (e: React.DragEvent) => void; onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void; fileInputKey: number; }) {
  const [dragOver, setDragOver] = useState(false);
  if (activeTab === 'file') {
    return (
      <div className="flex flex-col items-center gap-4">
        <div onDragOver={e => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)} onDrop={onDrop}
          onClick={() => document.getElementById('kb-file-input')?.click()}
          className={`w-full cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-all ${dragOver ? 'border-primary bg-primary/5' : 'border-border bg-background-muted/50 hover:border-border-hover'}`}>
          <i className="fa-solid fa-cloud-arrow-up mb-3 block text-3xl text-foreground-muted" />
          <div className="mb-1 text-sm text-foreground">拖拽文件到这里</div>
          <div className="text-xs text-foreground-muted">支持 TXT, MD, HTML, PDF, DOCX, PPTX, XLSX, EPUB ... 格式</div>
          <input key={fileInputKey} id="kb-file-input" type="file" multiple onChange={onFileSelect} className="hidden" />
        </div>
        <div className="text-xs text-foreground-muted">暂无数据</div>
      </div>
    );
  }
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
  return (
    <div onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} onClick={onClick}
      className={`flex cursor-pointer items-center gap-2.5 rounded-lg border border-border-muted px-3 py-2.5 transition-colors ${hover ? 'bg-accent/50' : 'bg-background-muted/30'}`}>
      <i className={`${iconClass} text-base text-blue-500`} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-foreground">{getItemTitle(doc)}</div>
        <div className="mt-0.5 flex gap-2 text-[10px] text-foreground-muted"><span>{doc.type.toUpperCase()}</span><span>{new Date(doc.updatedAt).toLocaleDateString()}</span></div>
      </div>
      <span className={`inline-flex items-center gap-1 text-xs ${status.color}`}><i className={`${status.icon} text-[10px]`} />{status.label}</span>
      <button onClick={e => { e.stopPropagation(); onDelete(); }} className={`rounded p-1 text-foreground-muted transition-opacity hover:bg-destructive/10 hover:text-destructive ${hover ? 'opacity-70' : 'opacity-0'}`}>
        <i className="fa-solid fa-trash-can text-xs" />
      </button>
    </div>
  );
}
