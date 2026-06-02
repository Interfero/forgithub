import { cn } from '@/lib/utils'

function formatMb(bytes: number): string {
  if (bytes <= 0) return '0 МБ'
  return `${Math.round(bytes / (1024 * 1024))} МБ`
}

export interface DownloadProgressProps {
  percent: number
  message: string
  bytesDone?: number
  bytesTotal?: number
  indeterminate?: boolean
  className?: string
  size?: 'sm' | 'md'
}

/** Единая полоса загрузки (Qwen, XTTS и др.). */
export function DownloadProgress({
  percent,
  message,
  bytesDone = 0,
  bytesTotal = 0,
  indeterminate,
  className,
  size = 'sm',
}: DownloadProgressProps) {
  const hasBytes = bytesTotal > 0
  const pct = indeterminate
    ? undefined
    : Math.max(0, Math.min(100, Math.round(percent)))
  const barWidth = pct !== undefined ? `${Math.max(pct > 0 ? 3 : 0, pct)}%` : undefined

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
        <span className="min-w-0 truncate">{message}</span>
        <span className="shrink-0 tabular-nums">
          {pct !== undefined ? `${pct}%` : '…'}
          {hasBytes && (
            <span className="ml-1 opacity-80">
              · {formatMb(bytesDone)}
              {bytesTotal > 0 ? ` / ${formatMb(bytesTotal)}` : ''}
            </span>
          )}
        </span>
      </div>
      <div
        className={cn(
          'relative overflow-hidden rounded-full bg-muted/80 shadow-inner',
          size === 'sm' ? 'h-2' : 'h-2.5',
        )}
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={message}
      >
        {indeterminate || pct === undefined ? (
          <div
            className="absolute inset-y-0 w-[38%] rounded-full bg-primary shadow-[0_0_10px_rgba(45,212,191,0.45)] animate-[qwen-load_1.35s_ease-in-out_infinite]"
            aria-hidden
          />
        ) : (
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-primary transition-[width] duration-500 ease-out shadow-[0_0_10px_rgba(45,212,191,0.4)]"
            style={{ width: barWidth }}
          />
        )}
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-r from-transparent via-primary-foreground/10 to-transparent animate-[download-shimmer_2s_ease-in-out_infinite]"
          aria-hidden
        />
      </div>
    </div>
  )
}
