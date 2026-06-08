import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import { KnowledgeNavigator } from './KnowledgeNavigator';
import { KnowledgeDetail } from './KnowledgeDetail';
import { AddKnowledgeItemDialog } from './AddKnowledgeItemDialog';
import { RagConfigPanel } from './RagConfigPanel';
import { RecallTestPanel } from './RecallTestPanel';
import CreateKnowledgeBaseDialog from './CreateKnowledgeBaseDialog';

export default function KnowledgePage() {
  const {
    fetchBases, fetchGroups, selectedBaseId,
    isAddSourceOpen, closeAddSource,
    isRagConfigOpen, closeRagConfig,
    isRecallTestOpen, closeRecallTest,
    isCreateBaseOpen, closeCreateBase,
    editingName, closeRename, renameBase, renameGroup,
  } = useKnowledgeStore();

  useEffect(() => {
    fetchBases();
    fetchGroups();
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 flex-1 overflow-hidden bg-background">
        <KnowledgeNavigator />
        {selectedBaseId ? <KnowledgeDetail /> : <KnowledgeEmptyState />}
      </div>

      <AddKnowledgeItemDialog open={isAddSourceOpen} onClose={closeAddSource} />
      <RagConfigPanel open={isRagConfigOpen} onClose={closeRagConfig} />
      <RecallTestPanel open={isRecallTestOpen} onClose={closeRecallTest} />
      <CreateKnowledgeBaseDialog open={isCreateBaseOpen} onClose={closeCreateBase} />

      {editingName && (
        <RenameDialog
          title={editingName.type === 'base' ? '重命名知识库' : '重命名分组'}
          open={!!editingName}
          onClose={closeRename}
          initialName={editingName.name}
          onSubmit={(name) => {
            if (editingName.type === 'base') {
              renameBase(editingName.id, name);
            } else {
              renameGroup(editingName.id, name);
            }
          }}
        />
      )}
    </div>
  );
}

function KnowledgeEmptyState() {
  const { openCreateBase } = useKnowledgeStore();
  return (
    <div className="flex flex-1 items-center justify-center gap-4 flex-col">
      <i className="fa-regular fa-folder-open text-5xl text-foreground-muted opacity-20" />
      <div className="text-sm text-foreground-muted">选择或创建一个知识库</div>
      <button
        onClick={() => openCreateBase()}
        className="flex items-center gap-1.5 rounded-md bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        <i className="fa-solid fa-plus text-xs" />
        创建知识库
      </button>
    </div>
  );
}

function RenameDialog({ title, open, onClose, initialName, onSubmit }: {
  title: string; open: boolean; onClose: () => void;
  initialName: string; onSubmit: (name: string) => void;
}) {
  const [name, setName] = useState(initialName);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="w-[360px] rounded-xl border border-border bg-card p-5" onClick={e => e.stopPropagation()}>
        <div className="mb-3 text-base font-semibold text-foreground">{title}</div>
        <input
          autoFocus value={name} onChange={e => setName(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && name.trim()) { onSubmit(name.trim()); onClose(); } }}
          className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-md border border-border px-3.5 py-1.5 text-xs text-foreground-secondary hover:bg-accent">取消</button>
          <button onClick={() => { if (name.trim()) { onSubmit(name.trim()); onClose(); } }} className="rounded-md bg-primary px-3.5 py-1.5 text-xs text-primary-foreground hover:bg-primary/90">确认</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
