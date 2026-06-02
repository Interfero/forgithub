import { useEffect, useRef, useState } from 'react'
import type { JarvisSpeechBubbleVariant } from '@/components/JarvisSpeechBubble'
import type { AgentState, Message } from '@/types'

const IDLE_SLEEP_MS = 5 * 60 * 1000
const TICK_MS = 15_000

function latestUserActivityMs(messages: Message[]): number {
  let t = 0
  for (const m of messages) {
    if (m.role !== 'user') continue
    const ts = Date.parse(m.createdAt)
    if (!Number.isNaN(ts) && ts > t) t = ts
  }
  return t
}

/** ? при размышлении; ZzZ после 5+ мин без активности (если не думает). */
export function useJarvisSpeechBubble(
  agent: AgentState,
  isThinking: boolean,
  messages: Message[],
  connected: boolean,
): JarvisSpeechBubbleVariant | null {
  const lastActivityRef = useRef(Date.now())
  const [sleeping, setSleeping] = useState(false)

  const thinking =
    isThinking ||
    agent.status === 'Thinking...' ||
    agent.status === 'Searching...' ||
    agent.status === 'Generating image...'

  useEffect(() => {
    if (thinking) lastActivityRef.current = Date.now()
  }, [thinking])

  useEffect(() => {
    const fromMsgs = latestUserActivityMs(messages)
    if (fromMsgs > 0) lastActivityRef.current = Math.max(lastActivityRef.current, fromMsgs)
  }, [messages])

  useEffect(() => {
    const tick = () => {
      const idle = Date.now() - lastActivityRef.current >= IDLE_SLEEP_MS
      const backendUp = connected && agent.backendStatus !== 'offline'
      setSleeping(idle && backendUp && !thinking)
    }
    tick()
    const id = window.setInterval(tick, TICK_MS)
    return () => window.clearInterval(id)
  }, [thinking, connected, agent.backendStatus, messages.length])

  if (thinking) return 'think'
  if (sleeping) return 'sleep'
  return null
}
