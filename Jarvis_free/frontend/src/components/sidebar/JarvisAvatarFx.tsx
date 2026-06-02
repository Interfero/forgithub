import type { JarvisAvatarAnim } from '@/lib/jarvisHealth'
import { cn } from '@/lib/utils'

function DotRow({
  count,
  className,
  stagger = 0.18,
}: {
  count: number
  className: string
  stagger?: number
}) {
  return (
    <div className="flex items-center gap-1" aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <span
          key={i}
          className={cn('h-1 w-1 rounded-full', className)}
          style={{ animationDelay: `${i * stagger}s` }}
        />
      ))}
    </div>
  )
}

/** Декоративные индикаторы под аватаром по смыслу статуса. */
export function JarvisAvatarFx({ anim }: { anim: JarvisAvatarAnim }) {
  switch (anim) {
    case 'offline':
      return (
        <div
          className="pointer-events-none absolute bottom-1 left-1/2 z-20 -translate-x-1/2"
          aria-hidden
        >
          <span className="relative block h-3 w-3">
            <span className="absolute left-0 top-0 h-3 w-0.5 origin-bottom rotate-45 rounded-full bg-red-300/90 animate-jarvis-offline-x" />
            <span className="absolute right-0 top-0 h-3 w-0.5 origin-bottom -rotate-45 rounded-full bg-red-300/90 animate-jarvis-offline-x" />
          </span>
        </div>
      )
    case 'boot':
    case 'loading':
      return (
        <div
          className="pointer-events-none absolute bottom-1 left-1/2 z-20 -translate-x-1/2"
          aria-hidden
        >
          <span className="block h-2 w-2 rounded-full border border-cyan-200/80 border-t-transparent animate-jarvis-loading" />
        </div>
      )
    case 'angry':
      return (
        <div
          className="pointer-events-none absolute bottom-1 left-1/2 z-20 flex -translate-x-1/2 gap-0.5"
          aria-hidden
        >
          <span className="h-1.5 w-1.5 rounded-full bg-red-400 shadow-[0_0_6px_rgb(248_113_113/0.95)]" />
          <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-red-500 shadow-[0_0_6px_rgb(239_68_68/0.95)]" />
          <span className="h-1.5 w-1.5 rounded-full bg-red-400 shadow-[0_0_6px_rgb(248_113_113/0.95)]" />
        </div>
      )
    case 'corePending':
      return (
        <div
          className="pointer-events-none absolute bottom-1 left-1/2 z-20 -translate-x-1/2"
          aria-hidden
        >
          <DotRow
            count={3}
            className="bg-amber-200 shadow-[0_0_4px_rgb(251_191_36/0.8)] animate-jarvis-core-dot"
            stagger={0.22}
          />
        </div>
      )
    case 'listen':
      return (
        <div
          className="pointer-events-none absolute bottom-0.5 left-1/2 z-20 flex h-3 -translate-x-1/2 items-end gap-0.5"
          aria-hidden
        >
          {[0, 1, 2, 3].map((i) => (
            <span
              key={i}
              className="w-0.5 rounded-full bg-emerald-200 shadow-[0_0_3px_rgb(167_243_208/0.9)] animate-jarvis-listen-bar"
              style={{ animationDelay: `${i * 0.1}s` }}
            />
          ))}
        </div>
      )
    case 'think':
      return (
        <div
          className="pointer-events-none absolute bottom-1 left-1/2 z-20 -translate-x-1/2"
          aria-hidden
        >
          <DotRow
            count={3}
            className="bg-sky-200 shadow-[0_0_4px_rgb(125_211_252/0.85)] animate-jarvis-think-dot"
            stagger={0.14}
          />
        </div>
      )
    case 'search':
      return (
        <div
          className="pointer-events-none absolute bottom-1.5 left-1/2 z-20 h-0.5 w-10 -translate-x-1/2 overflow-hidden rounded-full bg-blue-950/40"
          aria-hidden
        >
          <span className="block h-full w-1/3 rounded-full bg-blue-200/90 animate-jarvis-search-glide" />
        </div>
      )
    case 'image':
      return (
        <div
          className="pointer-events-none absolute bottom-1 left-1/2 z-20 flex -translate-x-1/2 gap-1.5"
          aria-hidden
        >
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1 w-1 rotate-45 bg-fuchsia-200 shadow-[0_0_4px_rgb(240_171_252/0.9)] animate-jarvis-image-spark"
              style={{ animationDelay: `${i * 0.25}s` }}
            />
          ))}
        </div>
      )
    case 'idle':
      return (
        <div
          className="pointer-events-none absolute bottom-1 left-1/2 z-20 -translate-x-1/2"
          aria-hidden
        >
          <span className="block h-1.5 w-1.5 rounded-full bg-emerald-100/90 shadow-[0_0_5px_rgb(167_243_208/0.6)] animate-jarvis-idle-dot" />
        </div>
      )
    default:
      return null
  }
}
