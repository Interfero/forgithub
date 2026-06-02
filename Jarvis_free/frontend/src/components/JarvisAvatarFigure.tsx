import jarvisAvatarUrl from '@jarvis-base'
import {
  JarvisSpeechBubble,
  type JarvisSpeechBubbleVariant,
} from '@/components/JarvisSpeechBubble'
import { JarvisAvatarFx } from '@/components/sidebar/JarvisAvatarFx'
import { cn } from '@/lib/utils'
import type { JarvisAvatarAnim } from '@/lib/jarvisHealth'

/**
 * Пиксель-арт Jarvis: чёрно-красный рисунок на прозрачном PNG (клетки фона прозрачны).
 * Облачко мыслей — над «головой», не перекрывая спрайт (тамагочи-питомец).
 */
export function JarvisAvatarFigure({
  anim,
  avatarClassName,
  bubble = null,
  alt = 'Jarvis',
}: {
  anim: JarvisAvatarAnim
  avatarClassName: string
  bubble?: JarvisSpeechBubbleVariant | null
  alt?: string
}) {
  return (
    <div className="jarvis-avatar-figure flex flex-col items-center">
      {bubble ? (
        <JarvisSpeechBubble variant={bubble} placement="above" className="mb-0.5" />
      ) : null}
      <div className="relative flex shrink-0 items-start justify-center">
        <JarvisAvatarFx anim={anim} />
        <img
          src={jarvisAvatarUrl}
          alt={alt}
          width={96}
          height={96}
          decoding="async"
          className={cn(
            'jarvis-avatar-pixel relative z-10 object-contain object-[center_12%]',
            avatarClassName,
          )}
        />
      </div>
    </div>
  )
}
