import { useEffect, useRef } from 'react'
import { isChatVisibleNotification } from '@/lib/notifications'
import {
  speakChatMessage,
  stopChatSpeechPlayback,
  unlockChatSpeechPlayback,
} from '@/lib/chatSpeech'
import type { Message } from '@/types'

function shouldSpeakMessage(msg: Message, skipUserVoice: boolean): boolean {
  const text = msg.content.trim()
  if (text.length < 2) return false
  if (skipUserVoice && msg.role === 'user') return false
  if (msg.role === 'system') {
    return isChatVisibleNotification(msg.role, msg.content, msg.notifyLevel)
  }
  return msg.role === 'assistant' || msg.role === 'system'
}

/**
 * Озвучивает новые сообщения чата по очереди (user → assistant → system).
 * Ждёт окончания «думает», чтобы не озвучивать незаконченный стрим.
 */
export function useChatSpeechSync(
  chatId: string | undefined,
  messages: Message[],
  enabled: boolean,
  isThinking: boolean,
  /** Не озвучивать вопрос пользователя (голосовой режим «Джарвис») */
  skipUserMessages = false,
) {
  const cursorRef = useRef(0)
  const chatKeyRef = useRef<string | undefined>(undefined)
  const wasEnabledRef = useRef(false)

  useEffect(() => {
    if (chatKeyRef.current !== chatId) {
      chatKeyRef.current = chatId
      cursorRef.current = messages.length
    }
  }, [chatId, messages.length])

  useEffect(() => {
    if (!wasEnabledRef.current && enabled) {
      cursorRef.current = messages.length
      unlockChatSpeechPlayback()
    }
    if (wasEnabledRef.current && !enabled) {
      stopChatSpeechPlayback()
      cursorRef.current = messages.length
    }
    wasEnabledRef.current = enabled
  }, [enabled, messages.length])

  useEffect(() => {
    if (!enabled) return
    if (isThinking) return

    unlockChatSpeechPlayback()

    for (let i = cursorRef.current; i < messages.length; i++) {
      const msg = messages[i]
      if (!shouldSpeakMessage(msg, skipUserMessages)) continue
      if (msg.speechPlayed) continue
      speakChatMessage(msg.content, msg.audioUrl ?? null, msg.speechText ?? null)
    }
    cursorRef.current = messages.length
  }, [messages, enabled, isThinking])
}
