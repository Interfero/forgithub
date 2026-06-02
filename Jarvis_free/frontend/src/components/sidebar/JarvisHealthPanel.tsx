import { SimulatedChatPreview } from '@/components/game/SimulatedChatPreview'
import { Hint } from '@/components/ui/hint'
import { JarvisScreenBody } from '@/components/sidebar/jarvisScreen'
import { useJarvisScreenModel } from '@/hooks/useJarvisScreenModel'
import type { AgentState, Message } from '@/types'
import { MODE_LABELS } from '@/types'

export function JarvisHealthPanel({
  agent,
  connected = true,
  chatMessages = [],
  onExpandFullscreen,
  onMoodRestart,
}: {
  agent: AgentState
  connected?: boolean
  chatMessages?: Message[]
  onExpandFullscreen?: () => void
  onMoodRestart?: () => void
}) {
  const model = useJarvisScreenModel(agent, chatMessages, connected)

  return (
    <div className="space-y-1.5">
      <Hint
        text={`${MODE_LABELS[agent.mode]} · ${model.health.connectivityLabel}. Развернуть — 2D-игра Jarvis в Chrome (полный экран).`}
      >
        <JarvisScreenBody
          {...model.screenBodyProps}
          layout="compact"
          showMood={false}
          onToggleExpand={() => onExpandFullscreen?.()}
          onMoodRestart={onMoodRestart}
        />
      </Hint>
      <SimulatedChatPreview messages={chatMessages} className="mt-1.5" />
      <p className="text-center text-[9px] text-muted-foreground">
        {MODE_LABELS[agent.mode]}
      </p>
    </div>
  )
}
