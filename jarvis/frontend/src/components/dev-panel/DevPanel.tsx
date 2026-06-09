import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Server } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MemoryStores } from '@/components/dev-panel/MemoryStores'
import { DevPanelModeStores } from '@/components/dev-panel/DevPanelModeStores'
import { Hint } from '@/components/ui/hint'
import type { AgentState, VoiceSlot, XttsStatus } from '@/types'

const PANEL_STORAGE_KEY = 'jarvis-dev-panel-expanded'

interface DevPanelProps {
  agent: AgentState
  voiceSlots: VoiceSlot[]
  xtts: XttsStatus
  onBaseVoiceUploaded?: () => void
  onMemoryChange?: () => void
  onVoiceSlotUpdate?: (slot: VoiceSlot) => void
  onVoiceRefresh?: () => void
  onXttsRefresh?: () => void
  onSystemLog?: (text: string) => void
}

export function DevPanel({
  agent,
  onMemoryChange,
  onVoiceRefresh,
  onSystemLog,
}: DevPanelProps) {
  const [expanded, setExpanded] = useState(() => {
    try {
      return localStorage.getItem(PANEL_STORAGE_KEY) !== 'false'
    } catch {
      return true
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_STORAGE_KEY, String(expanded))
    } catch {
      /* ignore */
    }
  }, [expanded])

  return (
    <div className="border-b border-amber-500/25 bg-amber-500/5">
      <Hint text="Бессознательное и предобучение режимов. API-ключи, голос, АТС — в Настройках (⚙️).">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center gap-2 px-4 py-2 text-left transition-colors hover:bg-amber-500/10"
          aria-expanded={expanded}
        >
        <Server className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
        <span className="text-xs font-semibold text-foreground">
          Панель разработчика
        </span>
        <span className="text-[10px] text-muted-foreground">(только локально)</span>
        <span className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground">
          {expanded ? 'Свернуть' : 'Развернуть'}
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </span>
        </button>
      </Hint>

      {expanded && (
        <div className="max-h-[min(50dvh,520px)] space-y-2 overflow-y-auto overscroll-y-contain border-t border-amber-500/20 px-4 pb-3 pt-2 [scrollbar-gutter:stable]">
          <p className="text-[10px] text-muted-foreground">
            Бессознательное и файлы режимов — здесь. Сознательное, API-ключи, студия голоса и АТС — в «Настройках».
          </p>

          <MemoryStores
            memory={agent.memory}
            onChange={() => onMemoryChange?.()}
            onLog={onSystemLog}
          />

          <DevPanelModeStores
            memory={agent.memory}
            onMemoryChange={onMemoryChange}
            onLog={onSystemLog}
          />

          <div>
            <p className="mb-1 text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
              Журнал событий
            </p>
            <ScrollArea className="h-[48px] rounded-md border border-border/50 bg-background/50">
              <div className="space-y-0.5 p-2 font-mono text-[10px] leading-relaxed">
                {agent.toolLogs.length === 0 ? (
                  <span className="text-muted-foreground">Ожидание событий…</span>
                ) : (
                  agent.toolLogs.map((log) => (
                    <div key={log.id} className="flex gap-2 text-muted-foreground">
                      <span className="text-primary/70">{log.timestamp}</span>
                      <span className="text-foreground/80">[{log.tool}]</span>
                      <span>{log.message}</span>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>
        </div>
      )}
    </div>
  )
}
