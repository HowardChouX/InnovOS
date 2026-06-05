import type { ReactNode } from 'react';

interface MainPanelProps {
  children: ReactNode;
}

export function MainPanel({ children }: MainPanelProps) {
  return (
    <main className="flex-1 flex flex-col overflow-y-auto bg-slate-950 relative">
      {children}
    </main>
  );
}
