import type { ReactNode } from 'react'
import { Hint } from '@/components/ui/hint'
import { cn } from '@/lib/utils'

export type ComposerRailTone = 'default' | 'active' | 'recording' | 'warning' | 'error'

interface ComposerActionRailProps {
  hint: string
  icon: ReactNode
  onClick: () => void
  disabled?: boolean
  tone?: ComposerRailTone
  pressed?: boolean
  pulse?: boolean
  ariaLabel: string
  showDivider?: boolean
}

const toneClass: Record<ComposerRailTone, string> = {
  default: 'text-primary hover:bg-primary/10',
  active: 'bg-primary/15 text-primary ring-1 ring-primary/35 hover:bg-primary/20',
  recording:
    'bg-yellow-500/20 text-yellow-600 ring-1 ring-yellow-500/40 hover:bg-yellow-500/28 dark:text-yellow-400',
  warning: 'bg-amber-500/15 text-amber-600 ring-1 ring-amber-500/35 dark:text-amber-400',
  error: 'bg-destructive/15 text-destructive ring-1 ring-destructive/35 hover:bg-destructive/20',
}

/** Квадрат h-9 w-9 — как кнопка «Отправить»; только иконка, подпись в Hint. */
export function ComposerActionRail({
  hint,
  icon,
  onClick,
  disabled,
  tone = 'default',
  pressed,
  pulse,
  ariaLabel,
  showDivider = true,
}: ComposerActionRailProps) {
  return (
    <Hint text={hint}>
      <button
        type="button"
        disabled={disabled}
        onClick={onClick}
        aria-label={ariaLabel}
        aria-pressed={pressed}
        className={cn(
          'inline-flex h-9 w-9 max-h-9 max-w-9 shrink-0 items-center justify-center rounded-md transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          'disabled:pointer-events-none disabled:opacity-45',
          toneClass[tone],
          showDivider && 'border-r border-border/60',
          pulse && 'animate-pulse bg-primary/10',
          pressed && tone === 'default' && 'bg-primary/10',
        )}
      >
        {icon}
      </button>
    </Hint>
  )
}
