import { Settings } from 'lucide-react'
import { JarvisHealthPanel } from '@/components/sidebar/JarvisHealthPanel'
import { ChatModeSwitch } from '@/components/sidebar/ChatModeSwitch'
import { OpenConnectVpnPanel } from '@/components/sidebar/OpenConnectVpnPanel'
import { MenuSearch } from '@/components/menu/MenuSearch'
import { Hint } from '@/components/ui/hint'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import type { ChatSurfaceMode } from '@/lib/chatSurfaceMode'
import type { JarvisListenStatus } from '@/lib/jarvisWakeListen'
import type { AgentState, Message } from '@/types'

export interface MenuNavigatePayload {
  sectionDomId: string
  label: string
}

interface SidebarProps {
  agent: AgentState
  connected?: boolean
  chatMessages?: Message[]
  onOpenSettings: () => void
  onSystemLog?: (text: string) => void
  onMenuNavigate: (payload: MenuNavigatePayload) => void
  onExpandJarvisFullscreen?: () => void
  onMoodRestart?: () => void
  chatSurfaceMode?: ChatSurfaceMode
  onChatSurfaceModeChange?: (mode: ChatSurfaceMode) => void
  jarvisVoiceOn?: boolean
  voiceListenStatus?: JarvisListenStatus
  voicePaused?: boolean
  onVoiceToggle?: () => void
}

export function Sidebar({
  agent,
  connected = false,
  chatMessages = [],
  onOpenSettings,
  onSystemLog,
  onMenuNavigate,
  onExpandJarvisFullscreen,
  onMoodRestart,
  chatSurfaceMode = 'text',
  onChatSurfaceModeChange,
  jarvisVoiceOn,
  voiceListenStatus = 'off',
  voicePaused = false,
  onVoiceToggle,
}: SidebarProps) {
  return (
    <aside className="flex w-[300px] shrink-0 flex-col border-r border-border bg-sidebar">
      <div className="border-b border-border px-3 py-3">
        <JarvisHealthPanel
          agent={agent}
          connected={connected}
          chatMessages={chatMessages}
          onExpandFullscreen={onExpandJarvisFullscreen}
          onMoodRestart={onMoodRestart}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 px-3 py-4">
        <MenuSearch onNavigate={onMenuNavigate} />
        <p className="text-xs leading-relaxed text-muted-foreground">
          Один диалог с Jarvis. Текстовые файлы в{' '}
          <strong className="font-medium text-foreground">Сознательное</strong> — над полем ввода в чате
          (.txt, .md, .json).
        </p>
      </div>

      <Separator />

      <div className="flex shrink-0 flex-col gap-3 border-t border-border bg-sidebar p-3">
        {onChatSurfaceModeChange ? (
          <ChatModeSwitch
            mode={chatSurfaceMode}
            disabled={!connected}
            voiceEnabled={jarvisVoiceOn}
            voiceListenStatus={voiceListenStatus}
            voicePaused={voicePaused}
            onModeChange={onChatSurfaceModeChange}
            onVoiceToggle={onVoiceToggle}
          />
        ) : null}
        <OpenConnectVpnPanel onSystemLog={onSystemLog} />
        <Hint text="Все параметры: дерево разделов и поиск внутри">
          <Button variant="ghost" className="w-full justify-start gap-2" size="sm" onClick={onOpenSettings}>
            <Settings className="h-4 w-4" />
            Настройки
          </Button>
        </Hint>
      </div>
    </aside>
  )
}
