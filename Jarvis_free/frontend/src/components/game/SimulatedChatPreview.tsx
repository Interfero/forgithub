import { cn } from '@/lib/utils'
import type { Message } from '@/types'

/**
 * Лёгкая имитация чата в компактной панели — без второго ChatArea и лишних опросов.
 * Полноценный чат — справа (главное окно) или на странице /game.
 */
export function SimulatedChatPreview({
  messages,
  className,
}: {
  messages: Message[]
  className?: string
}) {
  const tail = messages.filter((m) => m.role === 'user' || m.role === 'assistant').slice(-2)

  if (tail.length === 0) {
    return (
      <div
        className={cn(
          'rounded border border-dashed border-primary-foreground/20 bg-black/10 px-2 py-1.5 text-[9px] leading-snug text-primary-foreground/60',
          className,
        )}
      >
        Чат — справа. «Развернуть» откроет 2D-игру Jarvis в Chrome.
      </div>
    )
  }

  return (
    <div className={cn('space-y-1', className)} aria-label="Превью диалога">
      {tail.map((m) => (
        <div
          key={m.id}
          className={cn(
            'rounded px-1.5 py-1 text-[9px] leading-snug line-clamp-3',
            m.role === 'user'
              ? 'ml-2 bg-primary-foreground/15 text-primary-foreground/90'
              : 'mr-2 bg-black/25 text-primary-foreground/75',
          )}
        >
          <span className="font-semibold opacity-70">
            {m.role === 'user' ? 'Шеф' : 'Jarvis'}:{' '}
          </span>
          {m.content.replace(/\s+/g, ' ').trim()}
        </div>
      ))}
    </div>
  )
}
