import { Activity, ExternalLink, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Hint } from '@/components/ui/hint'
import {
  InsultCounterBadge,
  MoodRestartButton,
  ReadinessScaleBar,
  type JarvisScreenLayout,
} from '@/components/sidebar/jarvisScreen'
import { insultOffendedRemainingMin, isJarvisOffended } from '@/lib/jarvisInsult'
import { STATUS_LINE_CLASS, type JarvisAvatarAnim, type JarvisHealthSnapshot, type ReadinessMetric } from '@/lib/jarvisHealth'
import { cn } from '@/lib/utils'
import type { AgentState } from '@/types'

export function JarvisGameTopPanel({
  agentView,
  health,
  avatarAnim,
  allBars,
  onMoodRestart,
  onCloseGame,
  onOpenMainUi,
}: {
  agentView: AgentState
  health: JarvisHealthSnapshot
  avatarAnim: JarvisAvatarAnim
  allBars: ReadinessMetric[]
  onMoodRestart?: () => void
  onCloseGame: () => void
  onOpenMainUi: () => void
}) {
  const layout: JarvisScreenLayout = 'split'
  const offended = isJarvisOffended(agentView)

  return (
    <header className="shrink-0 border-b border-border bg-primary px-3 py-2 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1 space-y-1">
          <Hint text={health.agent.hint}>
            <div className="flex min-w-0 items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-primary-foreground/90">
                Jarvis · 2D
              </span>
              <Badge
                variant={health.agent.variant}
                className="h-7 gap-1 border-primary-foreground/20 bg-black/25 text-xs text-primary-foreground"
              >
                <Activity className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{health.agent.value}</span>
              </Badge>
            </div>
          </Hint>
          <p
            className={cn(
              'truncate text-xs font-medium',
              STATUS_LINE_CLASS[avatarAnim],
            )}
          >
            {health.screenStatus} · {health.connectivityLabel}
            {offended ? ` · обида ~${insultOffendedRemainingMin(agentView)} мин` : ''}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-start justify-end gap-1">
          <InsultCounterBadge agent={agentView} large />
          {onMoodRestart ? (
            <MoodRestartButton agent={agentView} large onRestart={onMoodRestart} />
          ) : null}
          <button
            type="button"
            title="Открыть основной интерфейс Jarvis"
            aria-label="Открыть основной интерфейс Jarvis"
            onClick={onOpenMainUi}
            className="inline-flex h-9 w-9 items-center justify-center rounded border border-primary-foreground/25 bg-black/45 text-primary-foreground hover:bg-black/60"
          >
            <ExternalLink className="h-4 w-4" />
          </button>
          <button
            type="button"
            title="Закрыть окно игры"
            aria-label="Закрыть окно игры"
            onClick={onCloseGame}
            className="inline-flex h-9 w-9 items-center justify-center rounded border border-primary-foreground/25 bg-black/45 text-primary-foreground hover:bg-black/60"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-3 lg:grid-cols-6">
        {allBars.map((m) => (
          <ReadinessScaleBar key={m.id} metric={m} layout={layout} />
        ))}
      </div>
    </header>
  )
}
