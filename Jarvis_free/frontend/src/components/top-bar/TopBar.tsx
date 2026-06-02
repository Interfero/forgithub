import { useCallback, useState } from 'react'
import { Hint } from '@/components/ui/hint'
import { DevPanelShell } from '@/components/dev-panel/DevPanelShell'
import { AgentStatusBar } from '@/components/top-bar/AgentStatusBar'
import { ModeSwitch } from '@/components/top-bar/ModeSwitch'
import { Button } from '@/components/ui/button'
import { restartJarvis, waitForBackendAfterRestart } from '@/api/client'
import { APP_BUILD } from '@/version'
import { cn } from '@/lib/utils'
import type { AgentMode, AgentState, VoiceSlot, XttsStatus } from '@/types'

interface TopBarProps {
  agent: AgentState
  mode: AgentMode
  onModeChange: (mode: AgentMode) => void
  voiceSlots: VoiceSlot[]
  xtts: XttsStatus
  onBaseVoiceUploaded?: () => void
  onMemoryChange?: () => void
  onVoiceSlotUpdate?: (slot: VoiceSlot) => void
  onVoiceRefresh?: () => void
  onXttsRefresh?: () => void
  onSystemLog?: (text: string) => void
}

export function TopBar({
  agent,
  mode,
  onModeChange,
  voiceSlots,
  xtts,
  onBaseVoiceUploaded,
  onMemoryChange,
  onVoiceSlotUpdate,
  onVoiceRefresh,
  onXttsRefresh,
  onSystemLog,
}: TopBarProps) {
  const [restarting, setRestarting] = useState(false)

  const handleRestart = useCallback(async () => {
    if (restarting) return
    setRestarting(true)
    onSystemLog?.('🔄 **RESTART** — сборка интерфейса и перезапуск сервера (как `restart.bat`)…')
    try {
      await restartJarvis()
    } catch (e) {
      onSystemLog?.(
        `❌ Не удалось запустить перезапуск: ${e instanceof Error ? e.message : 'ошибка'}`,
      )
      setRestarting(false)
      return
    }
    const ok = await waitForBackendAfterRestart()
    if (ok) {
      onSystemLog?.('✅ Jarvis перезапущен — обновляю страницу')
      window.location.reload()
      return
    }
    onSystemLog?.('⚠️ Сервер не ответил вовремя. Смотрите `logs\\restart.log` и `logs\\frontend-build.log`')
    setRestarting(false)
  }, [onSystemLog, restarting])

  return (
    <div className="flex min-h-0 shrink-0 flex-col border-b border-border bg-card/80 backdrop-blur-md">
      <DevPanelShell
        agent={agent}
        voiceSlots={voiceSlots}
        xtts={xtts}
        onBaseVoiceUploaded={onBaseVoiceUploaded}
        onMemoryChange={onMemoryChange}
        onVoiceSlotUpdate={onVoiceSlotUpdate}
        onVoiceRefresh={onVoiceRefresh}
        onXttsRefresh={onXttsRefresh}
        onSystemLog={onSystemLog}
      />

      <div className="shrink-0 border-b border-border/30 bg-card/40 px-3 py-1">
        <div className="flex min-h-0 items-center justify-end gap-2">
          <Hint text="Версия фронтенд-сборки — после RESTART должна совпасть с последними изменениями">
            <span className="shrink-0 cursor-default whitespace-nowrap font-mono text-[9px] leading-none text-muted-foreground/80">
              build {APP_BUILD}
            </span>
          </Hint>

          <div className="hidden" aria-hidden="true">
            <ModeSwitch
              mode={mode}
              onModeChange={onModeChange}
              deepseekConfigured={agent.deepseekConfigured}
              nanobananaConfigured={agent.nanobananaConfigured}
              perplexityConfigured={agent.perplexityConfigured}
              perplexityUsable={agent.perplexityUsable}
            />
          </div>

          <Hint text="Пересобрать UI и перезапустить backend (restart.bat) — не нужно открывать папку Jarvis">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={restarting}
              onClick={() => void handleRestart()}
              className={cn(
                'h-7 shrink-0 rounded-md border-primary/40 px-2.5 py-0 font-mono text-[10px] font-semibold leading-none tracking-wider',
                restarting && 'animate-pulse opacity-70',
              )}
            >
              {restarting ? '…' : 'RESTART'}
            </Button>
          </Hint>
        </div>
      </div>

      <AgentStatusBar agent={agent} mode={mode} />
    </div>
  )
}
