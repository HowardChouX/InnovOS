import { useKnowledgeStore } from '../../../store/useKnowledgeStore';
import KnowledgeBaseNameDialog from './KnowledgeBaseNameDialog';

interface RenameKnowledgeGroupDialogProps {
  open: boolean;
  group: { id: string; name: string } | null;
  onClose: () => void;
}

export default function RenameKnowledgeGroupDialog({ open, group, onClose }: RenameKnowledgeGroupDialogProps) {
  const { renameGroup } = useKnowledgeStore();
  if (!open || !group) return null;

  return (
    <KnowledgeBaseNameDialog
      open={open}
      initialName={group.name}
      onSubmit={async (name) => {
        await renameGroup(group.id, name);
      }}
      onOpenChange={(open) => { if (!open) onClose(); }}
    />
  );
}
