import { useCallback, useEffect, useRef, useState } from 'react'
import { TopBar } from '@/components/top-bar/TopBar'
import { SidebarFree } from '@/components/sidebar/SidebarFree'
import { ChatArea } from '@/components/chat/ChatArea'
import { SettingsDialog } from '@/components/settings/SettingsDialog'
import {
  dispatchUiCommands,
  JARVIS_UI_EVENT,
  toggleIndicatorsPanel,
  type SettingsFocusSection,
  type UiCommand,
} from '@/lib/uiBridge'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useTheme } from '@/hooks/useTheme'
import { useChats } from '@/hooks/useChats'
import { useBackend } from '@/hooks/useBackend'
import {
  fetchSettings,
  fetchStatus,
  evaluateInsult,
  restartInsultSession,
  fetchAvitoConfig,
  fetchSystemHealthReport,
  fetchTelegramConfig,
  fetchVoiceSlots,
  postSystemLog,
  saveSettings,
  setMode,
  setVoiceEnabled,
  streamMessage,
  toggleAvito,
  toggleTelegram,
  uploadFiles,
} from '@/api/client'
import { createHealthReportMessage } from '@/lib/healthReportMessage'
import { useJarvisVoiceListen } from '@/hooks/useJarvisVoiceListen'
import {
  isSpeechRecognitionSupported,
  requestMicrophoneAccess,
  type JarvisListenStatus,
} from '@/lib/jarvisWakeListen'
import { stopChatSpeechPlayback, unlockChatSpeechPlayback } from '@/lib/chatSpeech'
import {
  formatChatMessage,
  inferNotifyImportance,
  type NotifyImportance,
} from '@/lib/notifications'
import {
  MODE_LABELS,
  type AgentMode,
  type AppSettings,
  type Message,
  type AvitoConfig,
  type OperationProgressState,
  type TelegramConfig,
  type VoiceSlot,
} from '@/types'

const DEFAULT_SETTINGS: AppSettings = {
  provider: 'deepseek',
  defaultModel: 'deepseek-chat',
  openaiKey: '',
  openaiModel: 'gpt-5.5-instant',
  anthropicKey: '',
  deepseekKey: '',
  perplexityKey: '',
  perplexityModel: 'sonar',
  xaiKey: '',
  xaiModel: 'grok-4.20',
  nanobananaKey: '',
  ideogramKey: '',
}

export default function App() {
  const { theme, toggleTheme } = useTheme()
  const { agent, setAgent, connected, refresh } = useBackend()
  const [chatSyncPaused, setChatSyncPaused] = useState(false)
  const chat = useChats(connected, { syncPaused: chatSyncPaused })

  /** Счётчик оскорблений сбрасывается при старте backend (рестарт приложения), не при F5. */
  const insultBootDone = true

  const [mode, setModeLocal] = useState<AgentMode>('standard')
  /** Единый режим «Голос (Джарвис)»: микрофон + wake-word + озвучка ответов */
  const [voiceEnabled, setVoiceLocal] = useState(false)
  const [voiceListenStatus, setVoiceListenStatus] =
    useState<JarvisListenStatus>('off')
  const [voiceDraft, setVoiceDraft] = useState('')
  const chatSpeechRef = useRef(false)
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS)
  const [voiceSlots, setVoiceSlots] = useState<VoiceSlot[]>([])
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsSaveState, setSettingsSaveState] = useState<
    'idle' | 'saving' | 'ok' | 'error'
  >('idle')
  const [settingsFocus, setSettingsFocus] = useState<SettingsFocusSection | null>(null)
  const [settingsSearchQuery, setSettingsSearchQuery] = useState('')
  const [settingsScrollDomId, setSettingsScrollDomId] = useState<string | null>(null)
  const [telegramConfig, setTelegramConfig] = useState<TelegramConfig | null>(null)
  const [avitoConfig, setAvitoConfig] = useState<AvitoConfig | null>(null)
  const [isThinking, setIsThinking] = useState(false)
  const [clearingContext, setClearingContext] = useState(false)
  const [operationProgress, setOperationProgress] =
    useState<OperationProgressState | null>(null)
  const [tgLoading, setTgLoading] = useState(false)
  const [avitoLoading, setAvitoLoading] = useState(false)
  const [hint, setHint] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const prevModeRef = useRef<AgentMode>('standard')
  const prevTgRef = useRef(false)
  const [startupHealthReport, setStartupHealthReport] = useState<Message | null>(null)
  const healthReportGenRef = useRef(0)

  const handleMoodRestart = useCallback(async () => {
    if (!connected) return
    if (
      !window.confirm(
        'Сбросить счётчик оскорблений (0/3), поднять настроение и очистить историю чата?',
      )
    ) {
      return
    }
    try {
      const r = await restartInsultSession()
      setAgent((a) => ({ ...a, insult: r.insult, mood: r.mood }))
      await chat.reload()
      setStartupHealthReport(null)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Сброс счётчика недоступен')
    }
  }, [connected, setAgent, chat])

  const refreshStartupHealthReport = useCallback(async () => {
    if (!connected) return
    const gen = ++healthReportGenRef.current
    try {
      const { content } = await fetchSystemHealthReport()
      if (gen !== healthReportGenRef.current) return
      setStartupHealthReport(createHealthReportMessage(content))
    } catch {
      /* отчёт необязателен — не блокируем UI */
    }
  }, [connected])

  useEffect(() => {
    if (!connected) {
      setVoiceLocal(false)
      setAgent((a) => ({
        ...a,
        voiceListening: false,
        status: a.status === 'Listening...' ? 'IDLE' : a.status,
      }))
      return
    }
    fetchSettings().then(setSettings).catch(() => {})
    fetchVoiceSlots().then(setVoiceSlots).catch(() => {})
    fetchTelegramConfig().then(setTelegramConfig).catch(() => {})
    fetchAvitoConfig().then(setAvitoConfig).catch(() => {})
    setModeLocal(agent.mode)
    prevModeRef.current = agent.mode
    prevTgRef.current = agent.telegram.enabled
    const voiceOn = agent.voiceListening || agent.chatSpeechEnabled
    setVoiceLocal(voiceOn)
    chatSpeechRef.current = voiceOn
  }, [connected, agent.mode, agent.telegram.enabled, agent.chatSpeechEnabled, agent.voiceListening])

  useEffect(() => {
    chatSpeechRef.current = voiceEnabled
  }, [voiceEnabled])

  const logSystem = useCallback(
    async (
      content: string,
      opts?: { importance?: NotifyImportance; silent?: boolean; detail?: string },
    ) => {
      const body = opts?.detail
        ? formatChatMessage(content, opts.detail)
        : content
      const importance = opts?.importance ?? inferNotifyImportance(body)
      if (importance === 'routine') {
        void refresh()
        return
      }
      if (!chat.activeChat || !connected) return
      try {
        const msg = await postSystemLog(chat.activeChat.id, body, importance)
        if (msg) chat.appendMessage(chat.activeChat.id, msg)
      } catch {
        const fallback: Message = {
          id: `sys-${Date.now()}`,
          role: 'system',
          content: body,
          createdAt: new Date().toISOString(),
          notifyLevel: importance,
        }
        chat.appendMessage(chat.activeChat.id, fallback)
      }
      void refresh()
    },
    [chat, connected, refresh],
  )

  const handleModeChange = useCallback(
    async (m: AgentMode) => {
      const prev = prevModeRef.current
      if (prev === m) return
      if (
        m === 'marketer' &&
        !settings.nanobananaUsable &&
        !agent.nanobananaConfigured
      ) {
        void logSystem(
          'Режим «Маркетолог+Дизайнер» — нужен ключ Google Nano Banana (AIza…).',
          {
            detail:
              'Открыты **Настройки** → раздел **Google Nano Banana**. Вставьте ключ с aistudio.google.com/apikey и нажмите **Сохранить**.',
          },
        )
        setSettingsFocus('nanobanana')
        setSettingsOpen(true)
        return
      }
      if (m === 'accountant' && !settings.deepseekUsable && !agent.deepseekConfigured) {
        void logSystem('Режим «Бухгалтер + Юрист» — нужен ключ DeepSeek (`sk-…`).', {
          detail:
            'Открыты **Настройки** → раздел **DeepSeek**. Вставьте API-ключ и нажмите **Сохранить**.',
        })
        setSettingsFocus('deepseek')
        setSettingsOpen(true)
        return
      }
      if (
        m === 'developer' &&
        !settings.perplexityUsable &&
        !agent.perplexityUsable &&
        !agent.perplexityConfigured
      ) {
        void logSystem('Режим «Разработчик» — нужен ключ Perplexity (`pplx-…`).', {
          detail:
            'Открыты **Настройки** → **Perplexity**. Вставьте ключ, включите сервис и нажмите **Сохранить**.',
        })
        setSettingsFocus('perplexity')
        setSettingsOpen(true)
        return
      }
      setModeLocal(m)
      prevModeRef.current = m
      if (connected) {
        try {
          await setMode(m)
        } catch (e) {
          setModeLocal(prev)
          prevModeRef.current = prev
          void logSystem(
            `❌ ${e instanceof Error ? e.message : 'Не удалось сменить режим'}`,
          )
        }
      }
      void refresh()
      void refreshStartupHealthReport()
    },
    [
      agent.nanobananaConfigured,
      agent.perplexityConfigured,
      connected,
      logSystem,
      refresh,
      settings.deepseekUsable,
      settings.nanobananaUsable,
      settings.perplexityUsable,
      settings.deepseekConfigured,
      settings.nanobananaConfigured,
      settings.perplexityConfigured,
      refreshStartupHealthReport,
    ],
  )

  useEffect(() => {
    if (!connected || chat.loading || !chat.activeChat) return
    void refreshStartupHealthReport()
  }, [connected, chat.loading, chat.activeChat?.id, refreshStartupHealthReport])

  useEffect(() => {
    const onUi = (e: Event) => {
      const cmd = (e as CustomEvent<UiCommand>).detail
      if (cmd.action === 'open_settings') {
        const section = (cmd.section ?? 'general') as SettingsFocusSection
        setSettingsFocus(section === 'general' ? null : section)
        setSettingsOpen(true)
      }
      if (cmd.action === 'expand_panel') {
        setSettingsFocus(cmd.panel)
        setSettingsOpen(true)
      }
      if (cmd.action === 'refresh_status') void refresh()
      if (cmd.action === 'set_mode') {
        setModeLocal((prev) => {
          prevModeRef.current = prev
          return cmd.mode
        })
        void refresh()
        void refreshStartupHealthReport()
      }
      if (
        cmd.action === 'click' &&
        cmd.target === 'app' &&
        cmd.control === 'indicators_toggle'
      ) {
        toggleIndicatorsPanel()
      }
    }
    window.addEventListener(JARVIS_UI_EVENT, onUi)
    return () => window.removeEventListener(JARVIS_UI_EVENT, onUi)
  }, [refresh, refreshStartupHealthReport])

  const resetVoiceListening = useCallback(() => {
    stopChatSpeechPlayback()
    setVoiceListenStatus('off')
    setVoiceDraft('')
    setVoiceLocal(false)
    chatSpeechRef.current = false
    setAgent((a) => ({
      ...a,
      voiceListening: false,
      chatSpeechEnabled: false,
      status: a.status === 'Listening...' ? 'IDLE' : a.status,
    }))
    if (connected) void setVoiceEnabled(false)
  }, [connected, setAgent])

  const handleSendRef = useRef<(text: string) => void>(() => {})

  const handleVoiceWakeCommand = useCallback(
    (command: string) => {
      if (!chat.activeChat || isThinking) return
      setVoiceDraft('')
      handleSendRef.current(command)
    },
    [chat.activeChat, isThinking],
  )

  useJarvisVoiceListen({
    enabled: voiceEnabled && connected,
    paused: isThinking,
    onWakeCommand: handleVoiceWakeCommand,
    onStatus: (s) => {
      setVoiceListenStatus(s)
      if (s !== 'recording') setVoiceDraft('')
    },
    onInterim: setVoiceDraft,
    onError: (msg) => {
      setVoiceListenStatus('error')
      void logSystem(`❌ ${msg}`, {
        detail:
          'Chrome: замок слева от адреса → **Микрофон** → Разрешить. Нужен интернет для распознавания речи.',
      })
      resetVoiceListening()
    },
  })

  const handleVoiceToggle = useCallback(async () => {
    if (voiceEnabled) {
      resetVoiceListening()
      return
    }

    if (!isSpeechRecognitionSupported()) {
      void logSystem('❌ Голосовой ввод недоступен в этом браузере', {
        detail:
          `Используйте **Chrome** или **Edge** на \`${typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8001'}\`. Подключите микрофон в Windows.`,
      })
      return
    }

    setAgent((a) => ({ ...a, status: 'Listening...' }))

    const micCheck = await requestMicrophoneAccess()
    if (!micCheck.ok) {
      setAgent((a) => ({ ...a, status: 'IDLE' }))
      void logSystem(`❌ ${micCheck.error ?? 'Нет доступа к микрофону'}`)
      return
    }

    setVoiceLocal(true)
    chatSpeechRef.current = true
    setAgent((a) => ({
      ...a,
      voiceListening: true,
      chatSpeechEnabled: true,
      status: 'Listening...',
    }))

    if (connected) {
      try {
        const res = await setVoiceEnabled(true)
        setAgent((a) => ({
          ...a,
          chatSpeechEnabled: res.chat_speech_enabled ?? true,
        }))
      } catch {
        resetVoiceListening()
        return
      }
    }

    unlockChatSpeechPlayback()
    void logSystem(
      '🎤 **Голос (Джарвис)** — микрофон в фоне. Скажите **«Джарвис»** (кнопка станет жёлтой — идёт запись), затем вопрос до паузы.',
      { importance: 'routine' },
    )
  }, [voiceEnabled, connected, logSystem, resetVoiceListening, setAgent])

  const handleTgToggle = useCallback(async () => {
    if (!connected) {
      void logSystem('❌ Backend недоступен — запустите start.bat')
      return
    }
    const next = !agent.telegram.enabled
    if (next && !telegramConfig?.botTokenConfigured && !agent.telegram.botTokenConfigured) {
      void logSystem('❌ Сначала сохраните токен бота (кнопка «Сохранить токен»)')
      return
    }
    setTgLoading(true)
    try {
      await toggleTelegram(next)
      await refresh()
      const cfg = await fetchTelegramConfig()
      setTelegramConfig(cfg)
      if (next) {
        await new Promise((r) => setTimeout(r, 1500))
        await refresh()
      }
      let tg = agent.telegram
      try {
        tg = (await fetchStatus()).telegram
      } catch {
        /* refresh already updated agent */
      }
      if (next && tg.status === 'error') {
        void logSystem(
          `❌ **Коннектор Телеграм** — ${tg.error ?? 'нет связи с api.telegram.org'}`,
        )
      } else if (next && tg.status === 'active') {
        void logSystem(
          `📱 **Коннектор Телеграм** — сервер на связи${tg.botUsername ? ` (@${tg.botUsername})` : ''}`,
        )
      }
    } catch (e) {
      void logSystem(
        `❌ Коннектор Телеграм: ${e instanceof Error ? e.message : 'ошибка'}`,
      )
    } finally {
      setTgLoading(false)
    }
  }, [
    agent.telegram.enabled,
    agent.telegram.botTokenConfigured,
    connected,
    logSystem,
    refresh,
    telegramConfig?.botTokenConfigured,
  ])

  const handleAvitoToggle = useCallback(async () => {
    if (!connected) {
      void logSystem('❌ Backend недоступен — запустите start.bat')
      return
    }
    const next = !agent.avito.enabled
    if (
      next &&
      !avitoConfig?.clientIdConfigured &&
      !agent.avito.clientIdConfigured
    ) {
      void logSystem('❌ Сначала сохраните Client ID и Client Secret Авито')
      return
    }
    setAvitoLoading(true)
    try {
      await toggleAvito(next)
      await refresh()
      const cfg = await fetchAvitoConfig()
      setAvitoConfig(cfg)
    } catch (e) {
      void logSystem(`❌ Авито: ${e instanceof Error ? e.message : 'ошибка'}`)
    } finally {
      setAvitoLoading(false)
    }
  }, [
    agent.avito.enabled,
    agent.avito.clientIdConfigured,
    avitoConfig?.clientIdConfigured,
    connected,
    logSystem,
    refresh,
  ])

  const handleClearContext = useCallback(async () => {
    if (!chat.activeChat || !connected || isThinking) return
    setClearingContext(true)
    setError(null)
    try {
      await chat.clearContext()
      void logSystem('Контекст чата очищен.', { importance: 'routine' })
      void refreshStartupHealthReport()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось очистить контекст')
    } finally {
      setClearingContext(false)
    }
  }, [chat, connected, isThinking, logSystem, refreshStartupHealthReport])

  const handleSend = useCallback(
    async (text: string) => {
      if (!chat.activeChat || !connected || !insultBootDone) return
      setStartupHealthReport(null)
      healthReportGenRef.current += 1
      setError(null)
      const insultRequestId = crypto.randomUUID()
      const chatId = chat.activeChat.id

      const pendingUserId = `pending-${crypto.randomUUID()}`
      chat.upsertUserMessage(chatId, {
        id: pendingUserId,
        role: 'user',
        content: text,
        createdAt: new Date().toISOString(),
      })

      void evaluateInsult(text, insultRequestId, chatId)
        .then((ev) => {
          setAgent((a) => ({
            ...a,
            insult: ev.insult,
            ...(ev.mood ? { mood: ev.mood } : {}),
          }))
        })
        .catch(() => {
          /* дублирование в потоке чата с тем же insult_request_id */
        })

      setChatSyncPaused(true)
      setIsThinking(true)
      setOperationProgress(null)
      setAgent((a) => ({
        ...a,
        status: 'Thinking...',
        voiceListening: voiceEnabled,
      }))
      let streamId: string | null = null
      const speechOn = chatSpeechRef.current

      if (speechOn) unlockChatSpeechPlayback()

      try {
        await streamMessage(
          chat.activeChat.id,
          text,
          mode,
          speechOn,
          (ev) => {
          if (ev.type === 'user') {
            chat.upsertUserMessage(chat.activeChat!.id, ev.message)
          }
          if (ev.type === 'status') setAgent((a) => ({ ...a, status: ev.status }))
          if (ev.type === 'insult') {
            setAgent((a) => ({ ...a, insult: ev.insult }))
          }
          if (ev.type === 'mood') {
            setAgent((a) => ({ ...a, mood: ev.mood }))
          }
          if (ev.type === 'progress') {
            setOperationProgress((prev) => ({
              phase: ev.phase,
              message: ev.message,
              current: ev.current,
              total: ev.total,
              percent: ev.percent,
              logs: prev?.logs ?? [],
            }))
          }
          if (ev.type === 'log') {
            const stamp = new Date().toLocaleTimeString('ru-RU', { hour12: false })
            const line = `[${ev.tool}] ${ev.message}`
            setOperationProgress((prev) => ({
              phase: prev?.phase ?? ev.tool,
              message: prev?.message ?? ev.message,
              current: prev?.current ?? 0,
              total: prev?.total ?? 0,
              percent: prev?.percent ?? null,
              logs: [...(prev?.logs ?? []), line].slice(-12),
            }))
            setAgent((a) => ({
              ...a,
              toolLogs: [
                {
                  id: String(Date.now()),
                  timestamp: stamp,
                  tool: ev.tool,
                  message: ev.message,
                },
                ...a.toolLogs.slice(0, 24),
              ],
            }))
          }
          if (ev.type === 'chunk') {
            if (!streamId) {
              streamId = `s-${Date.now()}`
              chat.appendMessage(chat.activeChat!.id, {
                id: streamId,
                role: 'assistant',
                content: ev.content,
                createdAt: new Date().toISOString(),
              })
            } else {
              chat.updateAssistantMessage(chat.activeChat!.id, streamId, ev.content)
            }
          }
          if (ev.type === 'done') {
            if (streamId) chat.replaceMessage(chat.activeChat!.id, streamId, ev.message)
            else chat.appendMessage(chat.activeChat!.id, ev.message)
            if (ev.meta?.refresh_settings) {
              void fetchSettings().then(setSettings)
            }
            if (typeof ev.meta?.chat_speech_enabled === 'boolean') {
              setVoiceLocal(ev.meta.chat_speech_enabled)
              chatSpeechRef.current = ev.meta.chat_speech_enabled
            }
          }
          if (ev.type === 'ui' && ev.commands.length) {
            dispatchUiCommands(ev.commands)
          }
          if (ev.type === 'error') setError(ev.message)
          },
          insultRequestId,
        )
        void refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Ошибка')
      } finally {
        setChatSyncPaused(false)
        setIsThinking(false)
        setOperationProgress(null)
        setAgent((a) => ({
          ...a,
          status: voiceEnabled ? 'Listening...' : 'IDLE',
        }))
      }
    },
    [chat, connected, insultBootDone, mode, setAgent, refresh, voiceEnabled],
  )

  useEffect(() => {
    handleSendRef.current = (text: string) => {
      void handleSend(text)
    }
  }, [handleSend])

  const handleAttach = useCallback(
    async (files: FileList) => {
      if (!connected) return
      try {
        const res = await uploadFiles(files, mode)
        for (const f of res.files) {
          if (f.type === 'voice_base') {
            void logSystem(`🎙️ Голос «${f.name}» загружен.`, {
              detail: `Файл сохранён${f.filename ? ` как ${f.filename}` : ''}. Включите «Речь в текст» для озвучки ответов.`,
            })
          } else if (f.type === 'memory') {
            void logSystem(`📁 Файл «${f.name}» добавлен в память.`, {
              detail: `Хранилище: **${f.label ?? 'Память'}**. Учтётся в ответах ИИ.`,
            })
          } else if (f.type === 'bank_statement' && f.summary_markdown) {
            const n = f.transaction_count ?? 0
            void logSystem(`📊 Выписка «${f.name}» обработана.`, {
              detail: `${n} операций. Аналитика передана в контекст режима бухгалтера.`,
            })
          } else if (f.error) {
            void logSystem(`⚠️ \`${f.name}\`: ${f.error}`)
          }
        }
        setHint(null)
      } catch (e) {
        setHint(e instanceof Error ? e.message : 'Ошибка загрузки')
      }
      void refresh()
    },
    [connected, logSystem, refresh, mode],
  )

  const chatAreaProps = {
    agent,
    chat: chat.activeChat,
    sessionTokens: agent.sessionTokens,
    isThinking,
    operationProgress,
    disabled: !connected,
    connected,
    startupHealthReport,
    memory: agent.memory,
    onMemoryChange: () => void refresh(),
    onSystemLog: (t: string) => void logSystem(t),
    accountantMode: mode === 'accountant',
    marketerMode: mode === 'marketer',
    jarvisVoiceOn: voiceEnabled,
    voiceListenStatus,
    voicePaused: isThinking && voiceEnabled,
    onVoiceToggle: () => void handleVoiceToggle(),
    voiceDraft,
    onSend: (t: string) => void handleSend(t),
    onAttach: (f: FileList) => void handleAttach(f),
    onClearContext: () => void handleClearContext(),
    clearingContext,
  } as const

  return (
    <TooltipProvider>
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
      <TopBar
        agent={agent}
        mode={mode}
        voiceSlots={voiceSlots}
        xtts={agent.xtts}
        onModeChange={(m) => void handleModeChange(m)}
        onBaseVoiceUploaded={() => {
          resetVoiceListening()
          void refresh()
        }}
        onMemoryChange={() => void refresh()}
        onVoiceSlotUpdate={(s) => {
          setVoiceSlots((prev) => prev.map((x) => (x.slot === s.slot ? s : x)))
        }}
        onVoiceRefresh={() => void fetchVoiceSlots().then(setVoiceSlots)}
        onXttsRefresh={() => void refresh()}
        onSystemLog={(t) => void logSystem(t)}
      />

      {connected && !agent.deepseekConfigured && (
        <div className="border-b border-primary/30 bg-primary/5 px-4 py-2 text-center text-sm">
          Укажите <strong>DeepSeek API Key</strong> в Настройках (формат{' '}
          <code className="rounded bg-muted px-1 text-xs">sk-…</code>) для ответов нейросети.
        </div>
      )}

      {!connected && (
        <div className="bg-amber-500/10 px-4 py-2 text-center text-sm text-amber-800 dark:text-amber-200">
          Backend недоступен — запустите <code className="rounded bg-muted px-1">start.bat</code>
        </div>
      )}
      {(error || chat.error) && (
        <div className="bg-destructive/10 px-4 py-1 text-center text-xs text-destructive">
          {error ?? chat.error}
        </div>
      )}
      {hint && (
        <div className="bg-accent/30 px-4 py-1 text-center text-xs">
          {hint}
          <button type="button" className="ml-2 underline" onClick={() => setHint(null)}>
            скрыть
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <SidebarFree
          onOpenSettings={() => setSettingsOpen(true)}
          onMenuNavigate={({ sectionDomId }) => {
            setSettingsOpen(true)
            setSettingsScrollDomId(sectionDomId)
          }}
        />
        <ChatArea {...chatAreaProps} />
      </div>

      <SettingsDialog
        open={settingsOpen}
        focusSection={settingsFocus}
        onOpenChange={(open) => {
          setSettingsOpen(open)
          if (!open) {
            setSettingsFocus(null)
            setSettingsSearchQuery('')
            setSettingsScrollDomId(null)
          }
        }}
        searchQuery={settingsSearchQuery}
        onSearchQueryChange={setSettingsSearchQuery}
        scrollTargetDomId={settingsScrollDomId}
        onScrollTargetConsumed={() => setSettingsScrollDomId(null)}
        settings={settings}
        theme={theme}
        agent={agent}
        voiceSlots={voiceSlots}
        xtts={agent.xtts}
        onChange={setSettings}
        onThemeChange={(t) => {
          if (t !== theme) toggleTheme()
        }}
        onVoiceSlotUpdate={(s) => {
          setVoiceSlots((prev) => prev.map((x) => (x.slot === s.slot ? s : x)))
        }}
        onVoiceRefresh={() => void fetchVoiceSlots().then(setVoiceSlots)}
        onXttsRefresh={() => void refresh()}
        onBaseVoiceUploaded={() => void refresh()}
        onMemoryChange={() => void refresh()}
        onSystemLog={(t) => void logSystem(t)}
        telegramConfig={telegramConfig}
        avitoConfig={avitoConfig}
        tgLoading={tgLoading}
        avitoLoading={avitoLoading}
        onToggleTelegram={() => void handleTgToggle()}
        onToggleAvito={() => void handleAvitoToggle()}
        onTelegramConfigSaved={(cfg) => {
          setTelegramConfig(cfg)
          void refresh()
        }}
        onAvitoConfigSaved={(cfg) => {
          setAvitoConfig(cfg)
          void refresh()
        }}
        backendConnected={connected}
        onQwenRamChanged={() => void refresh({ force: true })}
        saveState={settingsSaveState}
        onSave={async () => {
          setSettingsSaveState('saving')
          try {
            const s = await saveSettings(settings)
            setSettings(s)
            setSettingsSaveState('ok')
            void logSystem(
              s.deepseekConfigured
                ? '✅ Настройки сохранены. Ключ **DeepSeek** принят сервером.'
                : 'Настройки сохранены.',
              {
                detail: s.deepseekConfigured
                  ? 'Режим «Бухгалтер + Юрист» и сложные запросы пойдут в DeepSeek. В стандартном чате по умолчанию отвечает локальная Qwen.'
                  : 'Вставьте **DeepSeek API ключ** (`sk-…`, 32+ символов) и нажмите **Сохранить** ещё раз.',
              },
            )
            await refresh()
            window.setTimeout(() => setSettingsSaveState('idle'), 3500)
          } catch {
            setSettingsSaveState('error')
            void logSystem('❌ Не удалось сохранить настройки на сервере')
            window.setTimeout(() => setSettingsSaveState('idle'), 4000)
          }
        }}
      />
    </div>
    </TooltipProvider>
  )
}
