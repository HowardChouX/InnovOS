import { useEffect, useState, useCallback, createContext, useContext, useMemo } from 'react';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import type { KnowledgeBase } from '../../types/knowledge';
import { KnowledgeNavigator } from './KnowledgeNavigator';
import { KnowledgeDetail } from './KnowledgeDetail';

import { RecallTestPanel } from './RecallTestPanel';
import CreateKnowledgeBaseDialog from './CreateKnowledgeBaseDialog';
import CreateKnowledgeGroupDialog from './components/CreateKnowledgeGroupDialog';
import KnowledgeBaseNameDialog from './components/KnowledgeBaseNameDialog';
import RestoreKnowledgeBaseDialog from './components/RestoreKnowledgeBaseDialog';
import RenameKnowledgeGroupDialog from './components/RenameKnowledgeGroupDialog';

// ─── Context for dialog coordination ─────────────────────────
interface KnowledgePageContextValue {
  openRenameBaseDialog: (base: Pick<KnowledgeBase, 'id' | 'name'>) => void;
  openRestoreBaseDialog: (base: KnowledgeBase) => void;
}

const KnowledgePageContext = createContext<KnowledgePageContextValue | null>(null);

export const useKnowledgePage = () => {
  const ctx = useContext(KnowledgePageContext);
  if (!ctx) {
    throw new Error('useKnowledgePage must be used within KnowledgePage');
  }
  return ctx;
};

// ─── Main Page ──────────────────────────────────────────────
export default function KnowledgePage() {
  const {
    fetchBases, fetchGroups, selectedBaseId,
    isRecallTestOpen, closeRecallTest,
    isCreateBaseOpen, closeCreateBase,
    isCreateGroupOpen, closeCreateGroup,
    createGroup,
    editingName, closeRename,
    isRestoringBase, restoreBase,
  } = useKnowledgeStore();

  // Dialog state for rename base and restore
  const [renameBaseDialog, setRenameBaseDialog] = useState<{ id: string; name: string } | null>(null);
  const [restoreDialogBase, setRestoreDialogBase] = useState<KnowledgeBase | null>(null);
  const [renameGroupDialog, setRenameGroupDialog] = useState<{ id: string; name: string } | null>(null);

  useEffect(() => {
    fetchBases();
    fetchGroups();
  }, []);

  const handleRenameBaseSubmit = useCallback(async (name: string) => {
    if (!renameBaseDialog) return;
    const { renameBase } = useKnowledgeStore.getState();
    await renameBase(renameBaseDialog.id, name);
    setRenameBaseDialog(null);
  }, [renameBaseDialog]);

  const handleRestoreBaseRestored = useCallback((base: KnowledgeBase) => {
    setRestoreDialogBase(null);
    // Select the restored base
    const { selectBase, fetchBases } = useKnowledgeStore.getState();
    fetchBases().then(() => selectBase(base.id));
  }, []);

  const ctxValue = useMemo<KnowledgePageContextValue>(() => ({
    openRenameBaseDialog: (base) => setRenameBaseDialog(base),
    openRestoreBaseDialog: (base) => setRestoreDialogBase(base),
  }), []);

  return (
    <KnowledgePageContext value={ctxValue}>
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 overflow-hidden bg-background">
          <KnowledgeNavigator
            onOpenRenameGroup={(group) => setRenameGroupDialog(group)}
          />
          {selectedBaseId ? <KnowledgeDetail /> : <KnowledgeEmptyState />}
        </div>

        {/* Dialogs */}
        <RecallTestPanel open={isRecallTestOpen} onClose={closeRecallTest} />
        <CreateKnowledgeBaseDialog open={isCreateBaseOpen} onClose={closeCreateBase} />

        <CreateKnowledgeGroupDialog
          open={isCreateGroupOpen}
          onSubmit={async (name) => {
            await createGroup(name);
          }}
          onOpenChange={closeCreateGroup}
        />

        <KnowledgeBaseNameDialog
          open={!!renameBaseDialog}
          initialName={renameBaseDialog?.name ?? ''}
          onSubmit={handleRenameBaseSubmit}
          onOpenChange={(open) => { if (!open) setRenameBaseDialog(null); }}
        />

        <RenameKnowledgeGroupDialog
          open={!!renameGroupDialog}
          group={renameGroupDialog}
          onClose={() => setRenameGroupDialog(null)}
        />

        <RestoreKnowledgeBaseDialog
          open={!!restoreDialogBase}
          base={restoreDialogBase}
          isRestoring={isRestoringBase}
          onRestore={restoreBase}
          onOpenChange={(open) => { if (!open) setRestoreDialogBase(null); }}
          onRestored={handleRestoreBaseRestored}
        />

        {/* Legacy rename (from store) */}
        {editingName && editingName.type === 'base' && (
          <KnowledgeBaseNameDialog
            open
            initialName={editingName.name}
            onSubmit={async (name) => {
              const { renameBase } = useKnowledgeStore.getState();
              await renameBase(editingName.id, name);
              closeRename();
            }}
            onOpenChange={(open) => { if (!open) closeRename(); }}
          />
        )}
      </div>
    </KnowledgePageContext>
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
