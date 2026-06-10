interface KnowledgeBaseIconProps {
  className?: string;
  status?: string;
}

const KnowledgeBaseIcon = ({ className = '', status }: KnowledgeBaseIconProps) => {
  const isFailed = status === 'failed';
  const wrapperStyle: React.CSSProperties = isFailed
    ? { borderColor: 'color-mix(in srgb, var(--accent-red) 20%, transparent)', backgroundColor: 'color-mix(in srgb, var(--accent-red) 5%, transparent)' }
    : { borderColor: 'color-mix(in srgb, var(--accent-blue) 20%, transparent)', backgroundColor: 'color-mix(in srgb, var(--accent-blue) 5%, transparent)' };

  return (
    <span
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${className}`}
      style={wrapperStyle}
    >
      <i className={`fa-solid ${isFailed ? 'fa-triangle-exclamation text-accent-danger' : 'fa-book text-accent-info'} text-sm`} />
    </span>
  );
};

export default KnowledgeBaseIcon;
