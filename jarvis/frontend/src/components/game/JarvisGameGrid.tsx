import { useMemo } from 'react'
import { JarvisAvatarFigure } from '@/components/JarvisAvatarFigure'
import {
  JARVIS_GAME_CELL_UNITS,
  JARVIS_GAME_DEFAULT_POS,
  JARVIS_GAME_GRID_SIZE,
} from '@/lib/jarvisGameCoords'
import { cn } from '@/lib/utils'
import type { JarvisAvatarAnim } from '@/lib/jarvisHealth'
import type { JarvisSpeechBubbleVariant } from '@/components/JarvisSpeechBubble'

/** Визуальный размер аватара как в компактной панели — не меняем. */
const AVATAR_CLASS =
  'h-[4.25rem] w-[4.25rem] max-h-[4.25rem] max-w-[4.25rem]'

export function JarvisGameGrid({
  avatarAnim,
  avatarCls,
  bubble,
}: {
  avatarAnim: JarvisAvatarAnim
  avatarCls: string
  bubble: JarvisSpeechBubbleVariant | null
}) {
  const pos = JARVIS_GAME_DEFAULT_POS
  const gridLabel = useMemo(
    () =>
      `Мир ${JARVIS_GAME_GRID_SIZE}×${JARVIS_GAME_GRID_SIZE} · Jarvis (${pos.x}, ${pos.y}) · клетка ${JARVIS_GAME_CELL_UNITS}×${JARVIS_GAME_CELL_UNITS}`,
    [pos.x, pos.y],
  )

  return (
    <div
      className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-[#6b7280]"
      aria-label={gridLabel}
    >
      <div
        className="relative shrink-0 border border-white/20 shadow-inner"
        style={{
          width: '34rem',
          height: '34rem',
          maxWidth: 'min(94vw, 34rem)',
          maxHeight: 'min(50vh, 34rem)',
          backgroundColor: '#6b7280',
          backgroundImage: `
            linear-gradient(to right, rgba(255,255,255,0.22) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255,255,255,0.22) 1px, transparent 1px)
          `,
          backgroundSize: '4.25rem 4.25rem',
          backgroundPosition: 'center center',
        }}
      >
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <JarvisAvatarFigure
            anim={avatarAnim}
            bubble={bubble}
            avatarClassName={cn(AVATAR_CLASS, avatarCls)}
          />
        </div>
        <p className="pointer-events-none absolute bottom-1 left-1 right-1 text-center text-[10px] leading-tight text-white/90 drop-shadow">
          {gridLabel}
        </p>
      </div>
    </div>
  )
}
