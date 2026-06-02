import { useEffect, useMemo, useState } from 'react'
import { fetchJarvisRam } from '@/api/client'
import { useJarvisAngryReaction } from '@/hooks/useJarvisAngryReaction'
import { useJarvisSpeechBubble } from '@/hooks/useJarvisSpeechBubble'
import { resolveJarvisAvatarAnim } from '@/lib/jarvisAvatarAnim'
import { isJarvisOffended } from '@/lib/jarvisInsult'
import {
  AVATAR_ANIM_CLASS,
  buildJarvisHealth,
  SCREEN_ANIM_CLASS,
  type JarvisAvatarAnim,
} from '@/lib/jarvisHealth'
import type { AgentState, Message } from '@/types'

function isRamLoadActive(agent: AgentState): boolean {
  const r = agent.ramUsage
  if (r.qwenRamLoading) return true
  if (!agent.qwen.ramEnabled) return false
  return (
    agent.qwen.ramPhase === 'loading' ||
    agent.qwen.ramPhase === 'pending' ||
    agent.qwen.status === 'loading_ram'
  )
}

/** Данные экрана Jarvis (компакт и полноэкранный тамагочи+чат). */
export function useJarvisScreenModel(
  agent: AgentState,
  chatMessages: Message[],
  connected: boolean,
) {
  const [liveRam, setLiveRam] = useState(agent.ramUsage)
  const ramActive = isRamLoadActive(agent)

  useEffect(() => {
    if (!ramActive || agent.backendStatus !== 'connected') {
      setLiveRam(agent.ramUsage)
      return
    }
    let cancelled = false
    const poll = async () => {
      try {
        const snap = await fetchJarvisRam()
        if (!cancelled) setLiveRam(snap)
      } catch {
        /* ignore */
      }
    }
    void poll()
    const id = window.setInterval(() => void poll(), 1000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [ramActive, agent.backendStatus, agent.ramUsage])

  const agentView = useMemo(
    () => (ramActive ? { ...agent, ramUsage: liveRam } : agent),
    [agent, liveRam, ramActive],
  )

  const health = useMemo(() => buildJarvisHealth(agentView), [agentView])
  const angry = useJarvisAngryReaction(agentView)
  const avatarAnim: JarvisAvatarAnim = useMemo(
    () => resolveJarvisAvatarAnim(agentView, { angry }),
    [agentView, angry],
  )
  const offended = isJarvisOffended(agentView)
  const avatarCls = AVATAR_ANIM_CLASS[avatarAnim]
  const screenCls = SCREEN_ANIM_CLASS[avatarAnim]
  const allBars = useMemo(
    () => [health.combat, ...health.metrics],
    [health.combat, health.metrics],
  )
  const thinking =
    agent.status === 'Thinking...' ||
    agent.status === 'Searching...' ||
    agent.status === 'Generating image...'
  const bubble = useJarvisSpeechBubble(agent, thinking, chatMessages, connected)

  const screenBodyProps = useMemo(
    () => ({
      agentView,
      health,
      avatarAnim,
      avatarCls,
      screenCls,
      allBars,
      bubble,
      offended,
    }),
    [agentView, health, avatarAnim, avatarCls, screenCls, allBars, bubble, offended],
  )

  return {
    agent,
    agentView,
    health,
    screenBodyProps,
  }
}
