import { useEffect, useState } from 'react'
import { isJarvisAngry } from '@/lib/jarvisInsult'
import type { AgentState } from '@/types'

/** Качание аватара: короткая вспышка после оскорбления или режим обиды. */
export function useJarvisAngryReaction(agent: AgentState): boolean {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const i = agent.insult
    if (!i?.angryUntil && !i?.offendedUntil) return
    const targets = [i.angryUntil, i.offendedUntil].filter(
      (t): t is number => t != null && t > Date.now(),
    )
    if (!targets.length) return
    const next = Math.min(...targets) - Date.now()
    const t = window.setTimeout(() => setTick((n) => n + 1), Math.max(200, next))
    return () => window.clearTimeout(t)
  }, [agent.insult?.angryUntil, agent.insult?.offendedUntil, tick])

  return isJarvisAngry(agent)
}
