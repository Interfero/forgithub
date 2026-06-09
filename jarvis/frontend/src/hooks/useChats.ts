import { useCallback, useEffect, useMemo, useState } from 'react'
import { clearChatContext, fetchChats } from '@/api/client'
import type { Chat, Message } from '@/types'

type UseChatsOptions = {
  /** Не подтягивать /api/chats пока идёт поток ответа — не затирает сообщение Шефа. */
  syncPaused?: boolean
}

/** Единственный чат Jarvis — без создания и удаления диалогов. */
export function useChats(connected: boolean, options: UseChatsOptions = {}) {
  const syncPaused = options.syncPaused ?? false
  const [chat, setChat] = useState<Chat | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!connected) return
    try {
      setError(null)
      const list = await fetchChats()
      const incoming = list[0] ?? null
      setChat((prev) => {
        if (!incoming) return null
        if (!prev || prev.id !== incoming.id) return incoming
        if (incoming.messages.length === 0 && prev.messages.length > 0) return prev
        if (incoming.messages.length < prev.messages.length) return prev
        return incoming
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки чата')
    } finally {
      setLoading(false)
    }
  }, [connected])

  useEffect(() => {
    if (connected) void load()
    else {
      // Диалог хранится на сервере; при кратком обрыве связи не очищаем UI.
      setLoading(false)
    }
  }, [connected, load])

  /** Подхват системных сообщений (плановые проверки каждые 30 мин). */
  useEffect(() => {
    if (!connected || syncPaused) return
    const id = window.setInterval(() => {
      void (async () => {
        try {
          const list = await fetchChats()
          const c = list[0] ?? null
          if (!c) return
          setChat((prev) => {
            if (!prev || prev.id !== c.id) return c
            // Не затирать UI пустым ответом (гонка с потоком / рестартом).
            if (c.messages.length === 0 && prev.messages.length > 0) return prev
            if (c.messages.length < prev.messages.length) return prev
            if (c.messages.length === prev.messages.length) {
              const prevTail = prev.messages[prev.messages.length - 1]?.id
              const nextTail = c.messages[c.messages.length - 1]?.id
              if (prevTail === nextTail) return prev
            }
            return c
          })
        } catch {
          /* ignore */
        }
      })()
    }, 25_000)
    return () => window.clearInterval(id)
  }, [connected, syncPaused])

  const activeChat = chat
  const activeChatId = chat?.id ?? ''

  const appendMessage = useCallback((chatId: string, message: Message) => {
    setChat((c) => {
      if (!c || c.id !== chatId) return c
      return {
        ...c,
        updatedAt: message.createdAt,
        messages: [...c.messages, message],
      }
    })
  }, [])

  /** Сразу показать сообщение Шефа; при ответе сервера подменить id на сохранённый. */
  const upsertUserMessage = useCallback((chatId: string, message: Message) => {
    setChat((c) => {
      if (!c || c.id !== chatId) return c
      const idx = c.messages.findIndex(
        (m) =>
          m.role === 'user' &&
          (m.id === message.id || m.content === message.content),
      )
      if (idx >= 0) {
        const next = [...c.messages]
        next[idx] = message
        return { ...c, updatedAt: message.createdAt, messages: next }
      }
      return {
        ...c,
        updatedAt: message.createdAt,
        messages: [...c.messages, message],
      }
    })
  }, [])

  const updateAssistantMessage = useCallback(
    (chatId: string, messageId: string, content: string) => {
      setChat((c) => {
        if (!c || c.id !== chatId) return c
        return {
          ...c,
          messages: c.messages.map((m) =>
            m.id === messageId ? { ...m, content } : m,
          ),
        }
      })
    },
    [],
  )

  const clearContext = useCallback(async () => {
    if (!chat?.id) return
    try {
      setError(null)
      const cleared = await clearChatContext(chat.id)
      setChat(cleared)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось очистить контекст')
      throw e
    }
  }, [chat?.id])

  const replaceMessage = useCallback(
    (chatId: string, messageId: string, message: Message) => {
      setChat((c) => {
        if (!c || c.id !== chatId) return c
        return {
          ...c,
          updatedAt: message.createdAt,
          messages: c.messages.map((m) => (m.id === messageId ? message : m)),
        }
      })
    },
    [],
  )

  return {
    chats: useMemo(() => (chat ? [chat] : []), [chat]),
    activeChat,
    activeChatId,
    setActiveChatId: () => {},
    createChat: async () => chat,
    deleteChat: async () => {},
    renameChat: async () => {},
    clearContext,
    appendMessage,
    upsertUserMessage,
    updateAssistantMessage,
    replaceMessage,
    loading,
    error,
    reload: load,
  }
}
