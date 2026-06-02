import { isJarvisAngry, isJarvisOffended } from '@/lib/jarvisInsult'
import { isQwenDownloading } from '@/lib/statusIndicators'
import type { JarvisAvatarAnim } from '@/lib/jarvisHealth'
import type { AgentState } from '@/types'

/** Подключение, скачивание Qwen / Chromium / XTTS, загрузка в ОЗУ. */
export function isAgentLoadingModules(agent: AgentState): boolean {
  if (agent.backendStatus === 'connecting') return true
  if (agent.backendStatus !== 'connected') return false

  const q = agent.qwen
  if (isQwenDownloading(q)) return true
  if (
    q.ramPhase === 'loading' ||
    q.ramPhase === 'pending' ||
    q.status === 'loading_ram' ||
    q.status === 'downloading'
  ) {
    return true
  }

  const ch = agent.chromiumBrowser
  if (ch.installInProgress) {
    return true
  }

  const x = agent.xtts
  if (x.status === 'installing_deps' || x.status === 'downloading_model') {
    return true
  }

  if (agent.ramUsage.launching) return true

  return false
}

export function resolveJarvisAvatarAnim(
  agent: AgentState,
  options?: { angry?: boolean },
): JarvisAvatarAnim {
  if (options?.angry || isJarvisAngry(agent) || isJarvisOffended(agent)) return 'angry'

  if (agent.backendStatus !== 'connected') {
    return agent.backendStatus === 'connecting' ? 'loading' : 'offline'
  }

  if (agent.status === 'Listening...' || agent.voiceListening) return 'listen'
  switch (agent.status) {
    case 'Thinking...':
      return 'think'
    case 'Searching Web...':
      return 'search'
    case 'Generating image...':
      return 'image'
    default:
      break
  }

  if (isAgentLoadingModules(agent)) return 'loading'

  const q = agent.qwen
  const core =
    (agent.qwen.ramEnabled && (q.ready || q.ollamaModelLoaded)) ||
    agent.deepseekUsable ||
    agent.deepseekConfigured
  const chOk = agent.chromiumBrowser.ready

  if (!core || !chOk) return 'corePending'

  return 'idle'
}
