import { Bot } from 'lucide-react'
import type { OperationProgressState } from '@/types'

interface OperationProgressProps {
  progress: OperationProgressState
}

export function OperationProgress({ progress }: OperationProgressProps) {
  const { message, percent, current, total, logs, phase } = progress
  const showBar = total > 0 && percent != null

  return (
    <div className="flex gap-3 px-4 py-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
        <Bot className="h-4 w-4 text-primary" />
      </div>
      <div className="min-w-0 flex-1 space-y-2 rounded-xl border border-border/60 bg-muted/40 px-3 py-2.5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-sm font-medium text-foreground">{message}</p>
          {showBar && (
            <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
              {current} / {total}
              {percent != null ? ` · ${percent}%` : ''}
            </span>
          )}
        </div>
        {showBar && (
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-background/80"
            role="progressbar"
            aria-valuenow={percent ?? 0}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={phase}
          >
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
              style={{ width: `${percent}%` }}
            />
          </div>
        )}
        {!showBar && (
          <div className="flex gap-1 py-0.5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary [animation-delay:300ms]" />
          </div>
        )}
        {logs.length > 0 && (
          <ul className="max-h-28 space-y-0.5 overflow-y-auto border-t border-border/40 pt-2 text-xs text-muted-foreground">
            {logs.map((line, i) => (
              <li key={`${i}-${line.slice(0, 24)}`} className="truncate font-mono">
                {line}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
