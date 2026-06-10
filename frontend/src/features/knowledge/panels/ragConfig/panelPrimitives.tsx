import type { ReactNode } from 'react'

export interface KnowledgeSelectOption {
  label: string
  value: string
}

export const RagFieldLabel = ({ className, label, hint }: { className?: string; label: string; hint?: string }) => {
  return (
    <div className={`mb-2 flex items-center gap-1.5 ${className ?? ''}`}>
      <span className="text-sm font-medium text-foreground">{label}</span>
      {hint ? (
        <div className="group relative">
          <i className="fa-solid fa-circle-info cursor-help text-[10px] text-foreground-muted" />
          <div className="pointer-events-none absolute bottom-full left-1/2 z-40 mb-1 hidden w-max max-w-sm -translate-x-1/2 rounded-md border border-border bg-popover px-2.5 py-1.5 text-[10px] leading-relaxed text-foreground shadow-lg group-hover:block">
            {hint}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export const RagSelectField = ({
  value,
  options,
  placeholder,
  onValueChange
}: {
  value?: string
  options: KnowledgeSelectOption[]
  placeholder?: string
  onValueChange: (value: string) => void
}) => {
  return (
    <select
      value={value ?? ''}
      onChange={(e) => onValueChange(e.target.value)}
      className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring">
      {placeholder ? (
        <option value="" disabled>
          {placeholder}
        </option>
      ) : null}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

export const RagNumericField = ({
  label,
  value,
  suffix,
  hint,
  onChange,
  inputClassName
}: {
  label?: string
  value: string
  suffix?: string
  hint?: string
  onChange: (value: string) => void
  inputClassName?: string
}) => {
  return (
    <div>
      {label ? <RagFieldLabel label={label} hint={hint} /> : null}
      <div className="relative">
        <input
          type="text"
          inputMode="numeric"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={`w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring shadow-none ${inputClassName ?? ''}`}
        />
        {suffix ? (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs leading-4 text-foreground-muted">
            {suffix}
          </span>
        ) : null}
      </div>
    </div>
  )
}

export const RagReadonlyField = ({ label, value, hint }: { label: string; value: string; hint?: string }) => {
  return (
    <div>
      <RagFieldLabel label={label} hint={hint} />
      <input
        readOnly
        value={value}
        className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground shadow-none"
      />
    </div>
  )
}

export const RagHintText = ({
  children,
  tone = 'info'
}: {
  children: ReactNode
  tone?: 'info' | 'warning' | 'error'
}) => {
  if (tone === 'error') {
    return (
      <div className="rounded-md badge-danger px-2.5 py-1.5 text-xs leading-4">
        {children}
      </div>
    )
  }

  return <p className="text-xs leading-4 text-foreground-muted">{children}</p>
}

export const RagSliderField = ({
  label,
  value,
  onValueChange,
  min,
  max,
  step,
  minLabel,
  maxLabel,
  formatValue,
  hint,
  disabled = false
}: {
  label: string
  value: number
  onValueChange: (value: number) => void
  min: number
  max: number
  step: number
  minLabel: string
  maxLabel: string
  formatValue: (value: number) => string
  hint?: string
  disabled?: boolean
}) => {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <RagFieldLabel label={label} hint={hint} className="mb-0" />
        <span className="text-xs leading-4 text-foreground-secondary tabular-nums">{formatValue(value)}</span>
      </div>

      <div className={disabled ? 'opacity-50' : undefined}>
        <input
          type="range"
          aria-label={label}
          value={value}
          onChange={(e) => onValueChange(Number(e.target.value))}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          className="w-full accent-primary"
        />

        <div className="mt-px flex items-center justify-between text-xs leading-4 text-foreground-muted">
          <span>{minLabel}</span>
          <span>{maxLabel}</span>
        </div>
      </div>
    </div>
  )
}
