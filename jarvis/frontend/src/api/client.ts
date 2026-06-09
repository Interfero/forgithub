import { mapMoodFromApi } from '@/lib/jarvisMood'
import type {
  AgentMode,
  AgentState,
  AppSettings,
  Chat,
  MemoryStoreId,
  MemoryFileContent,
  MemoryStores,
  Message,
  MessageRole,
  NotifyImportance,
  LocalQwenState,
  JarvisInsultState,
  JarvisMoodState,
  JarvisRamUsage,
  JarvisProcessInfo,
  AvitoConfig,
  AvitoState,
  TelegramConfig,
  TelegramState,
  TelephonyConfig,
  VoiceSlot,
} from '@/types'
import type { ChatSurfaceMode } from '@/lib/chatSurfaceMode'

function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  if (typeof window !== 'undefined' && window.location?.origin) {
    return `${window.location.origin}${p}`
  }
  return p
}

/** Сообщение об обрыве связи с backend (fetch / SSE). */
export function formatJarvisNetworkError(err: unknown): string {
  const raw =
    err instanceof Error
      ? err.message
      : typeof err === 'string'
        ? err
        : 'Неизвестная ошибка'
  const low = raw.toLowerCase()
  if (
    low.includes('network error') ||
    low.includes('failed to fetch') ||
    low.includes('load failed') ||
    low.includes('networkerror') ||
    low.includes('aborted')
  ) {
    return (
      'Связь с Jarvis прервалась (network error). Сервер мог долго собирать отчёт — ' +
      'обновите страницу (Ctrl+F5) и повторите. Если повторяется: restart.bat, затем «синхронизируй авито».'
    )
  }
  return raw
}

type ApiChat = {
  id: string
  title: string
  updated_at: string
  messages: Array<{
    id: string
    role: MessageRole
    content: string
    created_at: string
    notify_level?: NotifyImportance
  }>
}

function mapChat(c: ApiChat): Chat {
  return {
    id: c.id,
    title: c.title,
    updatedAt: c.updated_at,
    messages: c.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      createdAt: m.created_at,
      notifyLevel: m.notify_level,
    })),
  }
}

async function json<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = 0,
): Promise<T> {
  const ctrl = timeoutMs > 0 ? new AbortController() : null
  const timer =
    ctrl && timeoutMs > 0
      ? window.setTimeout(() => ctrl.abort(), timeoutMs)
      : null
  try {
    const res = await fetch(apiUrl(path), {
      ...init,
      signal: ctrl?.signal,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
    const contentType = res.headers.get('content-type') || ''
    if (!res.ok) {
      const text = await res.text()
      if (contentType.includes('application/json') && text) {
        try {
          const errBody = JSON.parse(text) as { detail?: string | unknown; message?: string }
          const detail =
            typeof errBody.detail === 'string'
              ? errBody.detail
              : typeof errBody.message === 'string'
                ? errBody.message
                : undefined
          if (detail) throw new Error(detail)
        } catch (e) {
          if (e instanceof Error && !(e instanceof SyntaxError)) throw e
        }
      }
      if (text.trimStart().startsWith('<!')) {
        throw new Error(
          'Сервер вернул HTML вместо API. Перезапустите Jarvis (restart.bat) и обновите страницу (Ctrl+F5).',
        )
      }
      throw new Error(text.slice(0, 280) || `HTTP ${res.status}`)
    }
    if (!contentType.includes('application/json')) {
      const text = await res.text()
      if (text.trimStart().startsWith('<!')) {
        throw new Error(
          'Ответ не JSON (похоже на страницу сайта). Откройте интерфейс Jarvis после restart.bat (Ctrl+F5).',
        )
      }
      throw new Error('Сервер вернул не JSON')
    }
    return res.json() as Promise<T>
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new Error('Таймаут запроса — проверьте, что backend запущен (start.bat)')
    }
    throw new Error(formatJarvisNetworkError(e))
  } finally {
    if (timer) window.clearTimeout(timer)
  }
}

export function mapJarvisRamUsage(
  d?: {
    jarvis_rss_bytes?: number
    jarvis_rss_mb?: number
    total_ram_mb?: number
    jarvis_percent_of_total?: number
    system_used_percent?: number
    system_used_mb?: number
    process_count?: number
    launching?: boolean
    services_active?: boolean
    processes?: Array<{
      pid: number
      name: string
      role: string
      rss_bytes: number
      rss_mb: number
    }>
    qwen_ram_loading?: boolean
    load_target_mb?: number
    load_progress_percent?: number
    load_baseline_mb?: number
  } | null,
): JarvisRamUsage {
  const processes: JarvisProcessInfo[] = (d?.processes ?? []).map((p) => ({
    pid: p.pid,
    name: p.name,
    role: p.role,
    rssBytes: p.rss_bytes,
    rssMb: p.rss_mb,
  }))
  return {
    jarvisRssBytes: d?.jarvis_rss_bytes ?? 0,
    jarvisRssMb: d?.jarvis_rss_mb ?? 0,
    totalRamMb: d?.total_ram_mb ?? 0,
    jarvisPercentOfTotal: d?.jarvis_percent_of_total ?? 0,
    systemUsedPercent: d?.system_used_percent ?? 0,
    systemUsedMb: d?.system_used_mb ?? 0,
    processCount: d?.process_count ?? 0,
    launching: d?.launching ?? false,
    servicesActive: d?.services_active ?? false,
    processes,
    qwenRamLoading: d?.qwen_ram_loading ?? false,
    loadTargetMb: d?.load_target_mb ?? 0,
    loadProgressPercent: d?.load_progress_percent ?? 0,
    loadBaselineMb: d?.load_baseline_mb ?? 0,
  }
}

export async function fetchJarvisRam(): Promise<JarvisRamUsage> {
  const d = await json<Parameters<typeof mapJarvisRamUsage>[0]>(
    '/api/system/jarvis-ram',
    undefined,
    5000,
  )
  return mapJarvisRamUsage(d)
}

export async function checkHealth(): Promise<boolean> {
  try {
    await json<{ ok: boolean }>('/api/health', undefined, 2500)
    return true
  } catch {
    return false
  }
}

export async function restartJarvis(): Promise<{ ok: boolean; message?: string }> {
  return json<{ ok: boolean; message?: string }>('/api/app/restart', { method: 'POST' }, 8000)
}

/** Ждёт возврата backend после POST /api/app/restart (до ~3 мин). */
export async function waitForBackendAfterRestart(
  maxWaitMs = 180_000,
  intervalMs = 2000,
  onProgress?: (info: { elapsedMs: number; attempt: number }) => void,
): Promise<boolean> {
  const started = Date.now()
  const deadline = started + maxWaitMs
  let attempt = 0
  await new Promise((r) => setTimeout(r, 800))
  while (Date.now() < deadline) {
    attempt += 1
    onProgress?.({ elapsedMs: Date.now() - started, attempt })
    if (await checkHealth()) return true
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  onProgress?.({ elapsedMs: Date.now() - started, attempt })
  return false
}

/** Подпись этапа перезапуска для UI (по прошедшему времени). */
export function restartPhaseLabel(elapsedMs: number): string {
  const sec = Math.floor(elapsedMs / 1000)
  if (sec < 4) return 'Останавливаем сервер…'
  if (sec < 50) return 'Сборка интерфейса (npm run build)…'
  if (sec < 120) return 'Запуск backend…'
  return 'Всё ещё ждём ответ сервера…'
}

export interface NetworkStatus {
  internet_ok: boolean
  internet_detail: string
  web_search_ok: boolean
  web_search_detail: string
  uses_system_proxy: boolean
  ready: boolean
  chromium?: {
    embedded_in_jarvis: boolean
    chrome_exe_on_pc: boolean
    jarvis_uses: string
  }
}

export async function fetchNetworkStatus(): Promise<NetworkStatus> {
  return json<NetworkStatus>('/api/network', undefined, 8000)
}

export interface SessionStartupInfo {
  chat_empty: boolean
  message_count: number
  messages_cleared_on_boot: number
  recovered_unclean_shutdown: boolean
  chat_persisted?: boolean
}

export async function fetchSessionStartup(): Promise<SessionStartupInfo> {
  return json<SessionStartupInfo>('/api/session/startup', undefined, 5000)
}

function unixToMs(value: number | null | undefined): number | null {
  if (value == null || value <= 0) return null
  return value > 1e12 ? value : value * 1000
}

export function mapInsultFromApi(d: {
  session_count?: number
  threshold?: number
  offended?: boolean
  offended_until?: number | null
  angry_until?: number | null
  offended_remaining_sec?: number
}): JarvisInsultState {
  return {
    sessionCount: d.session_count ?? 0,
    threshold: d.threshold ?? 3,
    offended: d.offended ?? false,
    offendedUntil: unixToMs(d.offended_until ?? null),
    angryUntil: unixToMs(d.angry_until ?? null),
    offendedRemainingSec: d.offended_remaining_sec ?? 0,
  }
}

export interface InsultEvaluateResult {
  kind: string
  counted: boolean
  insult: JarvisInsultState
  mood?: JarvisMoodState
}

/** Регистрация оскорбления при отправке (основной путь для счётчика и анимации). */
export async function evaluateInsult(
  text: string,
  requestId: string,
  chatId?: string,
): Promise<InsultEvaluateResult> {
  const d = await json<{
    kind: string
    counted?: boolean
    insult?: Parameters<typeof mapInsultFromApi>[0]
    session_count?: number
    threshold?: number
    offended?: boolean
    offended_until?: number | null
    angry_until?: number | null
    offended_remaining_sec?: number
    moderation_response?: string
    mood?: Parameters<typeof mapMoodFromApi>[0]
  }>('/api/insult/evaluate', {
    method: 'POST',
    body: JSON.stringify({
      text,
      request_id: requestId,
      chat_id: chatId ?? null,
    }),
  })
  const insult = mapInsultFromApi(d.insult ?? d)
  return {
    kind: d.kind ?? 'none',
    counted: d.counted === true,
    insult,
    mood: d.mood ? mapMoodFromApi(d.mood) : undefined,
  }
}

/** Сброс счётчика при старте backend (без бонуса настроения). */
export async function resetInsultSession(): Promise<{
  insult: JarvisInsultState
  mood: JarvisMoodState
}> {
  const d = await json<{
    session_count?: number
    threshold?: number
    offended?: boolean
    offended_until?: number | null
    angry_until?: number | null
    offended_remaining_sec?: number
    mood?: Parameters<typeof mapMoodFromApi>[0]
  }>('/api/session/reset-insults', { method: 'POST' })
  return {
    insult: mapInsultFromApi(d),
    mood: mapMoodFromApi(d.mood ?? {}),
  }
}

/** RESTART: сброс оскорблений +30 к настроению (после порога 3/3). */
export async function restartInsultSession(): Promise<{
  insult: JarvisInsultState
  mood: JarvisMoodState
}> {
  const d = await json<{
    session_count?: number
    threshold?: number
    offended?: boolean
    offended_until?: number | null
    angry_until?: number | null
    offended_remaining_sec?: number
    mood?: Parameters<typeof mapMoodFromApi>[0]
  }>('/api/insult/restart', { method: 'POST' })
  return {
    insult: mapInsultFromApi(d),
    mood: mapMoodFromApi(d.mood ?? {}),
  }
}

export async function triggerChromiumInstall() {
  return json<{ started?: boolean }>(
    '/api/system/chromium-browser/install',
    { method: 'POST' },
    120_000,
  )
}

export async function triggerGoogleChromeInstall() {
  return json<{ started?: boolean }>(
    '/api/system/google-chrome/install',
    { method: 'POST' },
    900_000,
  )
}

export async function fetchSystemHealthReport(): Promise<{ content: string }> {
  return json<{ content: string }>('/api/system/health-report', undefined, 30_000)
}

export async function openJarvisGame(): Promise<{ ok: boolean; url: string }> {
  return json<{ ok: boolean; url: string }>('/api/system/open-game', { method: 'POST' })
}

export async function fetchStatus(): Promise<AgentState> {
  const d = await json<{
    edition?: 'free' | 'pro'
    edition_label?: string
    deepseek_bundled?: boolean
    backend_status: string
    status: AgentState['status']
    session_tokens: number
    model: string
    mode: AgentMode
    voice_enabled: boolean
    voice_listening: boolean
    chat_speech_enabled: boolean
    deepseek_configured?: boolean
    neural_ready?: boolean
    qwen_ready?: boolean
    chat_llm_ready?: boolean
    chat_mode_label?: string
    chat_mode_detail?: string
    ideogram_configured?: boolean
    ideogram_usable?: boolean
    media_image_ready?: boolean
    media_video_ready?: boolean
    deepseek_active?: boolean
    deepseek_usable?: boolean
    nanobanana_configured?: boolean
    openai_configured?: boolean
    perplexity_configured?: boolean
    perplexity_usable?: boolean
    xai_configured?: boolean
    telephony?: {
      enabled: boolean
      status?: string
      status_label?: string
      last_event?: string
      greeting_ready?: boolean
      webhook_secret_configured?: boolean
      mango_api_key_configured?: boolean
      public_base_url?: string
    }
    qwen?: Parameters<typeof mapQwenStatus>[0]
    qwen_ram_enabled?: boolean
    voice_base: {
      exists: boolean
      path: string | null
      filename: string | null
      source: string
      active_studio_slot: number | null
      size_bytes: number
      version?: number
    }
    xtts: Parameters<typeof mapXttsStatus>[0]
    stt?: Parameters<typeof mapSttStatus>[0]
    tool_logs: ToolLogEntry[]
    telegram: {
      enabled: boolean
      status: TelegramState['status']
      status_label: string
      last_event: string
      blocklist_ids: string[]
      error: string | null
      bot_username: string | null
      bot_token_configured: boolean
      bot_logic_configured?: boolean
      bot_logic_valid?: boolean
      bot_logic_error?: string | null
      bot_logic_name?: string | null
      messages_handled?: number
      polling_active?: boolean
      ready: boolean
    }
    mail?: {
      enabled: boolean
      ready: boolean
      status: string
      status_label: string
      last_event: string
      slots: Array<{
        slot: number
        id: string | null
        label: string
        email: string
        enabled: boolean
        configured: boolean
        status: string
        status_label: string
        last_event: string
        error: string | null
      }>
    }
    avito: {
      enabled: boolean
      status: AvitoState['status']
      status_label: string
      last_event: string
      error: string | null
      last_sync_date: string | null
      items_synced: number
      client_id_configured: boolean
      client_secret_configured: boolean
      user_id: string
      ready: boolean
      chats_in_db?: number
      messages_in_db?: number
      last_chats_sync_at?: string | null
    }
    memory?: {
      conscious: Array<{ id: string; name: string; size_bytes: number; store: string }>
      unconscious: Array<{ id: string; name: string; size_bytes: number; store: string }>
      mode_standard?: Array<{ id: string; name: string; size_bytes: number; store: string }>
      mode_accountant?: Array<{ id: string; name: string; size_bytes: number; store: string }>
      mode_marketer?: Array<{ id: string; name: string; size_bytes: number; store: string }>
    }
    chromium_browser?: {
      playwright_installed: boolean
      browser_installed: boolean
      ready: boolean
      status_label: string
      detail: string
      install_phase?: string
      install_progress?: number
      install_message?: string
      install_in_progress?: boolean
      install_error?: string | null
      system_internet_ok?: boolean
      system_internet_detail?: string
    }
    net?: {
      internet_ok: boolean
      internet_detail: string
    }
    google_chrome?: {
      required_on_windows: boolean
      installed: boolean
      ready: boolean
      executable_path: string | null
      status_label: string
      detail: string
      install_phase?: string
      install_message?: string
      install_in_progress?: boolean
      install_error?: string | null
    }
    ram_usage?: {
      jarvis_rss_bytes: number
      jarvis_rss_mb: number
      total_ram_bytes: number
      total_ram_mb: number
      jarvis_percent_of_total: number
      system_used_percent: number
      system_used_mb: number
      process_count: number
      launching: boolean
      services_active: boolean
      processes?: Array<{
        pid: number
        name: string
        role: string
        rss_bytes: number
        rss_mb: number
      }>
      qwen_ram_loading?: boolean
      load_target_mb?: number
      load_progress_percent?: number
      load_baseline_mb?: number
    }
    session_count?: number
    threshold?: number
    offended?: boolean
    offended_until?: number | null
    angry_until?: number | null
    offended_remaining_sec?: number
    mood?: Parameters<typeof mapMoodFromApi>[0]
    router?: {
      last_intent?: string | null
      last_engine?: string | null
    }
  }>('/api/status', undefined, 8000)

  return {
    edition: d.edition,
    editionLabel: d.edition_label,
    deepseekBundled: d.deepseek_bundled,
    router: {
      lastIntent: d.router?.last_intent ?? null,
      lastEngine: d.router?.last_engine ?? null,
    },
    status: d.status,
    insult: mapInsultFromApi(d),
    mood: mapMoodFromApi(d.mood ?? {}),
    sessionTokens: d.session_tokens,
    model: d.model,
    neuralReady: d.neural_ready ?? false,
    qwenReady: d.qwen_ready ?? d.qwen?.ready ?? false,
    chatLlmReady: d.chat_llm_ready ?? d.neural_ready ?? false,
    chatModeLabel: d.chat_mode_label ?? '',
    chatModeDetail: d.chat_mode_detail ?? '',
    qwen: {
      ...mapQwenStatus(d.qwen),
      ramEnabled: d.qwen?.ram_enabled ?? d.qwen_ram_enabled ?? false,
      ramUsable: d.qwen?.ram_usable ?? false,
    },
    backendStatus: d.backend_status === 'connected' ? 'connected' : 'disconnected',
    mode: d.mode,
    voiceEnabled: d.voice_enabled,
    voiceListening: d.voice_listening,
    chatSpeechEnabled: d.chat_speech_enabled ?? false,
    deepseekConfigured: d.deepseek_configured,
    deepseekActive: d.deepseek_active ?? true,
    deepseekUsable: d.deepseek_usable ?? d.deepseek_configured,
    nanobananaConfigured: d.nanobanana_configured ?? false,
    ideogramConfigured: d.ideogram_configured ?? false,
    ideogramActive: d.ideogram_active ?? false,
    ideogramUsable: d.ideogram_usable ?? false,
    mediaImageReady: d.media_image_ready ?? false,
    mediaVideoReady: d.media_video_ready ?? false,
    openaiConfigured: d.openai_configured ?? false,
    perplexityConfigured: d.perplexity_configured ?? false,
    perplexityUsable: d.perplexity_usable ?? false,
    xaiConfigured: d.xai_configured ?? false,
    voiceBase: {
      exists: d.voice_base.exists,
      path: d.voice_base.path,
      filename: d.voice_base.filename,
      source: d.voice_base.source,
      activeStudioSlot: d.voice_base.active_studio_slot,
      sizeBytes: d.voice_base.size_bytes,
      version: d.voice_base.version ?? 0,
    },
    xtts: mapXttsStatus(d.silero ?? d.xtts),
    chatVoice: mapChatVoiceReadiness(d.chat_voice ?? {}),
    stt: mapSttStatus(d.stt ?? {}),
    memory: mapMemoryFromApi(d.memory),
    toolLogs: d.tool_logs,
    telegram: {
      enabled: d.telegram.enabled,
      status: d.telegram.status,
      statusLabel: d.telegram.status_label,
      lastEvent: d.telegram.last_event,
      blocklistIds: d.telegram.blocklist_ids ?? [],
      error: d.telegram.error,
      botTokenConfigured: d.telegram.bot_token_configured ?? false,
      botUsername: d.telegram.bot_username ?? null,
      botLogicConfigured: d.telegram.bot_logic_configured ?? false,
      botLogicValid: d.telegram.bot_logic_valid ?? false,
      botLogicError: d.telegram.bot_logic_error ?? null,
      botLogicName: d.telegram.bot_logic_name ?? null,
      messagesHandled: d.telegram.messages_handled ?? 0,
      pollingActive: d.telegram.polling_active ?? false,
      ready: d.telegram.ready ?? false,
    },
    mail: {
      enabled: d.mail?.enabled ?? false,
      ready: d.mail?.ready ?? false,
      status: d.mail?.status ?? 'off',
      statusLabel: d.mail?.status_label ?? 'Выключено',
      lastEvent: d.mail?.last_event ?? '',
      accounts: [],
      slots: (d.mail?.slots ?? []).map((s) => ({
        slot: s.slot,
        id: s.id,
        provider: s.provider,
        label: s.label,
        email: s.email,
        enabled: s.enabled,
        configured: s.configured,
        status: s.status,
        statusLabel: s.status_label,
        lastEvent: s.last_event,
        error: s.error,
      })),
    },
    avito: {
      enabled: d.avito?.enabled ?? false,
      status: (d.avito?.status ?? 'off') as AvitoState['status'],
      statusLabel: d.avito?.status_label ?? 'Выключен',
      lastEvent: d.avito?.last_event ?? '',
      error: d.avito?.error ?? null,
      lastSyncDate: d.avito?.last_sync_date ?? null,
      itemsSynced: d.avito?.items_synced ?? 0,
      clientIdConfigured: d.avito?.client_id_configured ?? false,
      clientSecretConfigured: d.avito?.client_secret_configured ?? false,
      userId: d.avito?.user_id ?? '',
      ready: d.avito?.ready ?? false,
      chatsInDb: d.avito?.chats_in_db ?? 0,
      messagesInDb: d.avito?.messages_in_db ?? 0,
      lastChatsSyncAt: d.avito?.last_chats_sync_at ?? null,
    },
    telephony: {
      enabled: d.telephony?.enabled ?? false,
      status: d.telephony?.status ?? 'off',
      statusLabel: d.telephony?.status_label ?? 'Выключено',
      lastEvent: d.telephony?.last_event ?? '',
      greetingReady: d.telephony?.greeting_ready ?? false,
      webhookSecretConfigured: d.telephony?.webhook_secret_configured ?? false,
      mangoApiKeyConfigured: d.telephony?.mango_api_key_configured ?? false,
      publicBaseUrl: d.telephony?.public_base_url ?? '',
    },
    ramUsage: mapJarvisRamUsage(d.ram_usage),
    chromiumBrowser: {
      playwrightInstalled: d.chromium_browser?.playwright_installed ?? false,
      browserInstalled: d.chromium_browser?.browser_installed ?? false,
      ready: d.chromium_browser?.ready ?? false,
      statusLabel: d.chromium_browser?.status_label ?? '—',
      detail: d.chromium_browser?.detail ?? '',
      installPhase: d.chromium_browser?.install_phase ?? 'idle',
      installProgress: d.chromium_browser?.install_progress ?? 0,
      installMessage: d.chromium_browser?.install_message ?? '',
      installInProgress: d.chromium_browser?.install_in_progress ?? false,
      installError: d.chromium_browser?.install_error ?? null,
      systemInternetOk: d.chromium_browser?.system_internet_ok ?? null,
      systemInternetDetail: d.chromium_browser?.system_internet_detail ?? '',
    },
    net: {
      internetOk: d.net?.internet_ok ?? false,
      internetDetail: d.net?.internet_detail ?? '',
    },
    googleChrome: {
      requiredOnWindows: d.google_chrome?.required_on_windows ?? false,
      installed: d.google_chrome?.installed ?? false,
      ready: d.google_chrome?.ready ?? false,
      executablePath: d.google_chrome?.executable_path ?? null,
      statusLabel: d.google_chrome?.status_label ?? '—',
      detail: d.google_chrome?.detail ?? '',
      installPhase: d.google_chrome?.install_phase ?? 'idle',
      installMessage: d.google_chrome?.install_message ?? '',
      installInProgress: d.google_chrome?.install_in_progress ?? false,
      installError: d.google_chrome?.install_error ?? null,
    },
  }
}

type ToolLogEntry = AgentState['toolLogs'][number]

export async function setMode(mode: AgentMode) {
  return json<{ mode: string; log_message: string }>('/api/agent/mode', {
    method: 'PUT',
    body: JSON.stringify({ mode }),
  })
}

export async function setVoiceEnabled(enabled: boolean) {
  return json<{ voice_enabled: boolean; chat_speech_enabled: boolean }>('/api/agent/voice', {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
}

export interface VoiceTranscribeResult {
  text: string
  command: string
  wake_found: boolean
  stop_command?: boolean
  language?: string
  duration_sec?: number
}

export async function transcribeVoiceAudio(blob: Blob, filename = 'speech.webm'): Promise<VoiceTranscribeResult> {
  const form = new FormData()
  form.append('file', blob, filename)
  const res = await fetch(apiUrl('/api/voice/transcribe'), { method: 'POST', body: form })
  if (!res.ok) {
    const raw = await res.text()
    let msg = raw || `STT ${res.status}`
    try {
      const parsed = JSON.parse(raw) as { detail?: string }
      if (parsed.detail) msg = parsed.detail
    } catch {
      /* plain text */
    }
    throw new Error(msg)
  }
  return res.json() as Promise<VoiceTranscribeResult>
}

export async function fetchVoiceReadiness(): Promise<{
  ready?: boolean
  dialog_ready?: boolean
  message?: string
  stt?: { package_installed?: boolean; ffmpeg?: boolean; message?: string }
}> {
  return json('/api/voice/readiness')
}

export async function setChatSpeechEnabled(enabled: boolean) {
  return json<{ chat_speech_enabled: boolean }>('/api/agent/chat-speech', {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
}

export async function setQwenRamEnabled(enabled: boolean) {
  return json<Record<string, unknown>>('/api/agent/qwen-ram', {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
}

export type QwenDownloadProgress = {
  phase: string
  progress: number
  message: string
  bytesDone: number
  bytesTotal: number
  filesPresent: boolean
}

export async function fetchQwenDownloadProgress(): Promise<QwenDownloadProgress> {
  const d = await json<{
    phase?: string
    progress?: number
    message?: string
    bytes_done?: number
    bytes_total?: number
    files_present?: boolean
  }>('/api/agent/qwen-download/status', undefined, 8000)
  return {
    phase: d.phase ?? 'idle',
    progress: d.progress ?? 0,
    message: d.message ?? '',
    bytesDone: d.bytes_done ?? 0,
    bytesTotal: d.bytes_total ?? 0,
    filesPresent: Boolean(d.files_present),
  }
}

export async function startQwenModelDownload(force = false) {
  const q = force ? '?force=true' : ''
  return json<{
    ok?: boolean
    skipped?: boolean
    started?: boolean
    already_installed?: boolean
    in_progress?: boolean
    download_phase?: string
    download_progress?: number
    download_message?: string
    message?: string
  }>(`/api/agent/qwen-download${q}`, { method: 'POST' }, 30_000)
}

/** @deprecated use startQwenModelDownload */
export async function downloadQwenModel(force = false) {
  return startQwenModelDownload(force)
}

let voicePreviewAudio: HTMLAudioElement | null = null
let voicePreviewObjectUrl: string | null = null

export async function playVoicePreview(): Promise<HTMLAudioElement | null> {
  stopVoicePreview()
  try {
    const res = await fetch(apiUrl(`/api/voice/preview?t=${Date.now()}`), {
      cache: 'no-store',
    })
    if (!res.ok) return null
    const blob = await res.blob()
    if (!blob.size) return null
    const mime = res.headers.get('Content-Type') || blob.type || 'audio/ogg'
    voicePreviewObjectUrl = URL.createObjectURL(
      blob.type ? blob : new Blob([blob], { type: mime }),
    )
    const audio = new Audio(voicePreviewObjectUrl)
    voicePreviewAudio = audio
    await audio.play()
    return audio
  } catch {
    stopVoicePreview()
    return null
  }
}

export function stopVoicePreview() {
  if (voicePreviewAudio) {
    voicePreviewAudio.pause()
    voicePreviewAudio.currentTime = 0
    voicePreviewAudio = null
  }
  if (voicePreviewObjectUrl) {
    URL.revokeObjectURL(voicePreviewObjectUrl)
    voicePreviewObjectUrl = null
  }
}

export function isVoicePreviewPlaying(): boolean {
  return voicePreviewAudio != null && !voicePreviewAudio.paused
}

function mapMemoryFile(
  f: { id: string; name: string; size_bytes: number; store: string; protected?: boolean },
  store: MemoryStoreId,
) {
  return {
    id: f.id,
    name: f.name,
    sizeBytes: f.size_bytes,
    store,
    protected: f.protected ?? false,
  }
}

function mapMemoryFromApi(
  raw?: {
    conscious?: Array<{ id: string; name: string; size_bytes: number; store: string }>
    unconscious?: Array<{ id: string; name: string; size_bytes: number; store: string }>
    mode_accountant?: Array<{ id: string; name: string; size_bytes: number; store: string }>
    mode_marketer?: Array<{ id: string; name: string; size_bytes: number; store: string }>
    mode_developer?: Array<{ id: string; name: string; size_bytes: number; store: string }>
  },
): MemoryStores {
  return {
    conscious: (raw?.conscious ?? []).map((f) => mapMemoryFile(f, 'conscious')),
    unconscious: (raw?.unconscious ?? []).map((f) => mapMemoryFile(f, 'unconscious')),
    modeAccountant: (raw?.mode_accountant ?? []).map((f) => mapMemoryFile(f, 'mode-accountant')),
    modeMarketer: (raw?.mode_marketer ?? []).map((f) => mapMemoryFile(f, 'mode-marketer')),
    modeDeveloper: (raw?.mode_developer ?? []).map((f) => mapMemoryFile(f, 'mode-developer')),
  }
}

export async function postSystemLog(
  chatId: string,
  content: string,
  importance: NotifyImportance = 'important',
): Promise<Message | null> {
  if (importance === 'routine') return null
  const m = await json<{
    id: string
    role: MessageRole
    content: string
    created_at: string
    notify_level?: NotifyImportance
  }>(`/api/chats/${chatId}/system`, {
    method: 'POST',
    body: JSON.stringify({ content, importance }),
  })
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    createdAt: m.created_at,
    notifyLevel: m.notify_level ?? importance,
  }
}

export async function fetchMemory(): Promise<MemoryStores> {
  const d = await json<{
    conscious: Array<{ id: string; name: string; size_bytes: number; store: string }>
    unconscious: Array<{ id: string; name: string; size_bytes: number; store: string }>
    mode_accountant: Array<{ id: string; name: string; size_bytes: number; store: string }>
    mode_marketer: Array<{ id: string; name: string; size_bytes: number; store: string }>
  }>('/api/memory')
  return mapMemoryFromApi(d)
}

export async function uploadMemoryFile(store: MemoryStoreId, file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(apiUrl(`/api/memory/${store}/upload`), { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchMemoryFile(
  store: MemoryStoreId,
  fileId: string,
): Promise<MemoryFileContent> {
  const d = await json<{
    id: string
    name: string
    content: string
    size_bytes: number
    store: string
    protected?: boolean
  }>(`/api/memory/${store}/${encodeURIComponent(fileId)}`)
  return {
    id: d.id,
    name: d.name,
    content: d.content,
    sizeBytes: d.size_bytes,
    store,
    protected: d.protected ?? false,
  }
}

export async function deleteMemoryFile(store: MemoryStoreId, fileId: string) {
  await json(`/api/memory/${store}/${encodeURIComponent(fileId)}`, { method: 'DELETE' })
}

export async function fetchChats(): Promise<Chat[]> {
  const data = await json<ApiChat[]>('/api/chats')
  return data.map(mapChat)
}

export async function createChat(title = 'Новый диалог') {
  const c = await json<ApiChat>('/api/chats', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
  return mapChat(c)
}

export async function updateChat(id: string, title: string) {
  const c = await json<ApiChat>(`/api/chats/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
  return mapChat(c)
}

export async function deleteChat(id: string): Promise<Chat> {
  const res = await json<{ chat: ApiChat }>(`/api/chats/${id}`, { method: 'DELETE' })
  return mapChat(res.chat)
}

/** Очистить всю переписку единственного чата (контекст диалога). */
export async function clearChatContext(id: string): Promise<Chat> {
  return deleteChat(id)
}

/** Маскированный ключ с сервера не кладём в поле ввода — иначе «Сохранить» затирает секрет. */
export function isMaskedApiSecret(value: string): boolean {
  const v = (value || '').trim()
  if (!v) return true
  if (v.includes('•') || v.includes('…') || v.includes('***')) return true
  if (v.startsWith('sk-') && v.length < 24 && /[•*]/.test(v)) return true
  if (v.startsWith('pplx-') && v.length < 16 && /[•*]/.test(v)) return true
  if (v.startsWith('AIza') && v.length < 20 && /[•*]/.test(v)) return true
  return false
}

function secretFromServer(value: string): string {
  return isMaskedApiSecret(value) ? '' : value
}

function mapSettings(d: {
  provider: string
  default_model: string
  openai_key: string
  openai_model?: string
  anthropic_key: string
  deepseek_key: string
  perplexity_key?: string
  perplexity_model?: string
  xai_key?: string
  xai_model?: string
  deepseek_configured?: boolean
  openai_configured?: boolean
  perplexity_configured?: boolean
  xai_configured?: boolean
  nanobanana_key?: string
  nanobanana_configured?: boolean
  nanobanana_active?: boolean
  nanobanana_usable?: boolean
  ideogram_key?: string
  ideogram_configured?: boolean
  ideogram_active?: boolean
  ideogram_usable?: boolean
  media_image_ready?: boolean
  media_video_ready?: boolean
  deepseek_active?: boolean
  deepseek_usable?: boolean
  openai_active?: boolean
  openai_usable?: boolean
  perplexity_active?: boolean
  perplexity_usable?: boolean
  xai_active?: boolean
  xai_usable?: boolean
  xtts_active?: boolean
}): AppSettings {
  return {
    provider: d.provider,
    defaultModel: d.default_model,
    openaiKey: secretFromServer(d.openai_key),
    openaiModel: d.openai_model ?? 'gpt-5.5-instant',
    anthropicKey: secretFromServer(d.anthropic_key),
    deepseekKey: secretFromServer(d.deepseek_key),
    perplexityKey: secretFromServer(d.perplexity_key ?? ''),
    perplexityModel: d.perplexity_model ?? 'sonar',
    xaiKey: secretFromServer(d.xai_key ?? ''),
    xaiModel: d.xai_model ?? 'grok-4.20',
    deepseekConfigured: d.deepseek_configured,
    deepseekActive: d.deepseek_active ?? true,
    deepseekUsable: d.deepseek_usable,
    openaiConfigured: d.openai_configured,
    openaiActive: d.openai_active ?? false,
    openaiUsable: d.openai_usable,
    perplexityConfigured: d.perplexity_configured,
    perplexityActive: d.perplexity_active ?? false,
    perplexityUsable: d.perplexity_usable,
    xaiConfigured: d.xai_configured,
    xaiActive: d.xai_active ?? false,
    xaiUsable: d.xai_usable,
    nanobananaKey: secretFromServer(d.nanobanana_key ?? ''),
    nanobananaConfigured: d.nanobanana_configured,
    nanobananaActive: d.nanobanana_active ?? false,
    nanobananaUsable: d.nanobanana_usable,
    ideogramKey: secretFromServer(d.ideogram_key ?? ''),
    ideogramConfigured: d.ideogram_configured,
    ideogramActive: d.ideogram_active ?? false,
    ideogramUsable: d.ideogram_usable,
    mediaImageReady: d.media_image_ready,
    mediaVideoReady: d.media_video_ready,
    xttsActive: d.xtts_active ?? true,
  }
}

export async function setServiceActive(
  service: 'deepseek' | 'openai' | 'perplexity' | 'xai' | 'nanobanana' | 'ideogram' | 'xtts',
  enabled: boolean,
): Promise<AppSettings> {
  const d = await json<Parameters<typeof mapSettings>[0]>(
    `/api/settings/service/${service}/active`,
    {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    },
  )
  return mapSettings(d)
}

export async function fetchSettings(): Promise<AppSettings> {
  const d = await json<Parameters<typeof mapSettings>[0]>('/api/settings')
  return mapSettings(d)
}

function secretForSave(value: string): string {
  return isMaskedApiSecret(value) ? '' : value.trim()
}

export async function saveSettings(s: AppSettings) {
  const d = await json<Parameters<typeof mapSettings>[0]>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify({
      provider: s.provider,
      default_model: s.defaultModel,
      openai_key: secretForSave(s.openaiKey),
      openai_model: s.openaiModel,
      anthropic_key: secretForSave(s.anthropicKey),
      deepseek_key: secretForSave(s.deepseekKey),
      perplexity_key: secretForSave(s.perplexityKey),
      perplexity_model: s.perplexityModel,
      xai_key: secretForSave(s.xaiKey),
      xai_model: s.xaiModel,
      nanobanana_key: secretForSave(s.nanobananaKey),
      ideogram_key: secretForSave(s.ideogramKey),
    }),
  })
  return mapSettings(d)
}

function mapQwenStatus(
  d?: {
    label?: string
    status?: string
    status_label?: string
    message?: string
    value?: string
    ready?: boolean
    files_present?: boolean
    files_path?: string | null
    files_bytes?: number
    ollama_reachable?: boolean
    ollama_model_loaded?: boolean
    ollama_model_name?: string | null
    ollama_expected_model?: string
    ollama_error?: string | null
    download_phase?: string
    download_progress?: number
    download_message?: string
    download_bytes_done?: number
    download_bytes_total?: number
    model_meta_stale?: boolean
    expected_model_path?: string | null
    ram_phase?: string
    ram_progress?: number
    ram_message?: string
    ram_enabled?: boolean
    ram_usable?: boolean
    embedded_ready?: boolean
  } | null,
): LocalQwenState {
  return {
    label: d?.label ?? 'Qwen 2.5 14B',
    status: d?.status ?? 'off',
    statusLabel: d?.status_label ?? 'Не подключена',
    message: d?.message ?? '',
    value: d?.value ?? '—',
    ready: d?.ready ?? false,
    filesPresent: d?.files_present ?? false,
    filesPath: d?.files_path ?? null,
    filesBytes: d?.files_bytes ?? 0,
    ollamaReachable: d?.ollama_reachable ?? false,
    ollamaModelLoaded: d?.ollama_model_loaded ?? false,
    ollamaModelName: d?.ollama_model_name ?? null,
    ollamaExpectedModel: d?.ollama_expected_model ?? 'qwen2.5:14b',
    ollamaError: d?.ollama_error ?? null,
    downloadPhase: d?.download_phase ?? 'idle',
    downloadProgress: d?.download_progress ?? 0,
    downloadMessage: d?.download_message ?? '',
    downloadBytesDone: d?.download_bytes_done ?? 0,
    downloadBytesTotal: d?.download_bytes_total ?? 0,
    modelMetaStale: d?.model_meta_stale ?? false,
    expectedModelPath: d?.expected_model_path ?? null,
    ramPhase: d?.ram_phase ?? 'idle',
    ramProgress: d?.ram_progress ?? 0,
    ramMessage: d?.ram_message ?? '',
    ramEnabled: d?.ram_enabled ?? false,
    ramUsable: d?.ram_usable ?? false,
    embeddedReady: d?.embedded_ready ?? false,
  }
}

function mapChatVoiceReadiness(d: {
  ready?: boolean
  edge_tts?: boolean
  xtts_ready?: boolean
  silero_ready?: boolean
  engine?: string
  model?: string
  speaker?: string
  tempo?: number
  message?: string
  speaker_source?: string | null
}) {
  const sileroReady = d.silero_ready ?? d.xtts_ready ?? false
  return {
    ready: d.ready ?? false,
    edgeTts: d.edge_tts ?? false,
    xttsReady: sileroReady,
    sileroReady,
    engine: d.engine ?? 'silero',
    model: d.model ?? 'v5_ru',
    speaker: d.speaker ?? 'aidar',
    tempo: d.tempo ?? 1.0,
    message: d.message ?? '—',
    speakerSource: d.speaker_source ?? null,
  }
}

function mapSttStatus(d: {
  ready?: boolean
  loading?: boolean
  package_installed?: boolean
  gigaam_installed?: boolean
  gigaam_active?: boolean
  gigaam_v3?: boolean
  ffmpeg?: boolean
  engine?: string
  model?: string
  message?: string
  error?: string | null
}) {
  return {
    ready: d.ready ?? false,
    loading: d.loading ?? false,
    packageInstalled: d.package_installed ?? false,
    gigaamInstalled: d.gigaam_installed ?? false,
    gigaamActive: d.gigaam_active ?? false,
    gigaamV3: d.gigaam_v3 ?? false,
    ffmpeg: d.ffmpeg ?? false,
    engine: d.engine ?? 'gigaam',
    model: d.model ?? 'GigaAM-v3',
    message: d.message ?? '—',
    error: d.error ?? null,
  }
}

function mapXttsStatus(d: {
  status: string
  progress: number
  message: string
  error: string | null
  detail?: string | null
  importable: boolean
  python_version?: string
  python_ok_for_xtts?: boolean
  embedded_in_jarvis?: boolean
  tts_data_dir?: string
  model_weights_present?: boolean
  model_path_hint?: string | null
  koschey_bundled?: boolean
  koschey_path?: string | null
  model?: string
  engine?: string
  selected_speaker?: string
  cache_dir?: string
}) {
  return {
    status: d.status,
    progress: d.progress,
    message: d.message,
    error: d.error,
    detail: d.detail ?? null,
    importable: d.importable,
    pythonVersion: d.python_version,
    pythonOkForXtts: d.python_ok_for_xtts ?? true,
    embeddedInJarvis: d.embedded_in_jarvis ?? true,
    ttsDataDir: d.cache_dir ?? d.tts_data_dir ?? 'backend/data/silero',
    modelWeightsPresent: d.model_weights_present ?? d.importable ?? false,
    modelPathHint: d.model_path_hint ?? d.model ?? 'v5_ru',
    koscheyBundled: d.koschey_bundled ?? false,
    koscheyPath: d.koschey_path ?? null,
    model: d.model ?? 'v5_ru',
    engine: d.engine ?? 'silero',
    selectedSpeaker: d.selected_speaker ?? 'aidar',
  }
}

export type SileroVoice = {
  id: string
  label: string
  description: string
}

export type SileroStressEntry = {
  plain: string
  marked: string
}

export async function fetchSileroStressLexicon(): Promise<{
  entries: SileroStressEntry[]
  stress_flags: Record<string, boolean>
  hint: string
}> {
  return json('/api/voice/stress-lexicon')
}

export async function saveSileroStressLexicon(lines: string): Promise<{
  entries: SileroStressEntry[]
}> {
  return json('/api/voice/stress-lexicon', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lines }),
  })
}

export async function deleteSileroStressEntry(plain: string): Promise<{
  entries: SileroStressEntry[]
}> {
  return json('/api/voice/stress-lexicon', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plain }),
  })
}

export async function fetchSileroSpeakers(): Promise<{
  model: string
  language: string
  sample_rate: number
  selected: string
  tempo: number
  tempo_min: number
  tempo_max: number
  tempo_default: number
  voices: SileroVoice[]
}> {
  return json('/api/voice/speakers')
}

export async function saveSileroVoiceSettings(speaker: string, tempo: number) {
  return json<{
    model: string
    selected: string
    tempo: number
    tempo_min: number
    tempo_max: number
    voices: SileroVoice[]
  }>('/api/voice/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speaker, tempo }),
  })
}

/** @deprecated use saveSileroVoiceSettings */
export async function saveSileroSpeaker(speaker: string) {
  return saveSileroVoiceSettings(speaker, 1.0)
}

export async function previewSileroSpeaker(speaker: string, tempo?: number): Promise<string> {
  const res = await fetch(apiUrl('/api/voice/preview-speaker'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speaker, tempo }),
  })
  if (!res.ok) throw new Error(await res.text())
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

export async function startSileroInstall() {
  return downloadJarvisVoice()
}

export async function fetchSileroStatus() {
  return fetchXttsStatus()
}

export async function downloadJarvisVoice() {
  return json<{
    status: string
    progress: number
    message: string
    already_installed?: boolean
    skipped?: boolean
  }>('/api/voice/download-jarvis', { method: 'POST' })
}

export async function fetchXttsStatus() {
  const d = await json<Parameters<typeof mapXttsStatus>[0]>(
    '/api/voice/download-status',
    undefined,
    5000,
  )
  return mapXttsStatus(d)
}

export async function uploadBaseVoice(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(apiUrl('/api/voice/base/upload'), { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export type UploadedFileResult = {
  name: string
  indexed?: boolean
  stored?: string
  type?: string
  transaction_count?: number
  summary_markdown?: string
  error?: string
}

export async function uploadFiles(files: FileList, mode?: AgentMode) {
  const form = new FormData()
  Array.from(files).forEach((f) => form.append('files', f))
  const q = mode ? `?mode=${mode}` : ''
  const res = await fetch(apiUrl(`/api/files/upload${q}`), { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<{ files: UploadedFileResult[]; mode: string }>
}

export async function fetchVoiceSlots(): Promise<VoiceSlot[]> {
  const d = await json<{
    slots: Array<{
      slot: number
      status: VoiceSlot['status']
      message: string
      duration_sec: number | null
      filename: string | null
    }>
  }>('/api/voice/slots')
  return d.slots.map((s) => ({
    slot: s.slot,
    status: s.status,
    message: s.message,
    durationSec: s.duration_sec,
    filename: s.filename,
  }))
}

export async function uploadVoiceSlot(slot: number, file: Blob, filename: string) {
  const form = new FormData()
  form.append('file', file, filename)
  const res = await fetch(apiUrl(`/api/voice/slots/${slot}/upload`), {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(await res.text())
  const d = (await res.json()) as {
    slot: number
    status: VoiceSlot['status']
    message: string
    duration_sec: number | null
    filename: string | null
  }
  return {
    slot: d.slot,
    status: d.status,
    message: d.message,
    durationSec: d.duration_sec,
    filename: d.filename,
  } as VoiceSlot
}

export async function toggleTelegram(enabled: boolean) {
  return json('/api/telegram/toggle', {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
}

function mapTelegramConfig(d: {
  bot_token: string
  bot_token_configured: boolean
  bot_username?: string | null
  blocklist_ids: string[]
  telegram_proxy?: string
  bot_logic_configured?: boolean
  bot_logic_valid?: boolean
  bot_logic_error?: string | null
  bot_logic_name?: string | null
  ready: boolean
  save_ok?: boolean
  message?: string
}): TelegramConfig & { save_ok?: boolean; message?: string } {
  return {
    botToken: d.bot_token ?? '',
    botTokenConfigured: d.bot_token_configured,
    botUsername: d.bot_username ?? null,
    blocklistIds: d.blocklist_ids ?? [],
    telegramProxy: d.telegram_proxy ?? '',
    botLogicConfigured: d.bot_logic_configured,
    botLogicValid: d.bot_logic_valid,
    botLogicError: d.bot_logic_error ?? null,
    botLogicName: d.bot_logic_name,
    ready: d.ready,
    save_ok: d.save_ok,
    message: d.message,
  }
}

export async function fetchTelegramConfig(): Promise<TelegramConfig> {
  const d = await json<Parameters<typeof mapTelegramConfig>[0]>('/api/telegram/config')
  return mapTelegramConfig(d)
}

export async function saveTelegramConfig(payload: {
  botToken?: string
  blocklistIds?: string[]
  telegramProxy?: string
}): Promise<TelegramConfig> {
  const d = await json<Parameters<typeof mapTelegramConfig>[0]>(
    '/api/telegram/config',
    {
      method: 'PUT',
      body: JSON.stringify({
        bot_token: payload.botToken ?? '',
        blocklist_ids: payload.blocklistIds ?? [],
        telegram_proxy: payload.telegramProxy ?? '',
      }),
    },
    10_000,
  )
  return mapTelegramConfig(d)
}

export async function fetchTelegramBotLogic(): Promise<{
  logic: Record<string, unknown>
  botLogicConfigured: boolean
  botLogicName?: string | null
}> {
  const d = await json<{
    logic: Record<string, unknown>
    bot_logic_configured: boolean
    bot_logic_name?: string | null
  }>('/api/telegram/bot-logic')
  return {
    logic: d.logic,
    botLogicConfigured: d.bot_logic_configured,
    botLogicName: d.bot_logic_name,
  }
}

export async function saveTelegramBotLogic(
  logic: Record<string, unknown>,
): Promise<{ save_ok?: boolean; message?: string }> {
  return json('/api/telegram/bot-logic', {
    method: 'PUT',
    body: JSON.stringify(logic),
  })
}

export async function fetchTelegramBotLogicExample(): Promise<Record<string, unknown>> {
  return json('/api/telegram/bot-logic/example')
}

export async function fetchHfStatus(): Promise<{
  tokenConfigured: boolean
  tokenMask: string
  skillsDir: string
  installedCount: number
  enabledCount: number
  totalMb: number
  maxDownloadGb: number
}> {
  const d = await json<{
    token_configured: boolean
    token_mask: string
    skills_dir: string
    installed_count: number
    enabled_count: number
    total_mb: number
    max_download_gb: number
  }>('/api/hf/status')
  return {
    tokenConfigured: d.token_configured,
    tokenMask: d.token_mask,
    skillsDir: d.skills_dir,
    installedCount: d.installed_count,
    enabledCount: d.enabled_count,
    totalMb: d.total_mb,
    maxDownloadGb: d.max_download_gb,
  }
}

export async function searchHfHub(
  query: string,
  repoType: 'model' | 'dataset' | 'space' = 'model',
): Promise<{
  items: Array<{
    repo_id: string
    downloads?: number | null
    likes?: number | null
    jarvis_download_bytes?: number
    jarvis_download_files?: number
    repo_total_bytes?: number
    main_file_bytes?: number
    main_file_name?: string | null
  }>
  searchMode?: 'exact' | 'multi_term' | 'empty'
  terms?: string[]
}> {
  const d = await json<{
    items: Array<{
      repo_id: string
      downloads?: number | null
      likes?: number | null
      jarvis_download_bytes?: number
      jarvis_download_files?: number
      repo_total_bytes?: number
      main_file_bytes?: number
      main_file_name?: string | null
    }>
    search_mode?: 'exact' | 'multi_term' | 'empty'
    terms?: string[]
  }>('/api/hf/search', {
    method: 'POST',
    body: JSON.stringify({ query, repo_type: repoType, limit: 12 }),
  })
  return {
    items: d.items,
    searchMode: d.search_mode,
    terms: d.terms,
  }
}

export async function fetchHfInstalled(): Promise<{
  skills: Array<Record<string, unknown>>
  installedCount: number
  totalMb: number
}> {
  const d = await json<{
    skills: Array<Record<string, unknown>>
    installed_count: number
    total_mb: number
  }>('/api/hf/installed')
  return {
    skills: d.skills,
    installedCount: d.installed_count,
    totalMb: d.total_mb,
  }
}

export async function downloadHfSkill(payload: {
  repoId: string
  repoType?: string
  revision?: string
  filenames?: string[]
}): Promise<Record<string, unknown>> {
  return json('/api/hf/download', {
    method: 'POST',
    body: JSON.stringify({
      repo_id: payload.repoId,
      repo_type: payload.repoType ?? 'model',
      revision: payload.revision ?? 'main',
      filenames: payload.filenames ?? [],
    }),
  }, 600_000)
}

export async function setHfSkillEnabled(skillId: string, enabled: boolean) {
  return json('/api/hf/enable', {
    method: 'POST',
    body: JSON.stringify({ skill_id: skillId, enabled }),
  })
}

export async function deleteHfSkill(skillId: string) {
  return json(`/api/hf/installed/${encodeURIComponent(skillId)}`, { method: 'DELETE' })
}

function mapOpenConnectVpnPreset(d: {
  id: string
  label: string
  server: string
  port: number
  username: string
  protocol: string
  hint: string
  has_cert_pin?: boolean
}): import('@/types').OpenConnectVpnPreset {
  return {
    id: d.id,
    label: d.label,
    server: d.server,
    port: d.port,
    username: d.username,
    protocol: d.protocol,
    hint: d.hint,
    hasCertPin: d.has_cert_pin ?? false,
  }
}

function mapOpenConnectVpnConfig(d: {
  server: string
  port: number
  username: string
  password_configured: boolean
  use_jarvis_preset: boolean
  openconnect_path: string
  openconnect_found: boolean
  openconnect_exe: string
  server_cert_pin_configured: boolean
  preset: Parameters<typeof mapOpenConnectVpnPreset>[0]
  ready: boolean
}): import('@/types').OpenConnectVpnConfig {
  return {
    server: d.server ?? '',
    port: d.port ?? 443,
    username: d.username ?? '',
    passwordConfigured: d.password_configured,
    useJarvisPreset: d.use_jarvis_preset,
    openconnectPath: d.openconnect_path ?? '',
    openconnectFound: d.openconnect_found,
    openconnectExe: d.openconnect_exe ?? '',
    serverCertPinConfigured: d.server_cert_pin_configured,
    preset: mapOpenConnectVpnPreset(d.preset),
    ready: d.ready,
  }
}

function mapOpenConnectVpnStatus(d: {
  status: string
  status_label: string
  message: string
  error: string | null
  server: string
  managed: boolean
  external_gui: boolean
  system_vpn_active?: boolean
  openconnect_found: boolean
  ready: boolean
  use_jarvis_preset: boolean
  preset: Parameters<typeof mapOpenConnectVpnPreset>[0]
}): import('@/types').OpenConnectVpnState {
  return {
    status: d.status as import('@/types').OpenConnectVpnState['status'],
    statusLabel: d.status_label,
    message: d.message ?? '',
    error: d.error,
    server: d.server ?? '',
    managed: d.managed,
    externalGui: d.external_gui,
    systemVpnActive: d.system_vpn_active ?? d.external_gui,
    openconnectFound: d.openconnect_found,
    ready: d.ready,
    useJarvisPreset: d.use_jarvis_preset,
    preset: mapOpenConnectVpnPreset(d.preset),
  }
}

export async function fetchOpenConnectVpnStatus(): Promise<
  import('@/types').OpenConnectVpnState
> {
  const d = await json<Parameters<typeof mapOpenConnectVpnStatus>[0]>('/api/vpn/openconnect/status')
  return mapOpenConnectVpnStatus(d)
}

export async function fetchOpenConnectVpnConfig(): Promise<
  import('@/types').OpenConnectVpnConfig
> {
  const d = await json<Parameters<typeof mapOpenConnectVpnConfig>[0]>('/api/vpn/openconnect/config')
  return mapOpenConnectVpnConfig(d)
}

export async function saveOpenConnectVpnConfig(payload: {
  server?: string
  port?: number
  username?: string
  password?: string
  useJarvisPreset?: boolean
  openconnectPath?: string
  serverCertPin?: string
}): Promise<import('@/types').OpenConnectVpnConfig & { saveOk?: boolean; message?: string }> {
  const d = await json<
    Parameters<typeof mapOpenConnectVpnConfig>[0] & { save_ok?: boolean; message?: string }
  >('/api/vpn/openconnect/config', {
    method: 'PUT',
    body: JSON.stringify({
      server: payload.server ?? '',
      port: payload.port ?? 443,
      username: payload.username ?? '',
      password: payload.password ?? '',
      use_jarvis_preset: payload.useJarvisPreset ?? false,
      openconnect_path: payload.openconnectPath ?? '',
      server_cert_pin: payload.serverCertPin ?? '',
    }),
  })
  return {
    ...mapOpenConnectVpnConfig(d),
    saveOk: d.save_ok,
    message: d.message,
  }
}

export async function connectOpenConnectVpn(): Promise<import('@/types').OpenConnectVpnState> {
  const d = await json<Parameters<typeof mapOpenConnectVpnStatus>[0]>(
    '/api/vpn/openconnect/connect',
    { method: 'POST' },
    120_000,
  )
  return mapOpenConnectVpnStatus(d)
}

export async function disconnectOpenConnectVpn(): Promise<import('@/types').OpenConnectVpnState> {
  const d = await json<Parameters<typeof mapOpenConnectVpnStatus>[0]>(
    '/api/vpn/openconnect/disconnect',
    { method: 'POST' },
    30_000,
  )
  return mapOpenConnectVpnStatus(d)
}

export async function fetchOpenConnectVpnLog(limit = 60): Promise<string[]> {
  const d = await json<{ lines: string[] }>(`/api/vpn/openconnect/log?limit=${limit}`)
  return d.lines ?? []
}

function mapAvitoConfig(d: {
  client_id: string
  client_id_configured: boolean
  client_secret_configured: boolean
  user_id: string
  sync_enabled: boolean
  last_sync_date: string | null
  ready: boolean
}): AvitoConfig {
  return {
    clientId: d.client_id ?? '',
    clientIdConfigured: d.client_id_configured,
    clientSecretConfigured: d.client_secret_configured,
    userId: d.user_id ?? '',
    syncEnabled: d.sync_enabled,
    lastSyncDate: d.last_sync_date,
    ready: d.ready,
  }
}

export async function fetchAvitoConfig(): Promise<AvitoConfig> {
  const d = await json<Parameters<typeof mapAvitoConfig>[0]>('/api/avito/config')
  return mapAvitoConfig(d)
}

export async function saveAvitoConfig(payload: {
  clientId?: string
  clientSecret?: string
  userId?: string
}): Promise<AvitoConfig & { save_ok?: boolean; message?: string }> {
  const d = await json<Parameters<typeof mapAvitoConfig>[0] & { save_ok?: boolean; message?: string }>(
    '/api/avito/config',
    {
      method: 'PUT',
      body: JSON.stringify({
        client_id: payload.clientId ?? '',
        client_secret: payload.clientSecret ?? '',
        user_id: payload.userId ?? '',
      }),
    },
  )
  return { ...mapAvitoConfig(d), save_ok: d.save_ok, message: d.message }
}

export async function toggleAvito(enabled: boolean) {
  return json('/api/avito/toggle', {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
}

export async function syncAvitoNow() {
  return json<{ ok: boolean; date?: string; items?: number; error?: string }>(
    '/api/avito/sync',
    { method: 'POST' },
  )
}

export async function syncAvitoChats(maxChats = 500, days = 30) {
  return json<{
    ok: boolean
    chats_saved?: number
    messages_saved?: number
    account_name?: string
    user_id?: string
    error?: string
  }>(
    `/api/avito/sync/chats?max_chats=${maxChats}&days=${days}`,
    { method: 'POST' },
    120000,
  )
}

export async function analyzeAvitoChats(days = 30) {
  return json<{
    ok: boolean
    report?: string
    data?: { analyzed?: number; counts?: Record<string, number> }
  }>(`/api/avito/analyze?days=${days}`, { method: 'POST' }, 120000)
}

export async function runAvitoChatPipeline(days = 30) {
  return json<{ ok: boolean; report?: string }>(
    `/api/avito/pipeline?days=${days}`,
    { method: 'POST' },
    180000,
  )
}

export async function purgeAvitoChat(chatId: string) {
  return json<{ ok: boolean; messages_deleted?: number; chat_deleted?: number }>(
    `/api/avito/chats/${encodeURIComponent(chatId)}`,
    { method: 'DELETE' },
  )
}

export async function probeAvitoApi() {
  return json<{
    credentials: boolean
    profile: { ok: boolean; error?: string }
    messenger_chats: { ok: boolean; error?: string; api_path?: string }
    stats: { ok: boolean; error?: string; http?: number }
    archive: { chats_in_db: number; messages_in_db: number; last_chats_sync_at?: string }
  }>('/api/avito/probe')
}

export async function fetchAvitoMetrics(dateFrom?: string, dateTo?: string) {
  const q = new URLSearchParams()
  if (dateFrom) q.set('date_from', dateFrom)
  if (dateTo) q.set('date_to', dateTo)
  const suffix = q.toString() ? `?${q}` : ''
  return json<{
    date_from: string
    date_to: string
    totals: { views: number; favorites: number; contacts: number; spend: number }
    series: Array<{ date: string; views: number; favorites: number; contacts: number; spend: number }>
    rows: Array<{
      date: string
      item_id: string
      title: string
      views: number
      favorites: number
      contacts: number
      spend: number
    }>
    items_count: number
  }>(`/api/avito/metrics${suffix}`)
}

function mapTelephonyConfig(d: {
  enabled: boolean
  provider: string
  public_base_url: string
  webhook_secret: string
  webhook_secret_configured: boolean
  greeting_text: string
  mango_api_key: string
  mango_api_key_configured: boolean
  mango_api_salt: string
  mango_api_salt_configured: boolean
  mango_line_number: string
  mango_extension: string
  zadarma_api_key: string
  zadarma_api_key_configured: boolean
  zadarma_api_secret: string
  zadarma_api_secret_configured: boolean
  zadarma_ivr_file_id: string
  use_llm_on_call: boolean
  webhook_url: string
  scenario_url: string
  greeting_media_url: string
  status?: string
  status_label?: string
  last_event?: string
  last_caller?: string | null
  greeting_ready?: boolean
}): TelephonyConfig {
  return {
    enabled: d.enabled,
    provider: d.provider,
    publicBaseUrl: d.public_base_url ?? '',
    webhookSecret: d.webhook_secret ?? '',
    webhookSecretConfigured: d.webhook_secret_configured ?? false,
    greetingText: d.greeting_text ?? '',
    mangoApiKey: d.mango_api_key ?? '',
    mangoApiKeyConfigured: d.mango_api_key_configured ?? false,
    mangoApiSalt: d.mango_api_salt ?? '',
    mangoApiSaltConfigured: d.mango_api_salt_configured ?? false,
    mangoLineNumber: d.mango_line_number ?? '',
    mangoExtension: d.mango_extension ?? '',
    zadarmaApiKey: d.zadarma_api_key ?? '',
    zadarmaApiKeyConfigured: d.zadarma_api_key_configured ?? false,
    zadarmaApiSecret: d.zadarma_api_secret ?? '',
    zadarmaApiSecretConfigured: d.zadarma_api_secret_configured ?? false,
    zadarmaIvrFileId: d.zadarma_ivr_file_id ?? '',
    useLlmOnCall: d.use_llm_on_call ?? true,
    webhookUrl: d.webhook_url ?? '',
    scenarioUrl: d.scenario_url ?? '',
    greetingMediaUrl: d.greeting_media_url ?? '',
    status: d.status,
    statusLabel: d.status_label,
    lastEvent: d.last_event,
    lastCaller: d.last_caller,
    greetingReady: d.greeting_ready,
  }
}

export async function fetchTelephonyConfig(): Promise<TelephonyConfig> {
  const d = await json<Parameters<typeof mapTelephonyConfig>[0]>('/api/telephony/status')
  return mapTelephonyConfig(d)
}

export async function saveTelephonyConfig(payload: {
  enabled?: boolean
  provider?: string
  publicBaseUrl?: string
  webhookSecret?: string
  greetingText?: string
  mangoApiKey?: string
  mangoApiSalt?: string
  mangoLineNumber?: string
  mangoExtension?: string
  zadarmaApiKey?: string
  zadarmaApiSecret?: string
  zadarmaIvrFileId?: string
  useLlmOnCall?: boolean
}): Promise<TelephonyConfig> {
  const d = await json<Parameters<typeof mapTelephonyConfig>[0]>('/api/telephony/config', {
    method: 'PUT',
    body: JSON.stringify({
      enabled: payload.enabled,
      provider: payload.provider,
      public_base_url: payload.publicBaseUrl,
      webhook_secret: payload.webhookSecret,
      greeting_text: payload.greetingText,
      mango_api_key: payload.mangoApiKey,
      mango_api_salt: payload.mangoApiSalt,
      mango_line_number: payload.mangoLineNumber,
      mango_extension: payload.mangoExtension,
      zadarma_api_key: payload.zadarmaApiKey,
      zadarma_api_secret: payload.zadarmaApiSecret,
      zadarma_ivr_file_id: payload.zadarmaIvrFileId,
      use_llm_on_call: payload.useLlmOnCall,
    }),
  })
  return mapTelephonyConfig(d)
}

export async function synthesizeTelephonyGreeting(): Promise<{ ok: boolean }> {
  return json('/api/telephony/synthesize', { method: 'POST' })
}

export async function telephonyTestWebhook(): Promise<{
  ok: boolean
  audio_url?: string
  http_status?: number
}> {
  return json('/api/telephony/test-webhook', { method: 'POST' })
}

export async function telephonyTestCall(
  toNumber: string,
): Promise<{ ok: boolean; message?: string; error?: string }> {
  return json('/api/telephony/test-call', {
    method: 'POST',
    body: JSON.stringify({ to_number: toNumber }),
  })
}

export type StreamEvent =
  | { type: 'user'; message: Message }
  | { type: 'status'; status: AgentState['status'] }
  | {
      type: 'progress'
      phase: string
      message: string
      current: number
      total: number
      percent: number | null
    }
  | { type: 'log'; tool: string; message: string }
  | { type: 'think'; line: string }
  | { type: 'think_end' }
  | { type: 'chunk'; content: string }
  | {
      type: 'done'
      message: Message
      meta?: {
        refresh_settings?: boolean
        refresh_voice?: boolean
        chat_speech_enabled?: boolean
        speech_text?: string
      }
      speak?: boolean
    }
  | { type: 'tts'; audioUrl: string; message?: string }
  | { type: 'speak'; text: string }
  | { type: 'ui'; commands: import('@/lib/uiBridge').UiCommand[] }
  | { type: 'insult'; insult: JarvisInsultState; kind: string; counted: boolean }
  | { type: 'mood'; mood: JarvisMoodState }
  | { type: 'error'; message: string }

export async function streamMessage(
  chatId: string,
  content: string,
  mode: AgentMode,
  chatSpeechEnabled: boolean,
  onEvent: (e: StreamEvent) => void,
  insultRequestId?: string,
  options?: { signal?: AbortSignal; chatSurfaceMode?: ChatSurfaceMode },
) {
  let res: Response
  try {
    res = await fetch(apiUrl(`/api/chats/${chatId}/messages`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        mode,
        chat_speech_enabled: chatSpeechEnabled,
        insult_request_id: insultRequestId ?? null,
        chat_surface_mode: options?.chatSurfaceMode ?? 'text',
      }),
      signal: options?.signal,
    })
  } catch (e) {
    throw new Error(formatJarvisNetworkError(e))
  }
  if (!res.ok) throw new Error(await res.text())
  if (!res.body) throw new Error('No stream')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
  while (true) {
    if (options?.signal?.aborted) {
      await reader.cancel().catch(() => {})
      return
    }
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6).trim()
      if (payload === '[DONE]') return
      try {
        const raw = JSON.parse(payload) as Record<string, unknown>
        if (raw.type === 'user' && raw.message) {
          const m = raw.message as { id: string; role: 'user'; content: string; created_at: string }
          onEvent({
            type: 'user',
            message: {
              id: m.id,
              role: 'user',
              content: m.content,
              createdAt: m.created_at,
            },
          })
        } else if (raw.type === 'done' && raw.message) {
          const m = raw.message as {
            id: string
            role: 'assistant'
            content: string
            created_at: string
          }
          onEvent({
            type: 'done',
            message: {
              id: m.id,
              role: 'assistant',
              content: m.content,
              createdAt: m.created_at,
            },
            meta: raw.meta as {
              refresh_settings?: boolean
              refresh_voice?: boolean
              chat_speech_enabled?: boolean
              speech_text?: string
            },
            speak: raw.speak === true,
          })
        } else if (raw.type === 'chunk') {
          onEvent({ type: 'chunk', content: String(raw.content) })
        } else if (raw.type === 'status') {
          onEvent({ type: 'status', status: raw.status as AgentState['status'] })
        } else if (raw.type === 'progress') {
          onEvent({
            type: 'progress',
            phase: String(raw.phase ?? ''),
            message: String(raw.message ?? ''),
            current: Number(raw.current) || 0,
            total: Number(raw.total) || 0,
            percent:
              raw.percent != null && raw.percent !== ''
                ? Number(raw.percent)
                : null,
          })
        } else if (raw.type === 'log') {
          onEvent({ type: 'log', tool: String(raw.tool), message: String(raw.message) })
        } else if (raw.type === 'think' && raw.line) {
          onEvent({ type: 'think', line: String(raw.line) })
        } else if (raw.type === 'think_end') {
          onEvent({ type: 'think_end' })
        } else if (raw.type === 'tts' && raw.audio_url) {
          onEvent({
            type: 'tts',
            audioUrl: String(raw.audio_url),
            message: raw.message != null ? String(raw.message) : undefined,
          })
        } else if (raw.type === 'speak' && raw.text) {
          onEvent({ type: 'speak', text: String(raw.text) })
        } else if (raw.type === 'ui' && Array.isArray(raw.commands)) {
          onEvent({
            type: 'ui',
            commands: raw.commands as import('@/lib/uiBridge').UiCommand[],
          })
        } else if (raw.type === 'insult') {
          const row = raw as {
            kind?: string
            counted?: boolean
            insult?: Parameters<typeof mapInsultFromApi>[0]
            mood?: Parameters<typeof mapMoodFromApi>[0]
          }
          const insultPayload = row.insult ?? (raw as Parameters<typeof mapInsultFromApi>[0])
          onEvent({
            type: 'insult',
            insult: mapInsultFromApi(insultPayload),
            kind: String(row.kind ?? ''),
            counted: row.counted === true,
          })
          if (row.mood) {
            onEvent({ type: 'mood', mood: mapMoodFromApi(row.mood) })
          }
        } else if (raw.type === 'mood' && raw.mood) {
          onEvent({
            type: 'mood',
            mood: mapMoodFromApi(raw.mood as Parameters<typeof mapMoodFromApi>[0]),
          })
        } else if (raw.type === 'error') {
          onEvent({ type: 'error', message: String(raw.message) })
        }
      } catch {
        /* skip */
      }
    }
  }
  } catch (e) {
    throw new Error(formatJarvisNetworkError(e))
  }
}

export type MenuSearchItem = {
  id: string
  block_id: string | null
  section_dom_id: string
  label: string
  path: string[]
  is_block?: boolean
  weight?: number
}

export type MenuSearchResponse = {
  query: string
  items: MenuSearchItem[]
  cells_matched: number
  blocks_matched: string[]
}

export async function searchMenu(
  query: string,
  limit = 24,
  init?: RequestInit,
): Promise<MenuSearchResponse> {
  const params = new URLSearchParams()
  if (query.trim()) params.set('q', query.trim())
  params.set('limit', String(limit))
  const res = await fetch(apiUrl(`/api/menu/search?${params}`), init)
  if (!res.ok) throw new Error('menu search failed')
  const data = (await res.json()) as MenuSearchResponse
  return {
    query: data.query ?? query,
    items: data.items ?? [],
    cells_matched: data.cells_matched ?? 0,
    blocks_matched: data.blocks_matched ?? [],
  }
}

export async function rebuildMenuIndex(): Promise<{ cells_upserted: number; cells_total: number }> {
  const res = await fetch(apiUrl('/api/menu/rebuild'), { method: 'POST' })
  if (!res.ok) throw new Error('menu rebuild failed')
  return res.json()
}

export type MailSlotMeta = {
  slot: number
  provider: string
  preset: string
  label: string
  hint: string
}

export type MailAccountConfig = {
  id?: string
  slot?: number
  provider?: string
  label: string
  email: string
  password: string
  imap_host: string
  imap_port: number
  imap_ssl: boolean
  enabled: boolean
  preset: string
}

export async function fetchMailConfig(): Promise<{
  max_accounts: number
  presets: string[]
  slots: MailSlotMeta[]
  accounts: Array<Omit<MailAccountConfig, 'password'> & { password_configured: boolean }>
}> {
  return json('/api/mail/config')
}

export async function saveMailConfig(accounts: MailAccountConfig[]) {
  return json('/api/mail/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ accounts }),
  })
}

export async function testMailAccount(accountId: string) {
  return json<{ ok: boolean; message: string }>(`/api/mail/test/${encodeURIComponent(accountId)}`, {
    method: 'POST',
  })
}
