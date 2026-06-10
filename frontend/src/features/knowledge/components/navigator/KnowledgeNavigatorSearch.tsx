interface SearchProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function KnowledgeNavigatorSearch({ value, onChange, placeholder = '搜索知识库...' }: SearchProps) {
  return (
    <div className="relative">
      <i className="fa-solid fa-search absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-foreground-muted" />
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 w-full rounded-md border border-border bg-background pl-7 pr-3 text-xs text-foreground placeholder:text-foreground-muted focus:outline-none focus:ring-1 focus:ring-ring"
      />
    </div>
  );
}
