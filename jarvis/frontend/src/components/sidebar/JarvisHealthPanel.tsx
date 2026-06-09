import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Power } from 'lucide-react'
import { SimulatedChatPreview } from '@/components/game/SimulatedChatPreview'
import { Hint } from '@/components/ui/hint'
import { JarvisScreenBody } from '@/components/sidebar/jarvisScreen'
import { useJarvisScreenModel } from '@/hooks/useJarvisScreenModel'
import { cn } from '@/lib/utils'
import type { AgentState, Message } from '@/types'
import { MODE_LABELS } from '@/types'

const ENABLED_KEY = 'jarvis-sidebar-panel-enabled'
const COLLAPSED_KEY = 'jarvis-sidebar-panel-collapsed'

function readEnabled(): boolean {
  try {
    return localStorage.getItem(ENABLED_KEY) !== '0'
  } catch {
    return true
  }
}

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

function JarvisPanelChrome({
  enabled,
  collapsed,
  onToggleEnabled,
  onToggleCollapse,
}: {
  enabled: boolean
  collapsed: boolean
  onToggleEnabled: () => void
  onToggleCollapse: () => void
}) {
  const canCollapse = !enabled
  const expandLabel = collapsed ? 'Развернуть заголовок панели' : 'Свернуть заголовок панели'

  return (
    <div className="flex items-center gap-1.5">
      <Hint
        text={
          enabled
            ? 'Выключить панель Jarvis — остановит анимации и опрос RAM (экономия ресурсов).'
            : 'Включить панель Jarvis — статус, шкалы и экран тамагочи.'
        }
      >
        <button
          type="button"
          onClick={onToggleEnabled}
          aria-pressed={enabled}
          aria-label={enabled ? 'Выключить панель Jarvis' : 'Включить панель Jarvis'}
          className={cn(
            'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border transition-colors',
            enabled
              ? 'border-amber-500/50 bg-amber-950/80 text-amber-200 hover:bg-amber-900/90'
              : 'border-border bg-muted/50 text-muted-foreground hover:bg-muted',
          )}
        >
          <Power className={cn('h-3.5 w-3.5', enabled && 'drop-shadow-[0_0_4px_rgba(251,191,36,0.5)]')} />
        </button>
      </Hint>
      <span className="min-w-0 flex-1 truncate text-[10px] font-semibold uppercase tracking-wide text-foreground/90">
        Jarvis
      </span>
      {canCollapse ? (
        <Hint text={expandLabel}>
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-expanded={!collapsed}
            aria-label={expandLabel}
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border bg-muted/40 text-muted-foreground hover:bg-muted/70"
          >
            {collapsed ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronUp className="h-3.5 w-3.5" />
            )}
          </button>
        </Hint>
      ) : (
        <Hint text="Свернуть можно только после выключения панели (кнопка питания).">
          <span
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-transparent opacity-35"
            aria-hidden
          >
            <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          </span>
        </Hint>
      )}
    </div>
  )
}

/** Тяжёлый экран — только когда панель включена. */
function JarvisHealthPanelActive({
  agent,
  connected,
  chatMessages,
  onExpandFullscreen,
  onMoodRestart,
}: {
  agent: AgentState
  connected: boolean
  chatMessages: Message[]
  onExpandFullscreen?: () => void
  onMoodRestart?: () => void
}) {
  const model = useJarvisScreenModel(agent, chatMessages, connected)

  return (
    <>
      <Hint
        text={`${MODE_LABELS[agent.mode]} · ${model.health.connectivityLabel}. Развернуть — 2D-игра Jarvis в Chrome (полный экран).`}
      >
        <JarvisScreenBody
          {...model.screenBodyProps}
          layout="compact"
          showMood={false}
          onToggleExpand={() => onExpandFullscreen?.()}
          onMoodRestart={onMoodRestart}
        />
      </Hint>
      <SimulatedChatPreview messages={chatMessages} className="mt-1.5" />
      <p className="text-center text-[9px] text-muted-foreground">
        {MODE_LABELS[agent.mode]}
      </p>
    </>
  )
}

export function JarvisHealthPanel({
  agent,
  connected = true,
  chatMessages = [],
  onExpandFullscreen,
  onMoodRestart,
}: {
  agent: AgentState
  connected?: boolean
  chatMessages?: Message[]
  onExpandFullscreen?: () => void
  onMoodRestart?: () => void
}) {
  const [enabled, setEnabled] = useState(readEnabled)
  const [collapsed, setCollapsed] = useState(() => {
    const on = readEnabled()
    return on ? false : readCollapsed()
  })

  useEffect(() => {
    try {
      localStorage.setItem(ENABLED_KEY, enabled ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [enabled])

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [collapsed])

  const toggleEnabled = useCallback(() => {
    setEnabled((on) => {
      const next = !on
      if (next) setCollapsed(false)
      return next
    })
  }, [])

  const toggleCollapse = useCallback(() => {
    if (enabled) return
    setCollapsed((v) => !v)
  }, [enabled])

  const showBody = enabled && !collapsed
  const showOffHint = !enabled && !collapsed

  return (
    <div className="space-y-1.5">
      <JarvisPanelChrome
        enabled={enabled}
        collapsed={collapsed}
        onToggleEnabled={toggleEnabled}
        onToggleCollapse={toggleCollapse}
      />

      <div
        className={cn(
          'grid transition-[grid-template-rows] duration-200 ease-out',
          showBody || showOffHint ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="min-h-0 overflow-hidden">
          {showBody ? (
            <div className="space-y-1.5 pt-0.5">
              <JarvisHealthPanelActive
                agent={agent}
                connected={connected}
                chatMessages={chatMessages}
                onExpandFullscreen={onExpandFullscreen}
                onMoodRestart={onMoodRestart}
              />
            </div>
          ) : showOffHint ? (
            <p className="pt-1 text-[10px] leading-snug text-muted-foreground">
              Панель выключена — анимации и опрос ОЗУ не выполняются. Сверните заголовок стрелкой или
              включите питание.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
