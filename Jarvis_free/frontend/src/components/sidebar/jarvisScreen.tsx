import { Activity, Maximize2, Minimize2 } from 'lucide-react'
import { JarvisAvatarFigure } from '@/components/JarvisAvatarFigure'
import { Badge } from '@/components/ui/badge'
import { Hint } from '@/components/ui/hint'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  insultCounterLabel,
  insultOffendedRemainingMin,
  isJarvisOffended,
} from '@/lib/jarvisInsult'
import {
  MOOD_TIER_MARKERS,
  moodHint,
  moodMarkerPercent,
  moodToneFor,
} from '@/lib/jarvisMood'
import type { JarvisMoodState } from '@/types'
import type { JarvisAvatarAnim, JarvisHealthSnapshot } from '@/lib/jarvisHealth'
import {
  READINESS_RULER_STEPS,
  STATUS_LINE_CLASS,
  type ReadinessMetric,
  type ReadinessTone,
} from '@/lib/jarvisHealth'
import { cn } from '@/lib/utils'
import type { AgentState } from '@/types'
import type { JarvisSpeechBubbleVariant } from '@/components/JarvisSpeechBubble'

const RULER_TICKS = Array.from(
  { length: READINESS_RULER_STEPS + 1 },
  (_, i) => (i * 100) / READINESS_RULER_STEPS,
)

export type JarvisScreenLayout = 'compact' | 'split'

function insultCounterHint(agent: AgentState): string {
  const threshold = agent.insult?.threshold ?? 3
  const label = insultCounterLabel(agent)
  if (isJarvisOffended(agent)) {
    const mins = insultOffendedRemainingMin(agent)
    return `Jarvis обиделся (${label}). Боеготовность прикрыта ещё ~${mins} мин. Извинитесь или подождите.`
  }
  if ((agent.insult?.sessionCount ?? 0) > 0) {
    return `Оскорбления в адрес Jarvis: ${label}. После ${threshold} — обида 30 мин.`
  }
  return `Счётчик грубости в адрес Jarvis: ${label}. Ругань «в воздух» не считается. После ${threshold} — обида 30 мин.`
}

function MoodScaleBar({
  mood,
  layout,
}: {
  mood: JarvisMoodState
  layout: JarvisScreenLayout
}) {
  const large = layout === 'split'
  const pct = moodMarkerPercent(mood.score)
  const tip = moodHint(mood)

  return (
    <Tooltip delayDuration={280}>
      <TooltipTrigger asChild>
        <div
          className="min-w-0 cursor-help space-y-0.5"
          title={tip}
          aria-label={tip}
        >
          <div className="flex items-center justify-between gap-1">
            <span
              className={cn(
                'font-medium text-primary-foreground/90',
                large ? 'text-xs' : 'text-[9px]',
              )}
            >
              Настроение
            </span>
            <span
              className={cn(
                'tabular-nums font-semibold',
                large ? 'text-xs' : 'text-[9px]',
                moodToneFor(mood),
              )}
            >
              {mood.score > 0 ? '+' : ''}
              {mood.score}
            </span>
          </div>
          <div
            className={cn(
              'relative overflow-hidden rounded-[3px] border border-primary-foreground/20 bg-gradient-to-r from-red-950/80 via-black/30 to-emerald-950/80',
              large ? 'h-2.5' : 'h-1.5',
            )}
            role="meter"
            aria-valuenow={mood.score}
            aria-valuemin={mood.min}
            aria-valuemax={mood.max}
          >
            <div
              className="pointer-events-none absolute inset-y-0 left-1/2 z-[2] w-px -translate-x-1/2 bg-primary-foreground/70"
              aria-hidden
            />
            <div
              className={cn(
                'absolute top-1/2 z-[3] h-[140%] w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full shadow-sm transition-[left] duration-500',
                mood.isCritical
                  ? 'bg-red-400'
                  : mood.isRadiant
                    ? 'bg-emerald-300'
                    : 'bg-amber-200/95',
              )}
              style={{ left: `${pct}%` }}
            />
          </div>
          <div
            className={cn(
              'flex justify-between leading-none text-primary-foreground/55',
              large ? 'text-[9px]' : 'text-[7px]',
            )}
          >
            {MOOD_TIER_MARKERS.map((m) => (
              <span key={m.tier} className="tabular-nums">
                {m.short}
              </span>
            ))}
          </div>
          <p
            className={cn(
              'truncate leading-tight',
              large ? 'text-[10px]' : 'text-[8px]',
              moodToneFor(mood),
            )}
          >
            {mood.tierLabel}
          </p>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" className="z-[250] max-w-[260px] text-[10px] leading-snug">
        {tip}
      </TooltipContent>
    </Tooltip>
  )
}

const MOOD_RESET_LABEL = 'Сбросить счётчик оскорблений'

export function MoodRestartButton({
  agent,
  onRestart,
  large = false,
}: {
  agent: AgentState
  onRestart: () => void
  large?: boolean
}) {
  if (!agent.mood?.canRestart) return null
  const tip =
    'Сбросить счётчик оскорблений (0/3), очистить историю чата и поднять настроение (+30). В чате можно написать RESTART.'

  return (
    <Tooltip delayDuration={280}>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onRestart}
          title={tip}
          aria-label={tip}
          className={cn(
            'inline-flex shrink-0 items-center justify-center rounded border border-emerald-300/45 bg-emerald-950/80 text-center font-medium normal-case leading-[1.12] text-emerald-100 hover:bg-emerald-900/90',
            large
              ? 'max-w-[9.5rem] px-2 py-1 text-[10px]'
              : 'max-w-[4.65rem] px-1 py-0.5 text-[7px]',
          )}
        >
          <span className="block whitespace-normal">{MOOD_RESET_LABEL}</span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="z-[250] max-w-[240px] text-[10px] leading-snug">
        {tip}
      </TooltipContent>
    </Tooltip>
  )
}

export function InsultCounterBadge({
  agent,
  className,
  large = false,
}: {
  agent: AgentState
  className?: string
  large?: boolean
}) {
  const offended = isJarvisOffended(agent)
  const label = insultCounterLabel(agent)
  const tip = insultCounterHint(agent)

  return (
    <Tooltip delayDuration={280}>
      <TooltipTrigger asChild>
        <button
          type="button"
          title={tip}
          aria-label={tip}
          className={cn(
            'inline-flex shrink-0 cursor-help items-center gap-0.5 rounded border font-semibold tabular-nums leading-none transition-colors',
            large ? 'px-2 py-1 text-[11px]' : 'px-1 py-px text-[8px]',
            offended
              ? 'border-red-300/50 bg-red-950/80 text-red-100 hover:bg-red-900/90'
              : (agent.insult?.sessionCount ?? 0) > 0
                ? 'border-amber-300/40 bg-amber-950/70 text-amber-100 hover:bg-amber-900/80'
                : 'border-primary-foreground/25 bg-black/40 text-primary-foreground/85 hover:bg-black/55',
            className,
          )}
        >
          <span aria-hidden>⚠</span>
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent
        side={large ? 'bottom' : 'left'}
        sideOffset={6}
        className="z-[250] max-w-[min(260px,calc(100vw-2rem))] text-[10px] leading-snug"
      >
        {tip}
      </TooltipContent>
    </Tooltip>
  )
}

function barToneClass(tone: ReadinessTone, active: boolean): string {
  if (tone === 'error') return 'bg-destructive/90'
  if (tone === 'warn') return 'bg-amber-500/95'
  if (tone === 'active' || active) return 'bg-emerald-300/95'
  if (tone === 'ok') return 'bg-emerald-500/95'
  return 'bg-primary-foreground/25'
}

export function ReadinessScaleBar({
  metric,
  layout,
}: {
  metric: ReadinessMetric
  layout: JarvisScreenLayout
}) {
  const active = metric.tone === 'active' || metric.loading
  const fill = Math.max(metric.percent > 0 ? 4 : 0, metric.percent)
  const large = layout === 'split'

  return (
    <Hint text={metric.maxHint} side="top">
      <div className="min-w-0 space-y-px">
        <p
          className={cn(
            'truncate font-medium leading-tight text-primary-foreground [text-shadow:0_1px_0_rgb(0_0_0/0.35)]',
            large
              ? metric.id === 'combat'
                ? 'text-sm font-semibold'
                : 'text-xs'
              : 'text-[9px]',
            metric.id === 'combat' && !large && 'text-[10px] font-semibold',
            metric.loading && large && 'text-emerald-100',
          )}
        >
          {metric.label}
          {metric.loading && metric.percent > 0 ? (
            <span className="ml-1 tabular-nums opacity-90">{metric.percent}%</span>
          ) : null}
        </p>
        <div
          className={cn(
            'relative overflow-hidden rounded-[3px] border border-primary-foreground/20 bg-black/20',
            large ? 'h-2' : 'h-1',
          )}
          role="progressbar"
          aria-valuenow={metric.indeterminate ? undefined : metric.percent}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          {metric.indeterminate ? (
            <div
              className="absolute inset-y-0 w-[38%] rounded-[2px] bg-emerald-300/95 animate-[qwen-load_1.35s_ease-in-out_infinite]"
              aria-hidden
            />
          ) : (
            <div
              className={cn(
                'absolute inset-y-0 left-0 z-[1] transition-[width] duration-700 ease-out',
                barToneClass(metric.tone, active),
                active && 'animate-pulse',
              )}
              style={{ width: `${fill}%` }}
            />
          )}
          {RULER_TICKS.map((at) => (
            <div
              key={`${metric.id}-ruler-${at}`}
              className="pointer-events-none absolute inset-y-0 z-[5] w-px -translate-x-1/2 bg-primary-foreground/50"
              style={{ left: `${at}%` }}
              aria-hidden
            />
          ))}
        </div>
        {metric.subline ? (
          <p
            className={cn(
              'truncate leading-tight',
              large ? 'text-[10px] text-primary-foreground/75' : 'text-[8px] text-primary-foreground/75',
            )}
          >
            {metric.subline}
          </p>
        ) : null}
      </div>
    </Hint>
  )
}

export function ScreenToolbar({
  layout,
  onToggleExpand,
  agent,
  onMoodRestart,
  showMood = true,
}: {
  layout: JarvisScreenLayout
  onToggleExpand: () => void
  agent: AgentState
  onMoodRestart?: () => void
}) {
  const large = layout === 'split'
  const expandLabel =
    layout === 'split'
      ? 'Свернуть тамагочи с чатом'
      : '2D-игра Jarvis: Chrome, полный экран'

  return (
    <div className="flex shrink-0 items-start gap-1">
      <InsultCounterBadge agent={agent} large={large} />
      {onMoodRestart ? (
        <MoodRestartButton agent={agent} large={large} onRestart={onMoodRestart} />
      ) : null}
      <Tooltip delayDuration={280}>
        <TooltipTrigger asChild>
          <button
            type="button"
            title={expandLabel}
            aria-label={expandLabel}
            onClick={onToggleExpand}
            className={cn(
              'inline-flex items-center justify-center rounded border border-primary-foreground/25 bg-black/45 text-primary-foreground shadow-sm transition-colors hover:bg-black/60',
              large ? 'h-9 w-9' : 'h-6 w-6',
            )}
          >
            {large ? (
              <Minimize2 className="h-4 w-4" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="z-[250] text-[10px]">
          {expandLabel}
        </TooltipContent>
      </Tooltip>
    </div>
  )
}

export function JarvisScreenBody({
  agentView,
  health,
  avatarAnim,
  avatarCls,
  screenCls,
  allBars,
  bubble,
  offended,
  layout,
  onToggleExpand,
  onMoodRestart,
  showMood = true,
}: {
  agentView: AgentState
  health: JarvisHealthSnapshot
  avatarAnim: JarvisAvatarAnim
  avatarCls: string
  screenCls: string
  allBars: ReadinessMetric[]
  bubble: JarvisSpeechBubbleVariant | null
  offended: boolean
  layout: JarvisScreenLayout
  onToggleExpand: () => void
  onMoodRestart?: () => void
  /** Шкала настроения скрыта в UI, логика на backend сохраняется. */
  showMood?: boolean
}) {
  const split = layout === 'split'

  return (
    <div
      className={cn(
        'relative flex h-full min-h-0 w-full flex-col overflow-hidden border-primary/30 bg-primary shadow-[inset_0_0_0_1px_rgb(255_255_255/0.06)]',
        split ? 'rounded-none border-r' : 'rounded-md border',
        screenCls,
      )}
    >
      <div
        className={cn(
          'shrink-0 border-b border-primary-foreground/15 bg-black/15',
          split ? 'px-3 py-2' : 'px-2 py-1',
        )}
      >
        <div className="flex min-w-0 items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <Hint text={health.agent.hint}>
              <div className="flex min-w-0 items-center gap-1.5">
                <span
                  className={cn(
                    'shrink-0 font-semibold uppercase tracking-wide text-primary-foreground/90',
                    split ? 'text-xs' : 'text-[9px]',
                  )}
                >
                  Агент
                </span>
                <Badge
                  variant={health.agent.variant}
                  className={cn(
                    'min-w-0 flex-1 justify-center gap-1 border-primary-foreground/20 bg-black/25 font-medium text-primary-foreground',
                    split ? 'h-8 px-2 text-sm' : 'h-[1.375rem] px-1.5 text-[10px]',
                  )}
                >
                  <Activity className={cn('shrink-0', split ? 'h-4 w-4' : 'h-3 w-3')} />
                  <span className="truncate">{health.agent.value}</span>
                </Badge>
              </div>
            </Hint>
            <p
              className={cn(
                'mt-0.5 truncate font-medium leading-snug [text-shadow:0_1px_0_rgb(0_0_0/0.25)]',
                split ? 'text-xs' : 'text-[9px]',
                STATUS_LINE_CLASS[avatarAnim],
              )}
            >
              {health.screenStatus} · {health.connectivityLabel}
              {offended ? ` · обида ~${insultOffendedRemainingMin(agentView)} мин` : ''}
            </p>
          </div>
          <ScreenToolbar
            layout={layout}
            onToggleExpand={onToggleExpand}
            agent={agentView}
            onMoodRestart={onMoodRestart}
          />
        </div>
      </div>

      <div
        className={cn(
          'relative flex min-h-0 flex-1 items-center justify-center overflow-visible',
          split ? 'py-2' : 'min-h-[5.25rem] py-1',
        )}
      >
        <JarvisAvatarFigure
          anim={avatarAnim}
          bubble={bubble}
          alt=""
          avatarClassName={cn(
            'max-h-full max-w-full object-contain',
            split
              ? 'h-[min(36vh,16rem)] w-[min(36vh,16rem)]'
              : 'h-[4.25rem] w-[4.25rem]',
            avatarCls,
          )}
        />
      </div>

      <div
        className={cn(
          'shrink-0 border-t border-primary-foreground/10 bg-black/10',
          split
            ? 'w-1/2 max-w-[50%] overflow-y-auto border-r border-primary-foreground/10 px-2 py-2'
            : 'flex flex-col gap-0.5 px-2 py-1',
        )}
      >
        {showMood && agentView.mood ? (
          <div className={split ? 'mb-2' : 'mb-1'}>
            <MoodScaleBar mood={agentView.mood} layout={layout} />
          </div>
        ) : null}
        {allBars.map((m) => (
          <ReadinessScaleBar key={m.id} metric={m} layout={layout} />
        ))}
      </div>
    </div>
  )
}
