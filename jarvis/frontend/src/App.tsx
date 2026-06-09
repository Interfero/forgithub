import { useCallback, useEffect, useRef, useState } from 'react'
import { TopBar } from '@/components/top-bar/TopBar'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { JarvisGameGrid } from '@/components/game/JarvisGameGrid'
import { JarvisGameTopPanel } from '@/components/game/JarvisGameTopPanel'
import { ChatArea } from '@/components/chat/ChatArea'
import { VoiceAccessDialog } from '@/components/chat/VoiceAccessDialog'
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
import { useJarvisScreenModel } from '@/hooks/useJarvisScreenModel'
import {
  fetchSettings,
  evaluateInsult,
  restartInsultSession,
  fetchAvitoConfig,
  fetchTelegramConfig,
  fetchStatus,
  fetchSystemHealthReport,
  fetchVoiceSlots,
  openJarvisGame,
  postSystemLog,
  saveSettings,
  setMode,
  setVoiceEnabled,
  fetchVoiceReadiness,
  streamMessage,
  toggleAvito,
  toggleTelegram,
  uploadFiles,
} from '@/api/client'
import { createHealthReportMessage } from '@/lib/healthReportMessage'
import { useJarvisVoiceDialog } from '@/hooks/useJarvisVoiceDialog'
import {
  enqueueChatSpeech,
  onSpeechPlaybackChange,
  setChatSpeechEnabled,
  speakChatContent,
  stopChatSpeechPlayback,
  unlockChatSpeechPlayback,
} from '@/lib/chatSpeech'
import { isMicCaptureSupported } from '@/lib/jarvisMicCapture'
import {
  requestMicrophoneAccess,
  type JarvisListenStatus,
} from '@/lib/jarvisWakeListen'
import {
  formatChatMessage,
  inferNotifyImportance,
  type NotifyImportance,
} from '@/lib/notifications'
import {
  readChatSurfaceMode,
  voiceAccessGranted,
  writeChatSurfaceMode,
  type ChatSurfaceMode,
} from '@/lib/chatSurfaceMode'
import {
  MODE_LABELS,
  type AgentMode,
  type AppSettings,
  type Message,
  type AvitoConfig,
  type TelegramConfig,
  type OperationProgressState,
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

export default function App({ gameMode = false }: { gameMode?: boolean }) {
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
  const [chatSurfaceMode, setChatSurfaceMode] = useState<ChatSurfaceMode>(() =>
    readChatSurfaceMode(),
  )
  const [voiceAccessOpen, setVoiceAccessOpen] = useState(false)
  const pendingAttachRef = useRef('')
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
  const [voiceSpeaking, setVoiceSpeaking] = useState(false)
  const [clearingContext, setClearingContext] = useState(false)
  const [operationProgress, setOperationProgress] =
    useState<OperationProgressState | null>(null)
  const [thinkingTrace, setThinkingTrace] = useState<string[]>([])
  const [tgLoading, setTgLoading] = useState(false)
  const [avitoLoading, setAvitoLoading] = useState(false)
  const [hint, setHint] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const prevModeRef = useRef<AgentMode>('standard')
  const prevTgRef = useRef(false)
  const [startupHealthReport, setStartupHealthReport] = useState<Message | null>(null)
  const [startupReportDismissed, setStartupReportDismissed] = useState(false)
  const healthReportGenRef = useRef(0)
  const streamAbortRef = useRef<AbortController | null>(null)

  const chatMessages = chat.activeChat?.messages ?? []
  const screenModel = useJarvisScreenModel(agent, chatMessages, connected)

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
      setStartupReportDismissed(false)
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

  useEffect(() => onSpeechPlaybackChange(setVoiceSpeaking), [])

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
    streamAbortRef.current?.abort()
    streamAbortRef.current = null
    stopChatSpeechPlayback()
    setChatSpeechEnabled(false)
    setIsThinking(false)
    setVoiceListenStatus('off')
    setVoiceDraft('')
    setVoiceLocal(false)
    chatSpeechRef.current = false
    writeChatSurfaceMode('text')
    setChatSurfaceMode('text')
    setAgent((a) => ({
      ...a,
      voiceListening: false,
      chatSpeechEnabled: false,
      status: a.status === 'Listening...' ? 'IDLE' : a.status,
    }))
    if (connected) void setVoiceEnabled(false)
  }, [connected, setAgent])

  const handleSendRef = useRef<(text: string) => void>(() => {})

  const handleVoiceBargeIn = useCallback(() => {
    streamAbortRef.current?.abort()
    streamAbortRef.current = null
    stopChatSpeechPlayback()
    setIsThinking(false)
    setVoiceSpeaking(false)
    setVoiceDraft('')
    setAgent((a) => ({
      ...a,
      status: 'Listening...',
      voiceListening: true,
    }))
  }, [setAgent])

  const handleVoiceStop = useCallback(() => {
    streamAbortRef.current?.abort()
    streamAbortRef.current = null
    stopChatSpeechPlayback()
    setIsThinking(false)
    setVoiceSpeaking(false)
    setVoiceDraft('Стоп')
    setAgent((a) => ({
      ...a,
      status: voiceEnabled ? 'Listening...' : 'IDLE',
    }))
    void logSystem('⏹ Голос: стоп — озвучка и ответ прерваны', { importance: 'routine' })
  }, [logSystem, setAgent, voiceEnabled])

  const handleVoiceWakeCommand = useCallback(
    (command: string) => {
      if (!connected) {
        void logSystem('❌ Голос: backend не подключён — запустите start.bat')
        return
      }
      if (!chat.activeChat) {
        void logSystem('❌ Голос: чат ещё не загружен — обновите страницу (F5)')
        return
      }
      setVoiceDraft('')
      handleSendRef.current(command)
    },
    [chat.activeChat, connected, logSystem],
  )

  useJarvisVoiceDialog({
    enabled: voiceEnabled && connected,
    sendPaused: isThinking,
    ttsActive: voiceSpeaking,
    requireWakeWord: false,
    onCommand: handleVoiceWakeCommand,
    onBargeIn: handleVoiceBargeIn,
    onStop: handleVoiceStop,
    onHeard: (text, sent) => {
      if (!sent && text) {
        void logSystem(`🎤 Распознано: «${text.slice(0, 120)}»`, {
          detail: sent
            ? undefined
            : 'Имя не распознано — скажите «Джарвис» или «Джа» и сразу вопрос одной фразой.',
          importance: 'routine',
        })
      }
    },
    onStatus: (s) => {
      setVoiceListenStatus(s)
      if (s !== 'recording') setVoiceDraft('')
    },
    onInterim: setVoiceDraft,
    onError: (msg) => {
      setVoiceListenStatus('error')
      void logSystem(`❌ ${msg}`, {
        detail:
          'Разрешите микрофон (замок в адресной строке). Для STT: `install-chat-voice.bat` (GigaAM-v3).',
      })
      resetVoiceListening()
    },
  })

  const handleVoiceToggle = useCallback(async () => {
    if (voiceEnabled) {
      resetVoiceListening()
      return
    }

    if (!isMicCaptureSupported()) {
      void logSystem('❌ Голосовой ввод недоступен в этом браузере', {
        detail:
          'Нужны **Chrome** или **Edge** на `http://127.0.0.1:8000` и рабочий микрофон в Windows.',
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

    writeChatSurfaceMode('voice')
    setChatSurfaceMode('voice')
    setVoiceLocal(true)
    chatSpeechRef.current = true
    setChatSpeechEnabled(true)
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

    try {
      const readiness = await fetchVoiceReadiness()
      if (!readiness.stt?.package_installed || !readiness.stt?.ffmpeg) {
        void logSystem(`⚠️ STT: ${readiness.stt?.message ?? 'не готов'}`, {
          detail: 'Запустите **install-chat-voice.bat** (GigaAM-v3 + ffmpeg).',
        })
      }
      if (!readiness.ready) {
        void logSystem(`⚠️ Озвучка: ${readiness.message ?? 'не готова'}`, {
          detail: 'Тот же install-chat-voice.bat (edge-tts). Ответы можно читать в чате.',
        })
      }
    } catch {
      /* readiness необязателен */
    }

    void logSystem(
      '🎤 **Голос включён** — микрофон слушает **постоянно** (даже пока Jarvis отвечает; фразы встают в очередь до 5). «**Джарвис стоп**» — прервать озвучку.',
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
      setStartupReportDismissed(false)
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
      const attachBlock = pendingAttachRef.current.trim()
      const payload = attachBlock ? `${text.trim()}\n\n${attachBlock}` : text.trim()
      if (!payload) return
      pendingAttachRef.current = ''
      setStartupReportDismissed(true)
      setStartupHealthReport(null)
      healthReportGenRef.current += 1
      setError(null)
      const insultRequestId = crypto.randomUUID()
      const chatId = chat.activeChat.id

      const pendingUserId = `pending-${crypto.randomUUID()}`
      chat.upsertUserMessage(chatId, {
        id: pendingUserId,
        role: 'user',
        content: payload,
        createdAt: new Date().toISOString(),
      })

      void evaluateInsult(payload, insultRequestId, chatId)
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
      setThinkingTrace([])
      setAgent((a) => ({
        ...a,
        status: 'Thinking...',
        voiceListening: voiceEnabled,
      }))
      let streamId: string | null = null
      let pendingSpeechAudioUrl: string | null = null
      let pendingSpeechText: string | null = null
      let speechPlayedFromStream = false
      const speechOn = chatSpeechRef.current
      const surfaceMode: ChatSurfaceMode = voiceEnabled ? 'voice' : chatSurfaceMode

      if (speechOn) unlockChatSpeechPlayback()

      streamAbortRef.current?.abort()
      const abortCtl = new AbortController()
      streamAbortRef.current = abortCtl

      try {
        await streamMessage(
          chat.activeChat.id,
          payload,
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
            setOperationProgress((prev) => {
              const logs = prev?.logs ?? []
              const line = ev.message.trim()
              const nextLogs =
                line && (logs.length === 0 || logs[logs.length - 1] !== line)
                  ? [...logs, line].slice(-12)
                  : logs
              return {
                phase: ev.phase,
                message: ev.message,
                current: ev.current,
                total: ev.total,
                percent: ev.percent,
                logs: nextLogs,
              }
            })
          }
          if (ev.type === 'log') {
            const stamp = new Date().toLocaleTimeString('ru-RU', { hour12: false })
            const line = `[${ev.tool}] ${ev.message}`
            setThinkingTrace((prev) =>
              prev.includes(line) ? prev : [...prev, line].slice(-40),
            )
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
          if (ev.type === 'think') {
            setThinkingTrace((prev) =>
              prev[prev.length - 1] === ev.line ? prev : [...prev, ev.line].slice(-40),
            )
          }
          if (ev.type === 'tts' && speechOn && ev.audioUrl && chatSpeechRef.current) {
            pendingSpeechAudioUrl = ev.audioUrl
            speechPlayedFromStream = true
            void enqueueChatSpeech(ev.audioUrl)
          }
          if (ev.type === 'speak' && speechOn && ev.text && chatSpeechRef.current) {
            pendingSpeechText = ev.text
            speakChatContent(ev.text)
            speechPlayedFromStream = true
            pendingSpeechAudioUrl = null
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
            setThinkingTrace([])
            const speechText =
              typeof ev.meta?.speech_text === 'string' ? ev.meta.speech_text : pendingSpeechText
            const finalMessage = {
              ...ev.message,
              audioUrl: pendingSpeechAudioUrl ?? undefined,
              speechText: speechText ?? undefined,
              speechPlayed: speechPlayedFromStream || undefined,
            }
            if (streamId) chat.replaceMessage(chat.activeChat!.id, streamId, finalMessage)
            else chat.appendMessage(chat.activeChat!.id, finalMessage)
            pendingSpeechAudioUrl = null
            pendingSpeechText = null
            speechPlayedFromStream = false
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
          if (ev.type === 'error') {
            setThinkingTrace([])
            setError(ev.message)
          }
          },
          insultRequestId,
          { signal: abortCtl.signal, chatSurfaceMode: surfaceMode },
        )
        void refresh()
      } catch (e) {
        if (!(e instanceof DOMException && e.name === 'AbortError')) {
          setError(e instanceof Error ? e.message : 'Ошибка')
        }
      } finally {
        if (streamAbortRef.current === abortCtl) streamAbortRef.current = null
        setChatSyncPaused(false)
        setIsThinking(false)
        setOperationProgress(null)
        setThinkingTrace([])
        setAgent((a) => ({
          ...a,
          status: voiceEnabled ? 'Listening...' : 'IDLE',
        }))
      }
    },
    [chat, connected, insultBootDone, mode, setAgent, refresh, voiceEnabled, chatSurfaceMode],
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
          } else if (f.type === 'chat_image') {
            const block = [
              `[Изображение ${f.name}]`,
              f.analysis ? String(f.analysis) : '',
              f.markdown ? String(f.markdown) : f.url ? `![](${f.url})` : '',
              f.image_id ? `(image_id: ${f.image_id})` : '',
            ]
              .filter(Boolean)
              .join('\n')
            pendingAttachRef.current = pendingAttachRef.current
              ? `${pendingAttachRef.current}\n\n${block}`
              : block
            void logSystem(`🖼️ Картинка «${f.name}» загружена.`, {
              detail: f.analysis ? String(f.analysis) : 'Опишите, что сделать: обрезать, формат, фон.',
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

  const handleChatSurfaceModeChange = useCallback(
    (next: ChatSurfaceMode) => {
      if (next === 'voice' && !voiceAccessGranted()) {
        setVoiceAccessOpen(true)
        return
      }
      writeChatSurfaceMode(next)
      setChatSurfaceMode(next)
      if (next === 'voice' && !voiceEnabled) {
        void handleVoiceToggle()
      } else if (next === 'text' && voiceEnabled) {
        resetVoiceListening()
      }
    },
    [voiceEnabled, handleVoiceToggle, resetVoiceListening],
  )

  const handleOpenJarvisGame = useCallback(async () => {
    if (!connected) {
      setError('Backend недоступен — запустите start.bat')
      return
    }
    try {
      await openJarvisGame()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось открыть 2D-игру Jarvis')
    }
  }, [connected])

  const handleCloseGameWindow = useCallback(() => {
    window.close()
  }, [])

  const handleOpenMainUi = useCallback(() => {
    window.location.href = '/'
  }, [])

  const chatAreaProps = {
    agent,
    chat: chat.activeChat,
    sessionTokens: agent.sessionTokens,
    isThinking,
    thinkingTrace,
    operationProgress,
    disabled: !connected,
    connected,
    startupHealthReport,
    startupReportDismissed,
    memory: agent.memory,
    onMemoryChange: () => void refresh(),
    onSystemLog: (t: string) => void logSystem(t),
    accountantMode: mode === 'accountant',
    marketerMode: mode === 'marketer',
    jarvisVoiceOn: voiceEnabled,
    voiceDraft,
    onSend: (t: string) => void handleSend(t),
    onAttach: (f: FileList) => void handleAttach(f),
    onClearContext: () => void handleClearContext(),
    clearingContext,
    chatSurfaceMode,
  } as const

  if (gameMode) {
    return (
      <TooltipProvider>
        <div className="flex h-[100dvh] max-h-[100dvh] min-h-0 flex-col overflow-hidden bg-background">
          <JarvisGameTopPanel
            agentView={screenModel.agentView}
            health={screenModel.health}
            avatarAnim={screenModel.screenBodyProps.avatarAnim}
            allBars={screenModel.screenBodyProps.allBars}
            onMoodRestart={() => void handleMoodRestart()}
            onCloseGame={handleCloseGameWindow}
            onOpenMainUi={handleOpenMainUi}
          />
          <JarvisGameGrid
            avatarAnim={screenModel.screenBodyProps.avatarAnim}
            avatarCls={screenModel.screenBodyProps.avatarCls}
            bubble={screenModel.screenBodyProps.bubble}
          />
          <div className="flex h-[min(42vh,22rem)] min-h-[12rem] shrink-0 flex-col border-t border-border">
            <ChatArea {...chatAreaProps} embedded />
          </div>
          {(error || chat.error) && (
            <div className="shrink-0 bg-destructive/10 px-3 py-1 text-center text-xs text-destructive">
              {error ?? chat.error}
            </div>
          )}
        </div>
      </TooltipProvider>
    )
  }

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
        <Sidebar
          agent={agent}
          connected={connected}
          chatMessages={chatMessages}
          chatSurfaceMode={chatSurfaceMode}
          onChatSurfaceModeChange={handleChatSurfaceModeChange}
          jarvisVoiceOn={voiceEnabled}
          voiceListenStatus={voiceListenStatus}
          voicePaused={voiceSpeaking && voiceEnabled}
          onVoiceToggle={() => void handleVoiceToggle()}
          onOpenSettings={() => setSettingsOpen(true)}
          onSystemLog={(t) => void logSystem(t)}
          onExpandJarvisFullscreen={() => void handleOpenJarvisGame()}
          onMoodRestart={() => void handleMoodRestart()}
          onMenuNavigate={({ sectionDomId }) => {
            setSettingsOpen(true)
            setSettingsScrollDomId(sectionDomId)
          }}
        />
        <ChatArea {...chatAreaProps} />
      </div>

      <VoiceAccessDialog
        open={voiceAccessOpen}
        onOpenChange={setVoiceAccessOpen}
        onGranted={() => {
          writeChatSurfaceMode('voice')
          setChatSurfaceMode('voice')
          void handleVoiceToggle()
        }}
      />

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
