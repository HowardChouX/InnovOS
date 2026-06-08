import { useState, useRef, useEffect, useMemo } from 'react';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';

const NAV_WIDTH = 260;
const NAV_MIN = 200;
const NAV_MAX = 360;

export function KnowledgeNavigator() {
  const {
    bases, groups, loading, selectedBaseId, selectBase,
    deleteBase, openCreateBase, openRename,
  } = useKnowledgeStore();

  const [width, setWidth] = useState(NAV_WIDTH);
  const [searchValue, setSearchValue] = useState('');
  const [contextMenu, setContextMenu] = useState<{
    x: number; y: number; id: string; name: string; type: 'base' | 'group';
  } | null>(null);

  const sections = useMemo(() => {
    const filtered = searchValue
      ? bases.filter(b => b.name.toLowerCase().includes(searchValue.toLowerCase()))
      : bases;
    const groupMap = new Map<string, typeof bases>();
    const ungrouped: typeof bases = [];
    for (const b of filtered) {
      if (b.groupId) {
        const list = groupMap.get(b.groupId) || [];
        list.push(b);
        groupMap.set(b.groupId, list);
      } else {
        ungrouped.push(b);
      }
    }
    const result: { groupId: string | null; groupName: string; items: typeof bases }[] = [];
    for (const g of groups) {
      result.push({ groupId: g.id, groupName: g.name, items: groupMap.get(g.id) || [] });
    }
    result.push({ groupId: null, groupName: '未分组', items: ungrouped });
    return result;
  }, [bases, groups, searchValue]);

  const startResize = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    const onMove = (me: MouseEvent) => setWidth(Math.min(NAV_MAX, Math.max(NAV_MIN, startW + me.clientX - startX)));
    const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); document.body.style.cursor = ''; };
    document.body.style.cursor = 'col-resize';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  return (
    <div style={{ width, flexShrink: 0, position: 'relative', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <aside className="flex h-full min-h-0 flex-col border-r border-border-muted">
        <div className="flex shrink-0 items-center gap-2 p-3">
          <div className="min-w-0 flex-1">
            <input type="text" placeholder="搜索知识库..." value={searchValue} onChange={(e) => setSearchValue(e.target.value)}
              className="h-8 w-full rounded-md border border-border bg-background px-3 text-xs text-foreground placeholder:text-foreground-muted focus:outline-none focus:ring-1 focus:ring-ring" />
          </div>
          <button onClick={() => openCreateBase()} className="flex h-8 items-center gap-1 rounded-md bg-primary px-3 text-xs text-primary-foreground hover:bg-primary/90">
            <i className="fa-solid fa-plus" style={{ fontSize: 10 }} />新建
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
          {loading && <div className="py-8 text-center text-xs text-foreground-muted"><i className="fa-solid fa-circle-notch fa-spin mr-1.5" />加载中...</div>}
          {!loading && sections.length === 0 && <div className="py-8 text-center text-xs text-foreground-muted">暂无知识库</div>}
          {sections.map((section) => (
            <div key={section.groupId ?? 'ungrouped'} className="mb-3">
              <div className="mb-1 flex items-center gap-2 px-1 text-xs font-medium text-foreground-muted">
                {section.groupName}<span className="rounded-full bg-background-muted px-1.5 py-0.5 text-[10px]">{section.items.length}</span>
              </div>
              {section.items.map((b) => (
                <div key={b.id} onClick={() => selectBase(b.id)}
                  onContextMenu={(e) => { e.preventDefault(); setContextMenu({ x: e.clientX, y: e.clientY, id: b.id, name: b.name, type: 'base' }); }}
                  className={`flex cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm ${b.id === selectedBaseId ? 'bg-accent text-accent-foreground font-medium' : 'text-foreground-secondary hover:bg-accent/50'}`}>
                  <i className="fa-regular fa-file-lines text-xs text-foreground-muted" />
                  <span className="min-w-0 flex-1 truncate">{b.name}</span>
                  <span className="rounded-full bg-background-muted px-1.5 py-0.5 text-[10px] text-foreground-muted">{b.itemCount}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </aside>
      <div onMouseDown={startResize} className="absolute right-0 top-0 z-10 h-full w-1 cursor-col-resize hover:bg-border" />
      {contextMenu && (
        <NavigatorContextMenu x={contextMenu.x} y={contextMenu.y} onClose={() => setContextMenu(null)}
          onRename={() => { openRename(contextMenu.id, contextMenu.name, contextMenu.type); setContextMenu(null); }}
          onDelete={() => { if (contextMenu.type === 'base') deleteBase(contextMenu.id); setContextMenu(null); }} />
      )}
    </div>
  );
}

function NavigatorContextMenu({ x, y, onClose, onRename, onDelete }: {
  x: number; y: number; onClose: () => void; onRename: () => void; onDelete: () => void;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handler = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose(); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);
  return (
    <div ref={menuRef} className="min-w-[120px] rounded-lg border border-border bg-popover p-1 shadow-md"
      style={{ position: 'fixed', left: x, top: y, zIndex: 9999 }}>
      <button onClick={onRename} className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground hover:bg-accent">
        <i className="fa-solid fa-pen text-[10px]" />重命名
      </button>
      <button onClick={onDelete} className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10">
        <i className="fa-solid fa-trash-can text-[10px]" />删除
      </button>
    </div>
  );
}
