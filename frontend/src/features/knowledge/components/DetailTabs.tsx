interface DetailTabsProps {
  activeTab: string;
  dataSourceCount: number;
  onChange: (value: string) => void;
}

const TAB_DEFS: { key: string; label: string; icon: string }[] = [
  { key: 'data', label: '数据源', icon: 'fa-regular fa-file-lines' },
  { key: 'rag', label: 'RAG 配置', icon: 'fa-solid fa-sliders' },
  { key: 'recall', label: '召回测试', icon: 'fa-solid fa-magnifying-glass' },
];

const DetailTabs = ({ activeTab, dataSourceCount, onChange }: DetailTabsProps) => {
  return (
    <div className="flex shrink-0 items-center gap-0 border-b border-border-muted bg-background px-3">
      {TAB_DEFS.map(tab => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={`flex items-center gap-1.5 border-b-2 px-3.5 py-3 text-sm font-medium transition-colors ${
              isActive
                ? 'border-primary text-foreground'
                : 'border-transparent text-foreground-muted hover:text-foreground'
            }`}
          >
            <i className={`${tab.icon} text-xs`} />
            {tab.label}
            {tab.key === 'data' && dataSourceCount > 0 && (
              <span className="rounded-full bg-background-muted px-1.5 py-0.5 text-[10px] text-foreground-muted">
                {dataSourceCount}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

export default DetailTabs;
