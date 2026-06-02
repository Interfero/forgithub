import { cn } from '@/lib/utils'

export interface ServiceEnableToggleProps {
  label: string
  description?: string
  enabled: boolean
  disabled?: boolean
  busy?: boolean
  /** Ключ/сервис настроен — без этого тумблер неактивен */
  ready?: boolean
  onToggle: (next: boolean) => void | Promise<void>
}

/** Тумблер вкл/выкл сервиса — заметная подсветка в обоих состояниях. */
export function ServiceEnableToggle({
  label,
  description,
  enabled,
  disabled = false,
  busy = false,
  ready = true,
  onToggle,
}: ServiceEnableToggleProps) {
  const off = !enabled
  const blocked = disabled || !ready || busy

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 transition-colors',
        enabled
          ? 'border-emerald-500/50 bg-emerald-500/12 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.15)]'
          : 'border-border/70 bg-muted/25',
        blocked && 'opacity-60',
      )}
    >
      <div className="min-w-0 flex-1">
        <p
          className={cn(
            'text-[11px] font-semibold',
            enabled ? 'text-emerald-800 dark:text-emerald-200' : 'text-foreground',
          )}
        >
          {label}
        </p>
        {description && (
          <p className="mt-0.5 text-[10px] text-muted-foreground">{description}</p>
        )}
        <p
          className={cn(
            'mt-1 text-[10px] font-medium',
            enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground',
          )}
        >
          {enabled ? '● Включено' : '○ Выключено'}
          {!ready && ' · сначала сохраните ключи'}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label={enabled ? `Выключить: ${label}` : `Включить: ${label}`}
        disabled={blocked}
        onClick={() => void onToggle(!enabled)}
        className={cn(
          'relative h-7 w-[3.25rem] shrink-0 rounded-full p-0.5 transition-all duration-300',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          enabled
            ? 'bg-emerald-600 shadow-[inset_0_2px_6px_rgba(0,0,0,0.35),0_0_10px_rgba(16,185,129,0.45)]'
            : 'bg-muted shadow-[inset_0_2px_6px_rgba(0,0,0,0.4)]',
          blocked && 'cursor-not-allowed',
        )}
      >
        <span
          className={cn(
            'pointer-events-none block h-6 w-6 rounded-full bg-white shadow-md transition-transform duration-300',
            enabled ? 'translate-x-[1.35rem]' : 'translate-x-0',
          )}
        />
      </button>
    </div>
  )
}
