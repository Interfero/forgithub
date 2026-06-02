import { Eraser, Paperclip, Send } from 'lucide-react'
import { SessionTokensChip } from '@/lib/statusIndicators'
import { ChatPinnedConscious } from '@/components/chat/ChatPinnedConscious'
import { ComposerActionRail } from '@/components/chat/ComposerActionRail'
import { JarvisVoiceButton } from '@/components/chat/JarvisVoiceButton'
import type { JarvisListenStatus } from '@/lib/jarvisWakeListen'
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react'
import { Button } from '@/components/ui/button'
import { Hint } from '@/components/ui/hint'
import { cn } from '@/lib/utils'
import type { MemoryStores } from '@/types'

export interface ChatInputHandle {
  focus: () => void
}

interface ChatInputProps {
  sessionTokens?: number
  disabled?: boolean
  sending?: boolean
  accountantMode?: boolean
  marketerMode?: boolean
  voiceEnabled?: boolean
  voiceListenStatus?: JarvisListenStatus
  voicePaused?: boolean
  onVoiceToggle?: () => void
  voiceDraft?: string
  onSend: (text: string) => void
  onAttach?: (files: FileList) => void
  onClearContext?: () => void | Promise<void>
  clearingContext?: boolean
  memory?: MemoryStores
  onMemoryChange?: () => void
  onSystemLog?: (text: string) => void
  showPinnedConscious?: boolean
}

const MIN_HEIGHT = 44
const MAX_HEIGHT = 200

/** Сетка: кнопки слева, поле ввода в центре колонки чата (боковые 1fr симметричны). */
/** Центральная колонка — поле ввода; боковые 1fr центрируют её в чате. Кнопки — в левой 1fr у правого края. */
const COMPOSER_GRID =
  'grid w-full grid-cols-[1fr_min(48rem,calc(100%-0.5rem))_1fr] items-end gap-x-2.5'

export const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(
  function ChatInput(
    {
      sessionTokens = 0,
      disabled,
      sending,
      accountantMode,
      marketerMode,
      voiceEnabled = false,
      voiceListenStatus = 'off',
      voicePaused = false,
      onVoiceToggle,
      voiceDraft = '',
      onSend,
      onAttach,
      onClearContext,
      clearingContext = false,
      memory,
      onMemoryChange,
      onSystemLog,
      showPinnedConscious = false,
    },
    ref,
  ) {
    const [value, setValue] = useState('')
    const displayValue = voiceDraft || value
    const voicePreview = !!voiceDraft
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const fileRef = useRef<HTMLInputElement>(null)

    const focusInput = useCallback(() => {
      const el = textareaRef.current
      if (!el || disabled) return
      el.focus({ preventScroll: true })
    }, [disabled])

    useImperativeHandle(ref, () => ({ focus: focusInput }), [focusInput])

    const textMinH = showPinnedConscious ? 40 : MIN_HEIGHT

    const resize = useCallback(() => {
      const el = textareaRef.current
      if (!el) return
      el.style.height = 'auto'
      const next = Math.min(Math.max(el.scrollHeight, textMinH), MAX_HEIGHT)
      el.style.height = `${next}px`
    }, [textMinH])

    useEffect(() => {
      resize()
    }, [voiceDraft, resize])

    const handleSend = () => {
      const text = value.trim()
      if (!text || disabled || sending) return
      onSend(text)
      setValue('')
      if (textareaRef.current) {
        textareaRef.current.style.height = `${textMinH}px`
      }
      requestAnimationFrame(() => focusInput())
    }

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    }

    const attachHint = accountantMode
      ? 'Документы, выписки или аудио (до 15 МБ)'
      : 'Текст или аудио для голоса (до 15 МБ)'

    return (
      <div className="border-t border-border bg-card/50 px-3 py-3 sm:px-4">
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          multiple
          accept={
            accountantMode
              ? ".xlsx,.xls,.txt,.csv,.pdf,.docx,.md,audio/*,.ogg,.wav,.mp3,.webm,.m4a,.flac"
              : ".pdf,.txt,.docx,.md,.json,audio/*,.ogg,.wav,.mp3,.webm,.m4a,.flac,.aac,.opus"
          }
          onChange={(e) => {
            if (e.target.files?.length && onAttach) {
              onAttach(e.target.files)
              e.target.value = ''
            }
          }}
        />

        <div className={COMPOSER_GRID}>
          <div className="col-start-1 row-start-1 flex items-end justify-end gap-1.5 self-end justify-self-end">
            <SessionTokensChip tokens={sessionTokens} compact />
          <div
            className={cn(
              'flex w-fit shrink-0 items-center',
              'overflow-hidden rounded-xl border border-border/80 bg-card/70 shadow-sm',
              'ring-1 ring-primary/5',
            )}
            role="toolbar"
            aria-label="Действия чата"
          >
            {onClearContext && (
              <ComposerActionRail
                hint="Очистить контекст чата (переписка). Сознательное и настройки не затрагиваются."
                icon={<Eraser className="h-4 w-4" strokeWidth={2} />}
                onClick={() => void onClearContext()}
                disabled={disabled || sending || clearingContext}
                pulse={clearingContext}
                ariaLabel="Очистить контекст чата"
              />
            )}

            {onVoiceToggle && (
              <JarvisVoiceButton
                voiceEnabled={voiceEnabled}
                voiceListenStatus={voiceListenStatus}
                voicePaused={voicePaused}
                disabled={disabled}
                onToggle={onVoiceToggle}
              />
            )}

            <ComposerActionRail
              hint={attachHint}
              icon={<Paperclip className="h-4 w-4" strokeWidth={2} />}
              onClick={() => fileRef.current?.click()}
              disabled={disabled}
              ariaLabel="Прикрепить файл"
              showDivider={false}
            />
          </div>
          </div>

          <div
            className={cn(
              'col-start-2 row-start-1 flex min-w-0 w-full flex-col gap-0 overflow-hidden rounded-xl p-2',
              'border border-input/90 bg-background shadow-sm',
              'transition-shadow focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/25',
            )}
          >
            {showPinnedConscious && memory && (
              <ChatPinnedConscious
                embedded
                memory={memory}
                onMemoryChange={onMemoryChange}
                onSystemLog={onSystemLog}
              />
            )}

            <div className="flex w-full min-w-0 items-end gap-2">
              <textarea
                ref={textareaRef}
                value={displayValue}
                readOnly={voicePreview}
                disabled={disabled}
                rows={1}
                placeholder={
                  voicePreview
                    ? 'Запись голоса…'
                    : 'Сообщение… (Enter — отправить, Shift+Enter — новая строка)'
                }
                className={cn(
                  'min-h-[40px] max-h-[200px] flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-relaxed outline-none placeholder:text-muted-foreground disabled:opacity-50',
                  voicePreview && 'text-yellow-700/90 dark:text-yellow-300/90',
                )}
                style={{ height: showPinnedConscious ? 40 : MIN_HEIGHT }}
                onChange={(e) => {
                  if (voicePreview) return
                  setValue(e.target.value)
                  resize()
                }}
                onKeyDown={voicePreview ? undefined : handleKeyDown}
              />

              <Hint text="Отправить сообщение (Enter)">
                <Button
                  type="button"
                  size="icon"
                  className="h-9 w-9 shrink-0 shadow-sm"
                  disabled={disabled || sending || !value.trim()}
                  onClick={handleSend}
                >
                  <Send className="h-4 w-4" />
                </Button>
              </Hint>
            </div>
          </div>

          <div className="col-start-3 min-w-0" aria-hidden />
        </div>

        <div className={cn(COMPOSER_GRID, 'mt-2')}>
          <div aria-hidden />
          <p className="col-start-2 text-center text-[11px] text-muted-foreground">
            Enter — отправить · Shift+Enter — новая строка
            {marketerMode && ' · Картинки: «нарисуй …» (Nano Banana)'}
            {' · '}
            Слева (иконки): очистка · голос · вложение
            {accountantMode && ' · выписки .xlsx / 1С .txt'}
          </p>
          <div aria-hidden />
        </div>
      </div>
    )
  },
)
