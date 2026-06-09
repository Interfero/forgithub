import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Loader2 } from 'lucide-react'
import { restartPhaseLabel } from '@/api/client'

interface JarvisRestartOverlayProps {
  active: boolean
  startedAt: number | null
}

export function JarvisRestartOverlay({ active, startedAt }: JarvisRestartOverlayProps) {
  const [elapsedMs, setElapsedMs] = useState(0)

  useEffect(() => {
    if (!active || startedAt == null) {
      setElapsedMs(0)
      return
    }
    const tick = () => setElapsedMs(Date.now() - startedAt)
    tick()
    const id = window.setInterval(tick, 500)
    return () => window.clearInterval(id)
  }, [active, startedAt])

  if (!active || startedAt == null) return null

  const sec = Math.floor(elapsedMs / 1000)
  const phase = restartPhaseLabel(elapsedMs)

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-background/85 backdrop-blur-md"
      role="alertdialog"
      aria-modal="true"
      aria-busy="true"
      aria-label="Перезапуск Jarvis"
    >
      <div className="mx-4 w-full max-w-md animate-in fade-in zoom-in-95 rounded-xl border-2 border-primary/50 bg-card px-6 py-8 shadow-2xl duration-200">
        <div className="flex flex-col items-center text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary" aria-hidden />
          <h2 className="mt-5 text-lg font-semibold tracking-tight">Перезапуск Jarvis</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Команда принята — идёт <code className="rounded bg-muted px-1 text-xs">restart.bat</code>
            . Не закрывайте окно.
          </p>
          <p className="mt-4 text-sm font-medium text-foreground">{phase}</p>
          <p className="mt-2 font-mono text-xs tabular-nums text-muted-foreground">
            прошло {sec} с
          </p>
          <div className="mt-5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
              style={{ width: `${Math.min(95, 8 + sec * 1.2)}%` }}
            />
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
