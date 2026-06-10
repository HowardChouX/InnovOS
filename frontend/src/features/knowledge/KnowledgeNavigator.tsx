import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import { buildKnowledgeBaseGroupSections } from './utils';
import type { CtxMenu } from './components/navigator';
import { KnowledgeNavigatorSearch } from './components/navigator';
import { KnowledgeNavigatorCreateMenu } from './components/navigator';
import { KnowledgeNavigatorSectionHeader } from './components/navigator';
import { KnowledgeBaseRow } from './components/navigator';
import { KnowledgeNavigatorContextMenu } from './components/navigator';
import { KnowledgeNavigatorResizeHandle } from './components/navigator';

const NAV_WIDTH = 260;
const NAV_MIN = 200;
const NAV_MAX = 360;

interface KnowledgeNavigatorProps {
  onOpenRenameGroup?: (group: { id: string; name: string }) => void;
}

export function KnowledgeNavigator({ onOpenRenameGroup }: KnowledgeNavigatorProps) {
  const {
    bases, groups, loading, selectedBaseId, selectBase,
    deleteBase, openCreateBase, deleteGroup,
    openCreateGroup, openRename, updateBase,
  } = useKnowledgeStore();

  const [width, setWidth] = useState(NAV_WIDTH);
  const [searchValue, setSearchValue] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['ungrouped']));
  const [contextMenu, setContextMenu] = useState<CtxMenu | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const sections = useMemo(
    () => buildKnowledgeBaseGroupSections(bases, groups, searchValue),
    [bases, groups, searchValue]
  );

  // Close context menu on outside click
  useEffect(() => {
    if (!contextMenu) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setContextMenu(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [contextMenu]);

  // Resize handler
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    const onMove = (me: MouseEvent) => setWidth(Math.min(NAV_MAX, Math.max(NAV_MIN, startW + me.clientX - startX)));
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
    };
    document.body.style.cursor = 'col-resize';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [width]);

  const toggleGroup = useCallback((groupId: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }, []);

  const handleContextMenu = useCallback((e: React.MouseEvent, item: CtxMenu) => {
    e.preventDefault();
    setContextMenu(item);
  }, []);

  const closeMenu = useCallback(() => setContextMenu(null), []);

  const handleMoveBase = useCallback(async (baseId: string, groupId: string | null) => {
    await updateBase(baseId, { groupId });
    closeMenu();
  }, [updateBase, closeMenu]);

  // Ensure "ungrouped" is always expanded
  useEffect(() => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      next.add('ungrouped');
      return next;
    });
  }, []);

  const handleCreateMenuToggle = useCallback(() => {
    setContextMenu(ctx => ctx?.type === 'createMenu' ? null : { x: 0, y: 0, type: 'createMenu', name: '' });
  }, []);

  return (
    <div style={{ width, flexShrink: 0, position: 'relative', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <aside className="flex h-full min-h-0 flex-col border-r border-border-muted">
        {/* Header with search and create menu */}
        <div className="flex shrink-0 items-center gap-2 p-3">
          <div className="min-w-0 flex-1">
            <KnowledgeNavigatorSearch value={searchValue} onChange={setSearchValue} />
          </div>

          <KnowledgeNavigatorCreateMenu
            visible={contextMenu?.type === 'createMenu'}
            menuRef={menuRef}
            onToggle={handleCreateMenuToggle}
            onClose={closeMenu}
            onCreateBase={openCreateBase}
            onCreateGroup={openCreateGroup}
          />
        </div>

        {/* Content */}
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
          {loading && (
            <div className="py-8 text-center text-xs text-foreground-muted">
              <i className="fa-solid fa-circle-notch fa-spin mr-1.5" />
              加载中...
            </div>
          )}
          {!loading && sections.length === 0 && (
            <div className="py-8 text-center text-xs text-foreground-muted">暂无知识库</div>
          )}
          {sections.map((section) => {
            const key = section.groupId ?? 'ungrouped';
            const isExpanded = expandedGroups.has(key);
            const group = section.groupId ? groups.find(g => g.id === section.groupId) : undefined;

            return (
              <div key={key} className="mb-2">
                <KnowledgeNavigatorSectionHeader
                  name={group?.name ?? '未分组'}
                  count={section.items.length}
                  isExpanded={isExpanded}
                  group={group}
                  onToggle={() => toggleGroup(key)}
                  onContextMenu={handleContextMenu}
                />

                {/* Items */}
                {isExpanded && (
                  <div className="mt-0.5 space-y-0.5">
                    {section.items.map((b) => (
                      <KnowledgeBaseRow
                        key={b.id}
                        base={b}
                        isSelected={b.id === selectedBaseId}
                        onSelect={selectBase}
                        onContextMenu={handleContextMenu}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </aside>

      {/* Resize handle */}
      <KnowledgeNavigatorResizeHandle onMouseDown={startResize} />

      {/* Context menu */}
      {contextMenu && contextMenu.type !== 'createMenu' && (
        <KnowledgeNavigatorContextMenu
          contextMenu={contextMenu}
          groups={groups}
          menuRef={menuRef}
          onClose={closeMenu}
          onRenameBase={(id, name) => { closeMenu(); openRename(id, name, 'base'); }}
          onMoveBase={handleMoveBase}
          onDeleteBase={async (id) => { await deleteBase(id); closeMenu(); }}
          onRenameGroup={(id, name) => { closeMenu(); onOpenRenameGroup?.({ id, name }); }}
          onCreateBaseInGroup={(groupId) => { closeMenu(); openCreateBase(groupId); }}
          onDeleteGroup={async (id) => { await deleteGroup(id); closeMenu(); }}
        />
      )}
    </div>
  );
}
