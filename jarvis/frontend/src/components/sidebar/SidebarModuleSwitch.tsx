import { cn } from '@/lib/utils'

export function SidebarModuleSwitch({
  on,
  busy,
  onClick,
  onClass,
  offClass,
  ariaOn,
  ariaOff,
  size = 'md',
}: {
  on: boolean
  busy: boolean
  onClick: () => void
  onClass: string
  offClass: string
  ariaOn: string
  ariaOff: string
  size?: 'md' | 'sm'
}) {
  const track = size === 'sm' ? 'h-6 w-11' : 'h-7 w-12'
  const knob = size === 'sm' ? 'h-5 w-5' : 'h-6 w-6'
  return (
    <button
      type="button"
      disabled={busy}
      onClick={onClick}
      className={cn(
        'relative shrink-0 rounded-full transition-colors disabled:opacity-50',
        track,
        on ? onClass : offClass,
      )}
      aria-label={on ? ariaOn : ariaOff}
    >
      <span
        className={cn(
          'absolute top-0.5 rounded-full bg-white shadow transition-transform',
          knob,
          on ? 'left-5' : 'left-0.5',
        )}
      />
    </button>
  )
}
