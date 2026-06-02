import type { JarvisMoodState, JarvisMoodTier } from '@/types'

export const MOOD_MIN = -50
export const MOOD_MAX = 50

export const MOOD_TIER_MARKERS: { tier: JarvisMoodTier; at: number; short: string }[] = [
  { tier: 'critical', at: -50, short: '−50' },
  { tier: 'chilly', at: -28, short: '−28' },
  { tier: 'neutral', at: 0, short: '0' },
  { tier: 'warm', at: 28, short: '+28' },
  { tier: 'radiant', at: 50, short: '+50' },
]

export function mapMoodFromApi(d: {
  score?: number
  min?: number
  max?: number
  tier?: string
  tier_label?: string
  can_restart?: boolean
  is_critical?: boolean
  is_radiant?: boolean
} | null | undefined): JarvisMoodState {
  const score = d?.score ?? 0
  return {
    score,
    min: d?.min ?? MOOD_MIN,
    max: d?.max ?? MOOD_MAX,
    tier: (d?.tier as JarvisMoodTier) ?? 'neutral',
    tierLabel: d?.tier_label ?? 'Нейтрально',
    canRestart: d?.can_restart ?? false,
    isCritical: d?.is_critical ?? score <= -36,
    isRadiant: d?.is_radiant ?? score >= 36,
  }
}

export function moodMarkerPercent(score: number): number {
  return ((score - MOOD_MIN) / (MOOD_MAX - MOOD_MIN)) * 100
}

export function moodHint(mood?: JarvisMoodState | null): string {
  if (!mood) return 'Настроение Jarvis: от −50 (критично) до +50 (радость).'
  return `Настроение: ${mood.score > 0 ? '+' : ''}${mood.score} — ${mood.tierLabel}. Оскорбление −30, похвала +30, RESTART +30.`
}

export function moodToneFor(mood: JarvisMoodState): string {
  if (mood.isCritical) return 'text-red-200'
  if (mood.tier === 'chilly' || mood.tier === 'reserved') return 'text-sky-200/90'
  if (mood.isRadiant) return 'text-emerald-100'
  if (mood.tier === 'warm' || mood.tier === 'pleasant') return 'text-emerald-200/95'
  return 'text-primary-foreground/85'
}
