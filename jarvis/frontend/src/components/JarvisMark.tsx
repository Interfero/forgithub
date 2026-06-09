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
  'jarvis-bridge-panel relative flex shrink-0 flex-col items-center justify-end overflow-hidden rounded-2xl border px-1 pt-1'

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
      <div className="jarvis-imperial-room rounded-t-2xl" aria-hidden>
        <div className="jarvis-imperial-room__ceiling" />
        <div className="jarvis-imperial-room__backwall" />
        <div className="jarvis-imperial-room__wall-l" />
        <div className="jarvis-imperial-room__wall-r" />
        <div className="jarvis-imperial-room__floor" />
        <div className="jarvis-imperial-room__plinth" />
      </div>
      <JarvisAvatarFigure
        anim={health.avatarAnim}
        bubble={bubble}
        avatarClassName={cn(
          'relative z-10 h-11 w-11 drop-shadow-[0_2px_8px_rgb(0_0_0/0.5)]',
          AVATAR_ANIM_CLASS[health.avatarAnim],
        )}
      />
      <span
        className={cn(
          'jarvis-bridge-fg z-20 mt-0.5 w-full truncate px-0.5 pb-0.5 text-center text-[8px] font-medium leading-none',
          STATUS_LINE_CLASS[health.avatarAnim],
          '[text-shadow:0_1px_2px_rgb(0_0_0/0.65)]',
        )}
      >
        {health.screenStatus}
      </span>
    </div>
  )
}
