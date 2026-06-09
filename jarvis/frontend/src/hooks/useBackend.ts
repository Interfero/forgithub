import { useCallback, useEffect, useRef, useState } from 'react'
import {
  checkHealth,
  fetchStatus,
  triggerChromiumInstall,
  triggerGoogleChromeInstall,
} from '@/api/client'
import type { AgentState } from '@/types'

/** Полный статус UI — не чаще 1 раза в 3 с (без ускорения при загрузке Qwen). */
const STATUS_POLL_MS = 3000

/** После 3 неудачных опросов подряд: пауза 30 с, затем 60 с. */
const BACKOFF_AFTER_FAILS = 3
const BACKOFF_MS_FIRST = 30_000
const BACKOFF_MS_NEXT = 60_000

const defaultState: AgentState = {
  status: 'IDLE',
  insult: {
    sessionCount: 0,
    threshold: 3,
    offended: false,
    offendedUntil: null,
    angryUntil: null,
    offendedRemainingSec: 0,
  },
  mood: {
    score: 0,
    min: -50,
    max: 50,
    tier: 'neutral',
    tierLabel: 'Нейтрально',
    canRestart: false,
    isCritical: false,
    isRadiant: false,
  },
  sessionTokens: 0,
  model: '',
  qwen: {
    label: 'Qwen 2.5 14B',
    status: 'off',
    statusLabel: 'Не подключена',
    message: '',
    value: '—',
    ready: false,
    filesPresent: false,
    filesPath: null,
    filesBytes: 0,
    ollamaReachable: false,
    ollamaModelLoaded: false,
    ollamaModelName: null,
    ollamaExpectedModel: 'qwen2.5:14b',
    ollamaError: null,
    downloadPhase: 'idle',
    downloadProgress: 0,
    downloadMessage: '',
    downloadBytesDone: 0,
    downloadBytesTotal: 0,
    ramPhase: 'idle',
    ramProgress: 0,
    ramMessage: '',
    ramEnabled: false,
    ramUsable: false,
  },
  backendStatus: 'connecting',
  chromiumBrowser: {
    playwrightInstalled: false,
    browserInstalled: false,
    ready: false,
    statusLabel: '—',
    detail: '',
    installPhase: 'idle',
    installProgress: 0,
    installMessage: '',
    installInProgress: false,
    installError: null,
  },
  googleChrome: {
    requiredOnWindows: false,
    installed: false,
    ready: false,
    executablePath: null,
    statusLabel: '—',
    detail: '',
    installPhase: 'idle',
    installMessage: '',
    installInProgress: false,
    installError: null,
  },
  ramUsage: {
    jarvisRssBytes: 0,
    jarvisRssMb: 0,
    totalRamMb: 0,
    jarvisPercentOfTotal: 0,
    systemUsedPercent: 0,
    systemUsedMb: 0,
    processCount: 0,
    launching: true,
    servicesActive: false,
    processes: [],
    qwenRamLoading: false,
    loadTargetMb: 0,
    loadProgressPercent: 0,
    loadBaselineMb: 0,
  },
  mode: 'standard',
  voiceEnabled: false,
  voiceListening: false,
  chatSpeechEnabled: false,
  deepseekConfigured: false,
  ideogramConfigured: false,
  mediaImageReady: false,
  mediaVideoReady: false,
  nanobananaConfigured: false,
  openaiConfigured: false,
  perplexityConfigured: false,
  perplexityUsable: false,
  xaiConfigured: false,
  voiceBase: {
    exists: false,
    path: null,
    filename: null,
    source: 'unknown',
    activeStudioSlot: null,
    sizeBytes: 0,
    version: 0,
  },
  xtts: {
    status: 'idle',
    progress: 0,
    message: '',
    error: null,
    detail: null,
    importable: false,
    pythonOkForXtts: true,
  },
  chatVoice: {
    ready: false,
    edgeTts: false,
    xttsReady: false,
    sileroReady: false,
    engine: 'silero',
    model: 'v5_ru',
    speaker: 'aidar',
    tempo: 1.0,
    message: '—',
    speakerSource: null,
  },
  stt: {
    ready: false,
    loading: false,
    packageInstalled: false,
    gigaamInstalled: false,
    gigaamActive: false,
    gigaamV3: false,
    ffmpeg: false,
    engine: 'gigaam',
    model: 'GigaAM-v3',
    message: '—',
    error: null,
  },
  memory: {
    conscious: [],
    unconscious: [],
    modeAccountant: [],
    modeMarketer: [],
  },
  toolLogs: [],
  telegram: {
    enabled: false,
    status: 'off',
    statusLabel: 'Выключен',
    lastEvent: '',
    blocklistIds: [],
    error: null,
    botTokenConfigured: false,
    botUsername: null,
    ready: false,
  },
  avito: {
    enabled: false,
    status: 'off',
    statusLabel: 'Выключен',
    lastEvent: '',
    error: null,
    lastSyncDate: null,
    itemsSynced: 0,
    clientIdConfigured: false,
    clientSecretConfigured: false,
    userId: '',
    ready: false,
  },
  mail: {
    enabled: false,
    ready: false,
    status: 'off',
    statusLabel: 'Выключено',
    lastEvent: '',
    accounts: [],
    slots: [
      { slot: 1, provider: 'gmail', label: 'Google Gmail' },
      { slot: 2, provider: 'yandex', label: 'Яндекс Почта' },
      { slot: 3, provider: 'icloud', label: 'Apple iCloud' },
      { slot: 4, provider: 'mailru', label: 'Mail.ru' },
      { slot: 5, provider: 'legacy', label: 'IMAP (legacy)' },
    ].map(({ slot, provider, label }) => ({
      slot,
      id: `mail-${provider}`,
      provider,
      label,
      email: '',
      enabled: false,
      configured: false,
      status: 'off',
      statusLabel: 'Не настроен',
      lastEvent: '',
      error: null,
    })),
  },
  telephony: {
    enabled: false,
    status: 'off',
    statusLabel: 'Выключено',
    lastEvent: '',
    greetingReady: false,
    webhookSecretConfigured: false,
    mangoApiKeyConfigured: false,
    publicBaseUrl: '',
  },
}

export function useBackend() {
  const [agent, setAgent] = useState<AgentState>(defaultState)
  const [connected, setConnected] = useState(false)
  const busyRef = useRef(false)
  const failStreakRef = useRef(0)
  const backoffUntilRef = useRef(0)
  const backoffTierRef = useRef(0)
  const chromiumKickAtRef = useRef(0)
  const chromeKickAtRef = useRef(0)

  const refresh = useCallback(async (options?: { force?: boolean }) => {
    if (busyRef.current && !options?.force) return
    if (!options?.force && Date.now() < backoffUntilRef.current) return

    busyRef.current = true
    setAgent((a) => ({
      ...a,
      backendStatus: a.backendStatus === 'connected' ? 'connected' : 'connecting',
    }))
    let ok = false
    try {
      ok = await checkHealth()
      if (!ok) {
        failStreakRef.current += 1
        if (failStreakRef.current >= BACKOFF_AFTER_FAILS) {
          const pause =
            backoffTierRef.current === 0 ? BACKOFF_MS_FIRST : BACKOFF_MS_NEXT
          backoffUntilRef.current = Date.now() + pause
          backoffTierRef.current = Math.min(2, backoffTierRef.current + 1)
          failStreakRef.current = 0
          setConnected(false)
          setAgent((a) => ({
            ...a,
            backendStatus: 'disconnected',
            status: 'IDLE',
          }))
        } else {
          setAgent((a) => ({
            ...a,
            backendStatus:
              a.backendStatus === 'connected' ? 'connected' : 'connecting',
          }))
        }
        return
      }

      // Сервер отвечает — баннер «запустите start.bat» только при мёртвом процессе.
      failStreakRef.current = 0
      backoffTierRef.current = 0
      backoffUntilRef.current = 0
      setConnected(true)
      setAgent((a) => ({
        ...a,
        backendStatus: 'connected',
      }))

      try {
        const prev = await fetchStatus()
        const ch = prev.chromiumBrowser
        if (!ch.ready && !ch.installInProgress) {
          const now = Date.now()
          if (now - chromiumKickAtRef.current > 12_000) {
            chromiumKickAtRef.current = now
            void triggerChromiumInstall().catch(() => {})
          }
        }
        const gc = prev.googleChrome
        if (gc.requiredOnWindows && !gc.ready && !gc.installInProgress) {
          const now = Date.now()
          const retryMs =
            gc.installPhase === 'error' || gc.installError ? 15_000 : 60_000
          if (now - chromeKickAtRef.current > retryMs) {
            chromeKickAtRef.current = now
            void triggerGoogleChromeInstall().catch(() => {})
          }
        }
        setAgent((a) => {
          const busy =
            a.status === 'Thinking...' ||
            a.status === 'Searching Web...' ||
            a.status === 'Generating image...' ||
            a.status === 'Listening...'
          const localInsult = a.insult
          const remoteInsult = prev.insult
          let insult = remoteInsult
          if (localInsult && remoteInsult) {
            const localN = localInsult.sessionCount ?? 0
            const remoteN = remoteInsult.sessionCount ?? 0
            const sessionCount = Math.max(localN, remoteN)
            const pickLater = (
              aMs: number | null | undefined,
              bMs: number | null | undefined,
            ) => {
              const av = aMs ?? 0
              const bv = bMs ?? 0
              if (av >= bv) return aMs ?? null
              return bMs ?? null
            }
            insult = {
              ...remoteInsult,
              sessionCount,
              angryUntil: pickLater(
                localInsult.angryUntil,
                remoteInsult.angryUntil,
              ),
              offended: localInsult.offended || remoteInsult.offended,
              offendedUntil: pickLater(
                localInsult.offendedUntil,
                remoteInsult.offendedUntil,
              ),
              offendedRemainingSec: Math.max(
                localInsult.offendedRemainingSec ?? 0,
                remoteInsult.offendedRemainingSec ?? 0,
              ),
            }
          } else if (localInsult && !remoteInsult) {
            insult = localInsult
          }
          return {
            ...prev,
            insult,
            mood: prev.mood ?? a.mood,
            backendStatus: 'connected',
            status: busy ? a.status : prev.status,
          }
        })
      } catch {
        // /api/status может быть тяжёлым (Qwen/Ollama) — не сбрасываем connected.
      }
    } finally {
      busyRef.current = false
    }
  }, [])

  const agentRef = useRef(agent)
  agentRef.current = agent

  useEffect(() => {
    void refresh()
    let id = 0
    const tick = () => {
      const a = agentRef.current
      const fastRam =
        a.backendStatus === 'connected' &&
        a.qwen.ramEnabled &&
        (a.ramUsage.qwenRamLoading ||
          a.qwen.ramPhase === 'loading' ||
          a.qwen.ramPhase === 'pending' ||
          a.qwen.status === 'loading_ram')
      const fastChromium =
        a.backendStatus === 'connected' &&
        (!a.chromiumBrowser.ready ||
          (a.googleChrome.requiredOnWindows &&
            !a.googleChrome.ready))
      const delay = fastRam || fastChromium ? 1000 : STATUS_POLL_MS
      void refresh().finally(() => {
        id = window.setTimeout(tick, delay)
      })
    }
    id = window.setTimeout(tick, STATUS_POLL_MS)
    return () => window.clearTimeout(id)
  }, [refresh])

  return { agent, setAgent, connected, refresh }
}
