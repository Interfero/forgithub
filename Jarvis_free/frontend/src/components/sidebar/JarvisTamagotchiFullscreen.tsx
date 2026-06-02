import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { JarvisScreenBody } from '@/components/sidebar/jarvisScreen'
import { cn } from '@/lib/utils'
import { MODE_LABELS } from '@/types'
import type { JarvisScreenBody } from '@/components/sidebar/jarvisScreen'
import type { ComponentProps } from 'react'
import type { AgentState } from '@/types'

type ScreenBodyProps = Omit<
  ComponentProps<typeof JarvisScreenBody>,
  'layout' | 'onToggleExpand'
>

export function JarvisTamagotchiFullscreen({
  open,
  onOpenChange,
  screenBodyProps,
  agent,
  chatPanel,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  screenBodyProps: ScreenBodyProps
  agent: AgentState
  chatPanel: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false)
    }
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onOpenChange])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex h-[100dvh] max-h-[100dvh] flex-col bg-background"
      role="dialog"
      aria-modal="true"
      aria-label="Jarvis — тамагочи и чат"
    >
      <div
        className={cn(
          'flex min-h-0 flex-1 flex-col sm:flex-row',
          'pt-[max(0.25rem,env(safe-area-inset-top))]',
          'pb-[max(1.25rem,env(safe-area-inset-bottom))]',
          'pl-[max(0.25rem,env(safe-area-inset-left))]',
          'pr-[max(0.25rem,env(safe-area-inset-right))]',
        )}
      >
        <aside
          className={cn(
            'flex min-h-0 shrink-0 flex-col',
            'h-[min(38vh,300px)] w-full border-b border-border sm:h-full sm:w-[min(42%,22rem)] sm:max-w-md sm:border-b-0',
          )}
        >
          <JarvisScreenBody
            {...screenBodyProps}
            layout="split"
            onToggleExpand={() => onOpenChange(false)}
          />
        </aside>

        <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
          {chatPanel}
        </section>
      </div>

      <p className="pointer-events-none absolute bottom-[max(0.2rem,env(safe-area-inset-bottom))] left-0 right-0 text-center text-[10px] text-muted-foreground">
        Esc — свернуть · {MODE_LABELS[agent.mode]} · тамагочи + чат
      </p>
    </div>,
    document.body,
  )
}
