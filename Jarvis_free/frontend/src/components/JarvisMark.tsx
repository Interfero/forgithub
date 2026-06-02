import { useMemo } from 'react'
import { JarvisAvatarFigure } from '@/components/JarvisAvatarFigure'
import type { JarvisSpeechBubbleVariant } from '@/components/JarvisSpeechBubble'
import {
  AVATAR_ANIM_CLASS,
  buildJarvisHealth,
  SCREEN_ANIM_CLASS,
  STATUS_LINE_CLASS,
} from '@/lib/jarvisHealth'
import { cn } from '@/lib/utils'
import type { AgentState } from '@/types'

const FRAME =
  'relative flex shrink-0 flex-col items-center justify-end overflow-visible rounded-2xl border border-primary/30 bg-primary px-1 pt-1 shadow-[inset_0_0_0_1px_rgb(255_255_255/0.06)]'

/** Мини-экран заставки чата — тамагочи-аватар Jarvis и статус. */
export function JarvisMark({
  agent,
  bubble = null,
  className,
}: {
  agent: AgentState
  bubble?: JarvisSpeechBubbleVariant | null
  className?: string
}) {
  const health = useMemo(() => buildJarvisHealth(agent), [agent])

  return (
    <div
      className={cn(
        FRAME,
        SCREEN_ANIM_CLASS[health.avatarAnim],
        bubble ? 'min-h-[4.25rem] min-w-[3.5rem]' : 'h-14 w-14',
        className,
      )}
      title={`${health.screenStatus} — ${health.connectivityLabel}`}
    >
      <JarvisAvatarFigure
        anim={health.avatarAnim}
        bubble={bubble}
        avatarClassName={cn('h-11 w-11', AVATAR_ANIM_CLASS[health.avatarAnim])}
      />
      <span
        className={cn(
          'z-20 mt-0.5 w-full truncate px-0.5 pb-0.5 text-center text-[8px] font-medium leading-none',
          STATUS_LINE_CLASS[health.avatarAnim],
          '[text-shadow:0_1px_0_rgb(0_0_0/0.4)]',
        )}
      >
        {health.screenStatus}
      </span>
    </div>
  )
}
