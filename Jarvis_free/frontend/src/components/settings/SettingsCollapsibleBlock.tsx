import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface SettingsCollapsibleBlockProps {
  id: string
  title: string
  description?: string
  expanded: boolean
  onExpandedChange: (next: boolean) => void
  hidden?: boolean
  children: ReactNode
}

export function SettingsCollapsibleBlock({
  id,
  title,
  description,
  expanded,
  onExpandedChange,
  hidden = false,
  children,
}: SettingsCollapsibleBlockProps) {
  if (hidden) return null

  return (
    <section
      id={id}
      className="scroll-mt-4 rounded-xl border border-border/80 bg-card/50 shadow-sm"
    >
      <button
        type="button"
        onClick={() => onExpandedChange(!expanded)}
        className="flex w-full items-start gap-2 rounded-xl px-4 py-3 text-left hover:bg-muted/30"
        aria-expanded={expanded}
      >
        <ChevronDown
          className={cn(
            'mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform',
            !expanded && '-rotate-90',
          )}
        />
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-semibold uppercase tracking-wider text-foreground/90">
            {title}
          </span>
          {description ? (
            <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">
              {description}
            </span>
          ) : null}
        </span>
      </button>
      {expanded ? <div className="border-t border-border/50 px-4 pb-4 pt-2">{children}</div> : null}
    </section>
  )
}
