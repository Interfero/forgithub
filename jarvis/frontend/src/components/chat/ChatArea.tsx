import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { ChatInput, type ChatInputHandle } from '@/components/chat/ChatInput'
import { JarvisMark } from '@/components/JarvisMark'
import { isChatVisibleNotification } from '@/lib/notifications'
import { useChatSpeechSync } from '@/hooks/useChatSpeechSync'
import { useJarvisSpeechBubble } from '@/hooks/useJarvisSpeechBubble'
import { OperationProgress } from '@/components/chat/OperationProgress'
import { JarvisThinkingBlock } from '@/components/chat/JarvisThinkingBlock'
import type { ChatSurfaceMode } from '@/lib/chatSurfaceMode'
import type { AgentState, Chat, MemoryStores, Message, OperationProgressState } from '@/types'

interface ChatAreaProps {
  agent: AgentState
  chat: Chat | undefined
  sessionTokens?: number
  isThinking?: boolean
  thinkingTrace?: string[]
  operationProgress?: OperationProgressState | null
  disabled?: boolean
  accountantMode?: boolean
  marketerMode?: boolean
  jarvisVoiceOn?: boolean
  voiceDraft?: string
  onSend: (text: string) => void
  onAttach?: (files: FileList) => void
  onClearContext?: () => void | Promise<void>
  clearingContext?: boolean
  memory?: MemoryStores
  onMemoryChange?: () => void
  onSystemLog?: (text: string) => void
  chatSurfaceMode?: ChatSurfaceMode
  /** Стартовый отчёт — скрывается после первого сообщения в этой сессии страницы */
  startupHealthReport?: Message | null
  startupReportDismissed?: boolean
  connected?: boolean
  /** Встроен в полноэкранный тамагочи — без дублирующего аватара в приветствии. */
  embedded?: boolean
}

export function ChatArea({
  agent,
  chat,
  sessionTokens = 0,
  isThinking,
  thinkingTrace = [],
  operationProgress,
  disabled,
  accountantMode,
  marketerMode,
  jarvisVoiceOn,
  voiceDraft = '',
  onSend,
  onAttach,
  onClearContext,
  clearingContext,
  memory,
  onMemoryChange,
  onSystemLog,
  chatSurfaceMode = 'text',
  startupHealthReport = null,
  startupReportDismissed = false,
  connected = false,
  embedded = false,
}: ChatAreaProps) {
  const showPinned = !accountantMode && !marketerMode && !!memory
  const messagesScrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<ChatInputHandle>(null)

  const messages = chat?.messages ?? []

  useChatSpeechSync(
    chat?.id,
    messages,
    false,
    !!isThinking,
    !!jarvisVoiceOn,
  )

  useEffect(() => {
    if (!isThinking && !disabled) {
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [isThinking, disabled])

  const visibleMessages = messages.filter((m) =>
    isChatVisibleNotification(m.role, m.content, m.notifyLevel),
  )
  const hasUserMessages = visibleMessages.some((m) => m.role === 'user')
  const showStartupReport =
    !startupReportDismissed && !isThinking && !!startupHealthReport
  const showWelcome = !hasUserMessages && !isThinking && !showStartupReport
  const bubble = useJarvisSpeechBubble(agent, !!isThinking, messages, connected)

  useEffect(() => {
    const el = messagesScrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [
    visibleMessages.length,
    isThinking,
    operationProgress?.message,
    showStartupReport,
    startupHealthReport?.id,
    chat?.id,
    voiceDraft,
  ])

  return (
    <main
      className={cn(
        'flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background',
        embedded && 'h-full',
      )}
    >
      <div
        ref={messagesScrollRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain scroll-smooth"
      >
        {showWelcome ? (
          <div
            className={cn(
              'flex min-h-full flex-col items-center justify-center gap-3 px-6 py-8 text-center',
              embedded ? 'min-h-[min(100%,240px)]' : 'min-h-[320px]',
            )}
          >
            {!embedded ? <JarvisMark agent={agent} bubble={bubble} /> : null}
            <h2 className="text-lg font-medium">Начните диалог</h2>
            <p className="max-w-md text-sm text-muted-foreground">
              {marketerMode
                ? 'Маркетинг и дизайн. Напишите «нарисуй …» или «сгенерируй баннер» — картинка через Google Nano Banana (ключ в Настройках).'
                : accountantMode
                  ? 'Режим бухгалтера и юриста: прикрепите выписку (.xlsx, 1С .txt), укажите реквизиты с ИНН — контрагент сохранится в SQLite. Законы — через веб-поиск (кейс-метод).'
                  : 'Стандартный чат: вопрос внизу; над полем ввода — «Сознательное»: загрузка .txt / .md / .json для контекста Jarvis.'}
            </p>
          </div>
        ) : (
          <div className="py-4">
            {showStartupReport && startupHealthReport ? (
              <>
                {!embedded ? (
                  <div className="flex justify-center px-4 pb-2 pt-2">
                    <JarvisMark agent={agent} bubble={bubble} />
                  </div>
                ) : null}
                <MessageBubble message={startupHealthReport} />
              </>
            ) : null}
            {visibleMessages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {thinkingTrace.length > 0 ? (
              <JarvisThinkingBlock lines={thinkingTrace} />
            ) : null}
            {isThinking ? (
              chatSurfaceMode === 'voice' ? (
                <div className="flex gap-3 px-4 py-3">
                  {!embedded ? (
                    <JarvisMark agent={agent} bubble="think" className="h-14 w-14" />
                  ) : null}
                  <p className="pt-3 text-sm text-muted-foreground">Jarvis думает — в чат пойдёт только финальная речь.</p>
                </div>
              ) : operationProgress ? (
                <div className="flex gap-3 px-4 py-3">
                  {!embedded ? (
                    <JarvisMark agent={agent} bubble="think" className="h-14 w-14" />
                  ) : null}
                  <div className="min-w-0 flex-1 pt-1">
                    <OperationProgress progress={operationProgress} />
                  </div>
                </div>
              ) : (
                <div className="flex gap-3 px-4 py-3">
                  {!embedded ? (
                    <JarvisMark agent={agent} bubble="think" className="h-14 w-14" />
                  ) : null}
                  <div
                    className={cn(
                      'flex items-center text-sm text-muted-foreground',
                      embedded ? 'px-2 pt-1' : 'pt-3',
                    )}
                  >
                    <span className="sr-only">Jarvis думает</span>
                    <span className="flex gap-1">
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.2s]" />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.1s]" />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
                    </span>
                  </div>
                </div>
              )
            ) : null}
          </div>
        )}
      </div>

      <div className="shrink-0">
      <ChatInput
        ref={inputRef}
        sessionTokens={sessionTokens}
        disabled={disabled}
        sending={isThinking}
        accountantMode={accountantMode}
        marketerMode={marketerMode}
        chatSurfaceMode={chatSurfaceMode}
        voiceDraft={voiceDraft}
        onSend={onSend}
        onAttach={onAttach}
        onClearContext={onClearContext}
        clearingContext={clearingContext}
        showPinnedConscious={showPinned}
        memory={memory}
        onMemoryChange={onMemoryChange}
        onSystemLog={onSystemLog}
      />
      </div>
    </main>
  )
}
