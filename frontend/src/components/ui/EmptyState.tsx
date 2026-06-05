interface EmptyStateProps {
  message?: string;
  icon?: string;
}

export function EmptyState({ message = '暂无数据', icon = 'fa-inbox' }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-500">
      <i className={`fa-regular ${icon} text-3xl mb-3`} />
      <p className="text-sm">{message}</p>
    </div>
  );
}
