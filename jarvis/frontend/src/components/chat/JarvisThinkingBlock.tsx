import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface JarvisThinkingBlockProps {
  lines: string[]
}

export function JarvisThinkingBlock({ lines }: JarvisThinkingBlockProps) {
  const [expanded, setExpanded] = useState(false)

  if (lines.length === 0) return null

  return (
    <div
      className="mx-4 my-2 rounded-xl border border-dashed border-primary/35 bg-muted/30 shadow-sm"
      role="status"
      aria-live="polite"
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-muted/50"
            aria-expanded={expanded}
          >
            <ChevronDown
              className={cn(
                'h-4 w-4 shrink-0 text-primary/70 transition-transform',
                !expanded && '-rotate-90',
              )}
            />
            <span className="text-xs font-semibold uppercase tracking-wide text-primary/90">
              Рассуждения Jarvis
            </span>
            <span className="ml-auto text-[10px] text-muted-foreground">
              {lines.length} шаг.
            </span>
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs">
          Отладочный поток: маршрут, инструменты, голосовой профиль. Исчезает после ответа.
        </TooltipContent>
      </Tooltip>

      {expanded ? (
        <div className="max-h-52 overflow-y-auto border-t border-dashed border-primary/20 px-3 py-2">
          <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-muted-foreground">
            {lines.join('\n')}
          </pre>
        </div>
      ) : (
        <p className="border-t border-dashed border-primary/15 px-3 py-1.5 text-[11px] text-muted-foreground">
          {lines[lines.length - 1]}
        </p>
      )}
    </div>
  )
}
