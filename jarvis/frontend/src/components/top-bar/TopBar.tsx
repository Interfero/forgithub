import { useCallback, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Hint } from '@/components/ui/hint'
import { DevPanelShell } from '@/components/dev-panel/DevPanelShell'
import { AgentStatusBar } from '@/components/top-bar/AgentStatusBar'
import { JarvisRestartOverlay } from '@/components/top-bar/JarvisRestartOverlay'
import { ModeSwitch } from '@/components/top-bar/ModeSwitch'
import { Button } from '@/components/ui/button'
import {
  restartJarvis,
  restartPhaseLabel,
  waitForBackendAfterRestart,
} from '@/api/client'
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
  const [restartStartedAt, setRestartStartedAt] = useState<number | null>(null)
  const lastLogSecRef = useRef(-1)

  const handleRestart = useCallback(async () => {
    if (restarting) return
    const started = Date.now()
    setRestartStartedAt(started)
    setRestarting(true)
    lastLogSecRef.current = -1
    onSystemLog?.('🔄 **RESTART** — команда отправлена, открывается окно перезапуска…')

    try {
      await restartJarvis()
      onSystemLog?.('🔄 Сервер принял перезапуск — сборка UI и запуск backend…')
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'ошибка'
      const likelyShutdown =
        /failed to fetch|network|abort|load failed|соединен/i.test(msg)
      if (likelyShutdown) {
        onSystemLog?.('🔄 Сервер остановлен — идёт `restart.bat` (это нормально)…')
      } else {
        onSystemLog?.(`⚠️ ${msg} — всё равно жду возврат backend…`)
      }
    }

    const ok = await waitForBackendAfterRestart(180_000, 2000, ({ elapsedMs }) => {
      const sec = Math.floor(elapsedMs / 1000)
      if (sec > 0 && sec % 12 === 0 && sec !== lastLogSecRef.current) {
        lastLogSecRef.current = sec
        onSystemLog?.(`⏳ ${restartPhaseLabel(elapsedMs)} (${sec} с)`)
      }
    })

    if (ok) {
      onSystemLog?.('✅ Jarvis снова на связи — обновляю страницу…')
      window.location.reload()
      return
    }
    onSystemLog?.(
      '⚠️ Сервер не ответил за 3 мин. Проверьте `logs\\restart.log` и `logs\\frontend-build.log`, затем `start.bat`.',
    )
    setRestarting(false)
    setRestartStartedAt(null)
  }, [onSystemLog, restarting])

  return (
    <>
      <JarvisRestartOverlay active={restarting} startedAt={restartStartedAt} />
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
        <div className="flex min-h-0 items-center gap-2">
          <Hint text="Версия фронтенд-сборки — после RESTART должна совпасть с последними изменениями">
            <span className="shrink-0 cursor-default whitespace-nowrap font-mono text-[9px] leading-none text-muted-foreground/80">
              build {APP_BUILD}
            </span>
          </Hint>

          <ModeSwitch
            mode={mode}
            onModeChange={onModeChange}
            deepseekConfigured={agent.deepseekConfigured}
            nanobananaConfigured={agent.nanobananaConfigured}
            perplexityConfigured={agent.perplexityConfigured}
            perplexityUsable={agent.perplexityUsable}
            className="min-h-0 min-w-0 flex-1"
          />

          <Hint text="Пересобрать UI и перезапустить backend (restart.bat) — не нужно открывать папку Jarvis">
            <Button
              type="button"
              variant={restarting ? 'default' : 'outline'}
              size="sm"
              disabled={restarting}
              onClick={() => void handleRestart()}
              className={cn(
                'h-7 shrink-0 gap-1 rounded-md px-2.5 py-0 font-mono text-[10px] font-semibold leading-none tracking-wider',
                restarting
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-primary/40',
              )}
            >
              {restarting ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                  Идёт…
                </>
              ) : (
                'RESTART'
              )}
            </Button>
          </Hint>
        </div>
      </div>

      <AgentStatusBar agent={agent} mode={mode} />
    </div>
    </>
  )
}
