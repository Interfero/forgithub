import type { AgentState } from '@/types'

export function isJarvisOffended(agent: AgentState): boolean {
  return Boolean(agent.insult?.offended)
}

export function isJarvisAngry(agent: AgentState): boolean {
  const i = agent.insult
  if (!i) return false
  if (i.angryUntil != null && i.angryUntil > Date.now()) return true
  return isJarvisOffended(agent)
}

export function insultOffendedRemainingMin(agent: AgentState): number {
  const sec = agent.insult?.offendedRemainingSec ?? 0
  return Math.max(0, Math.ceil(sec / 60))
}

export function insultCounterLabel(agent: AgentState): string {
  const n = agent.insult?.sessionCount ?? 0
  const max = agent.insult?.threshold ?? 3
  return `${n}/${max}`
}
