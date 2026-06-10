import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import RecallSearchBar from './panels/recallTest/RecallSearchBar'
import RecallTestBody from './panels/recallTest/RecallTestBody'
import RecallTestProvider from './panels/recallTest/RecallTestProvider'

interface Props {
  open: boolean;
  onClose: () => void;
}

export function RecallTestPanel({ open, onClose }: Props) {
  const { selectedBaseId } = useKnowledgeStore();

  if (!open || !selectedBaseId) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="grid h-[80vh] w-[720px] max-w-[95vw] grid-rows-[auto_minmax(0,1fr)] overflow-hidden rounded-xl border border-border bg-background shadow-xl"
        onClick={e => e.stopPropagation()}>
        <div className="flex shrink-0 items-center justify-between border-b border-border-muted px-5 py-3.5">
          <span className="text-base font-semibold text-foreground">召回测试</span>
          <button onClick={onClose} className="flex h-7 w-7 items-center justify-center rounded-md text-foreground-muted hover:bg-accent">
            <i className="fa-solid fa-xmark" />
          </button>
        </div>
        <RecallTestProvider key={selectedBaseId} baseId={selectedBaseId}>
          <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] bg-background">
            <div className="px-6 py-5">
              <RecallSearchBar />
            </div>
            <div className="min-h-0">
              <RecallTestBody />
            </div>
          </div>
        </RecallTestProvider>
      </div>
    </div>,
    document.body
  );
}
