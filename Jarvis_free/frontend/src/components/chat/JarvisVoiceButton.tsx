import { Mic, MicOff } from 'lucide-react'
import { ComposerActionRail, type ComposerRailTone } from '@/components/chat/ComposerActionRail'
import type { JarvisListenStatus } from '@/lib/jarvisWakeListen'

const VOICE_HINT: Record<JarvisListenStatus, string> = {
  off: 'Голос «Джарвис»: включить — скажите «Джарвис» и вопрос, текст попадёт в чат',
  starting: 'Подключение микрофона…',
  waiting_wake: 'Слушаю… После «Джарвис» задайте вопрос (до паузы или 10 с)',
  recording: 'Идёт запись вопроса — говорите',
  error: 'Ошибка микрофона — разрешите доступ в браузере',
}

interface JarvisVoiceButtonProps {
  voiceEnabled: boolean
  voiceListenStatus?: JarvisListenStatus
  voicePaused?: boolean
  disabled?: boolean
  onToggle: () => void
}

export function JarvisVoiceButton({
  voiceEnabled,
  voiceListenStatus = 'off',
  voicePaused = false,
  disabled,
  onToggle,
}: JarvisVoiceButtonProps) {
  const status = voiceEnabled ? voiceListenStatus : 'off'
  const isRecording = !voicePaused && status === 'recording'
  const isWaiting = !voicePaused && status === 'waiting_wake'
  const isStarting = !voicePaused && status === 'starting'
  const isError = status === 'error'
  const isPaused = voiceEnabled && voicePaused

  let tone: ComposerRailTone = 'default'
  if (isRecording) tone = 'recording'
  else if (isWaiting || isStarting) tone = 'active'
  else if (isError) tone = 'error'
  else if (isPaused) tone = 'warning'

  const hint = isPaused
    ? 'Jarvis отвечает — микрофон на паузе. Нажмите, чтобы выключить голос'
    : VOICE_HINT[status]

  const ariaLabel = isPaused
    ? 'Jarvis отвечает, выключить голос'
    : voiceEnabled
      ? 'Выключить голос «Джарвис»'
      : 'Включить голос «Джарвис»'

  const icon =
    isRecording || isWaiting || (voiceEnabled && !isError && !isPaused) ? (
      <Mic className="h-4 w-4" strokeWidth={2} />
    ) : (
      <MicOff className="h-4 w-4" strokeWidth={2} />
    )

  return (
    <ComposerActionRail
      hint={hint}
      icon={icon}
      onClick={onToggle}
      disabled={disabled}
      tone={tone}
      pressed={voiceEnabled}
      ariaLabel={ariaLabel}
    />
  )
}
