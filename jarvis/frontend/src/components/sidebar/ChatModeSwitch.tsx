import { MessageSquareText, Mic } from 'lucide-react'
import { ComposerActionRail } from '@/components/chat/ComposerActionRail'
import { Hint } from '@/components/ui/hint'
import type { ChatSurfaceMode } from '@/lib/chatSurfaceMode'
import { cn } from '@/lib/utils'

interface ChatModeSwitchProps {
  mode: ChatSurfaceMode
  disabled?: boolean
  voiceEnabled?: boolean
  voiceListenStatus?: string
  voicePaused?: boolean
  onModeChange: (mode: ChatSurfaceMode) => void
  onVoiceToggle?: () => void
}

const MODES: Array<{
  id: ChatSurfaceMode
  label: string
  hint: string
  icon: typeof MessageSquareText
}> = [
  {
    id: 'text',
    label: 'Текстовый чат',
    hint: 'Текст, файлы, картинки и лёгкая обработка изображений (crop, формат, фон).',
    icon: MessageSquareText,
  },
  {
    id: 'voice',
    label: 'Голосовой режим',
    hint: 'Hands-free: микрофон здесь, Jarvis слушает «Джарвис» или «Джа». В чат — только финальная речь.',
    icon: Mic,
  },
]

export function ChatModeSwitch({
  mode,
  disabled,
  voiceEnabled,
  voiceListenStatus = 'off',
  voicePaused,
  onModeChange,
  onVoiceToggle,
}: ChatModeSwitchProps) {
  return (
    <div
      className="rounded-xl border border-border/80 bg-card/50 p-2 shadow-sm"
      aria-label="Режим чата Jarvis"
    >
      <div
        className={cn(
          'flex w-full items-center gap-1 overflow-hidden rounded-lg border border-border/70 bg-background/60 p-0.5',
        )}
        role="group"
      >
        {MODES.map((item) => {
          const Icon = item.icon
          const active = mode === item.id
          return (
            <Hint key={item.id} text={item.hint}>
              <button
                type="button"
                disabled={disabled}
                aria-label={item.label}
                aria-pressed={active}
                onClick={() => onModeChange(item.id)}
                className={cn(
                  'inline-flex min-h-9 flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-all',
                  'hover:scale-[1.02] active:scale-[0.98]',
                  active
                    ? 'bg-primary/15 text-primary shadow-sm ring-1 ring-primary/30'
                    : 'text-muted-foreground hover:bg-muted/40',
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />
                <span className="truncate">{item.id === 'text' ? 'Текст' : 'Голос'}</span>
              </button>
            </Hint>
          )
        })}
      </div>

      {mode === 'voice' && onVoiceToggle ? (
        <div className="mt-2 flex justify-center">
          <JarvisVoiceMicToggle
            voiceEnabled={!!voiceEnabled}
            voiceListenStatus={voiceListenStatus}
            voicePaused={!!voicePaused}
            disabled={disabled}
            onToggle={onVoiceToggle}
          />
        </div>
      ) : null}
    </div>
  )
}

function JarvisVoiceMicToggle({
  voiceEnabled,
  voiceListenStatus,
  voicePaused,
  disabled,
  onToggle,
}: {
  voiceEnabled: boolean
  voiceListenStatus: string
  voicePaused: boolean
  disabled?: boolean
  onToggle: () => void
}) {
  const tone =
    voiceListenStatus === 'recording'
      ? 'recording'
      : voiceListenStatus === 'error'
        ? 'error'
        : voiceEnabled
          ? 'active'
          : 'default'

  return (
    <ComposerActionRail
      hint={
        voiceListenStatus === 'recording'
          ? 'Идёт запись — нажмите, чтобы остановить'
          : voiceListenStatus === 'waiting_wake'
            ? 'Слушаю «Джарвис» или «Джа»…'
            : voiceEnabled
              ? 'Голосовой режим включён — нажмите, чтобы выключить'
              : 'Включить микрофон Jarvis'
      }
      icon={<Mic className="h-4 w-4" strokeWidth={2} />}
      onClick={onToggle}
      disabled={disabled || voicePaused}
      tone={tone}
      pressed={voiceEnabled}
      ariaLabel="Микрофон Jarvis"
      showDivider={false}
    />
  )
}
