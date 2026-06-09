import { Download, Loader2 } from 'lucide-react'
import { Button, type ButtonProps } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface DownloadActionButtonProps extends Omit<ButtonProps, 'children'> {
  label: string
  activeLabel?: string
  loading?: boolean
  active?: boolean
}

/** Кнопка скачивания с анимацией во время загрузки. */
export function DownloadActionButton({
  label,
  activeLabel,
  loading = false,
  active = false,
  className,
  disabled,
  ...props
}: DownloadActionButtonProps) {
  const busy = loading || active
  const text = busy && activeLabel ? activeLabel : label

  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      disabled={disabled || loading}
      className={cn(
        'relative h-8 w-full gap-1.5 overflow-hidden text-xs transition-all',
        busy && 'download-btn-active border-primary/40 bg-primary/10 text-primary',
        className,
      )}
      {...props}
    >
      {busy ? (
        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
      ) : (
        <Download className="h-3.5 w-3.5 shrink-0" />
      )}
      <span className="relative z-[1]">{text}</span>
      {busy && (
        <span
          className="pointer-events-none absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/15 to-primary/0 animate-[download-shimmer_1.8s_ease-in-out_infinite]"
          aria-hidden
        />
      )}
    </Button>
  )
}
