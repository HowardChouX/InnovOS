import type { ReactNode } from 'react'

export const KnowledgeDialogHeader = ({ children, className }: { children: ReactNode; className?: string }) => {
  return (
    <div className={`pr-8 text-left ${className ?? ''}`}>
      <h2 className="text-lg font-semibold text-foreground">{children}</h2>
    </div>
  )
}

export const KnowledgeDialogBody = ({ className, children }: { className?: string; children: ReactNode }) => {
  return <div className={`space-y-3 ${className ?? ''}`}>{children}</div>
}

export const KnowledgeDialogField = ({ className, children }: { className?: string; children: ReactNode }) => {
  return <div className={`space-y-1.5 ${className ?? ''}`}>{children}</div>
}

export const KnowledgeDialogFooter = ({ className, children }: { className?: string; children: ReactNode }) => {
  return <div className={`flex items-center justify-end gap-2 ${className ?? ''}`}>{children}</div>
}
