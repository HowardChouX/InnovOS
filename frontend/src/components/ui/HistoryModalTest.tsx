import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useTaskStore } from '../../store/useTaskStore';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function HistoryModalTest({ isOpen, onClose }: Props) {
  const tasks = useTaskStore((s) => s.tasks);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);

  useEffect(() => {
    if (isOpen) fetchTasks();
  }, [isOpen]); // 不依赖 fetchTasks 避免循环

  if (!isOpen) return null;

  return createPortal(
    <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 99999 }} onClick={onClose}>
      <div style={{ width: 500, maxHeight: '80vh', background: '#fff', borderRadius: 12, overflow: 'hidden' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>历史方案</strong>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer' }}>×</button>
        </div>
        <div style={{ padding: 20, maxHeight: '60vh', overflowY: 'auto' }}>
          {tasks.length === 0 ? <p>暂无历史方案</p> : tasks.map(t => (
            <div key={t.id} style={{ padding: '8px 0', borderBottom: '1px solid #eee' }}>
              <div style={{ fontWeight: 500 }}>{t.title}</div>
              <div style={{ fontSize: 12, color: '#999' }}>{t.status}</div>
            </div>
          ))}
        </div>
      </div>
    </div>,
    document.body
  );
}
