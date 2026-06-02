export type AgentMode = 'standard' | 'accountant' | 'marketer' | 'developer'
export type AgentStatus =
  | 'IDLE'
  | 'Listening...'
  | 'Thinking...'
  | 'Searching Web...'
  | 'Generating image...'
export type BackendStatus = 'connected' | 'disconnected' | 'connecting'
export type TgTwinStatus = 'off' | 'waiting' | 'active' | 'need_token' | 'error'
export type AvitoStatus = 'off' | 'waiting' | 'active' | 'need_creds' | 'error'
export type VoiceSlotStatus = 'empty' | 'checking' | 'ready' | 'error'
export type MessageRole = 'user' | 'assistant' | 'system'
export type NotifyImportance = 'important' | 'routine'

export const MODE_LABELS: Record<AgentMode, string> = {
  standard: 'Стандартный чат',
  accountant: 'Бухгалтер + Юрист',
  marketer: 'Маркетолог+Дизайнер',
  developer: 'Разработчик',
}

export interface ToolLogEntry {
  id: string
  timestamp: string
  tool: string
  message: string
}

/** Прогресс длительной операции в чате (SSE type: progress). */
export interface OperationProgressState {
  phase: string
  message: string
  current: number
  total: number
  percent: number | null
  logs: string[]
}

export interface Message {
  id: string
  role: MessageRole
  content: string
  createdAt: string
  /** important — чат, LLM, озвучка; routine — только индикаторы */
  notifyLevel?: NotifyImportance
}

export interface Chat {
  id: string
  title: string
  updatedAt: string
  messages: Message[]
}

export type MemoryStoreId =
  | 'conscious'
  | 'unconscious'
  | 'mode-accountant'
  | 'mode-marketer'
  | 'mode-developer'

export interface MemoryFile {
  id: string
  name: string
  sizeBytes: number
  store: MemoryStoreId
  protected?: boolean
}

export interface MemoryFileContent extends MemoryFile {
  content: string
}

export interface MemoryStores {
  conscious: MemoryFile[]
  unconscious: MemoryFile[]
  modeAccountant: MemoryFile[]
  modeMarketer: MemoryFile[]
  modeDeveloper: MemoryFile[]
}

export interface TelegramConfig {
  botToken: string
  botTokenConfigured: boolean
  botUsername?: string | null
  blocklistIds: string[]
  telegramProxy: string
  botLogicConfigured?: boolean
  botLogicValid?: boolean
  botLogicError?: string | null
  botLogicName?: string | null
  ready: boolean
}

export interface AvitoConfig {
  clientId: string
  clientIdConfigured: boolean
  clientSecretConfigured: boolean
  userId: string
  syncEnabled: boolean
  lastSyncDate: string | null
  ready: boolean
}

export interface AvitoState {
  enabled: boolean
  status: AvitoStatus
  statusLabel: string
  lastEvent: string
  error: string | null
  lastSyncDate: string | null
  itemsSynced: number
  clientIdConfigured: boolean
  clientSecretConfigured: boolean
  userId: string
  ready: boolean
  chatsInDb?: number
  messagesInDb?: number
  lastChatsSyncAt?: string | null
}

export interface TelegramState {
  enabled: boolean
  status: TgTwinStatus
  statusLabel: string
  lastEvent: string
  blocklistIds: string[]
  error: string | null
  botTokenConfigured: boolean
  botUsername: string | null
  botLogicConfigured?: boolean
  botLogicValid?: boolean
  botLogicError?: string | null
  botLogicName?: string | null
  messagesHandled?: number
  pollingActive?: boolean
  ready: boolean
}

export interface TelephonyConfig {
  enabled: boolean
  provider: string
  publicBaseUrl: string
  webhookSecret: string
  webhookSecretConfigured: boolean
  greetingText: string
  mangoApiKey: string
  mangoApiKeyConfigured: boolean
  mangoApiSalt: string
  mangoApiSaltConfigured: boolean
  mangoLineNumber: string
  mangoExtension: string
  zadarmaApiKey: string
  zadarmaApiKeyConfigured: boolean
  zadarmaApiSecret: string
  zadarmaApiSecretConfigured: boolean
  zadarmaIvrFileId: string
  useLlmOnCall: boolean
  webhookUrl: string
  scenarioUrl: string
  greetingMediaUrl: string
  status?: string
  statusLabel?: string
  lastEvent?: string
  lastCaller?: string | null
  greetingReady?: boolean
}

export interface VoiceBaseInfo {
  exists: boolean
  path: string | null
  filename: string | null
  source: string
  activeStudioSlot: number | null
  sizeBytes: number
  version: number
}

export interface XttsStatus {
  status: string
  progress: number
  message: string
  error: string | null
  detail?: string | null
  importable: boolean
  pythonVersion?: string
  pythonOkForXtts?: boolean
  embeddedInJarvis?: boolean
  ttsDataDir?: string
  modelWeightsPresent?: boolean
  modelPathHint?: string | null
  koscheyBundled?: boolean
  koscheyPath?: string | null
}

export interface LocalQwenState {
  label: string
  status: string
  statusLabel: string
  message: string
  value: string
  ready: boolean
  filesPresent: boolean
  filesPath: string | null
  filesBytes: number
  ollamaReachable: boolean
  ollamaModelLoaded: boolean
  ollamaModelName: string | null
  ollamaExpectedModel: string
  ollamaError: string | null
  downloadPhase: string
  downloadProgress: number
  downloadMessage: string
  downloadBytesDone: number
  downloadBytesTotal: number
  /** Метаданные установки есть, но GGUF на диске отсутствует */
  modelMetaStale?: boolean
  expectedModelPath?: string | null
  ramPhase: string
  ramProgress: number
  ramMessage: string
  /** Пользователь включил загрузку GGUF в ОЗУ (кнопка в сайдбаре). */
  ramEnabled: boolean
  /** Модель реально готова к локальным ответам (RAM или Ollama при включённом тумблере). */
  ramUsable: boolean
  embeddedReady?: boolean
}

export interface TelephonyState {
  enabled: boolean
  status: string
  statusLabel: string
  lastEvent: string
  greetingReady: boolean
  webhookSecretConfigured: boolean
  mangoApiKeyConfigured: boolean
  publicBaseUrl: string
}

export interface MailAccountSlot {
  slot: number
  id: string | null
  label: string
  email: string
  enabled: boolean
  configured: boolean
  status: string
  statusLabel: string
  lastEvent: string
  error: string | null
}

export interface MailState {
  enabled: boolean
  ready: boolean
  status: string
  statusLabel: string
  lastEvent: string
  accounts: Array<{
    id: string
    label: string
    email: string
    enabled: boolean
    configured: boolean
    status: string
    statusLabel: string
    lastEvent: string
    error: string | null
  }>
  slots: MailAccountSlot[]
}

export interface JarvisProcessInfo {
  pid: number
  name: string
  role: string
  rssBytes: number
  rssMb: number
}

/** Снимок ОЗУ: процессы Jarvis относительно RAM ПК (см. backend jarvis_memory). */
export interface JarvisRamUsage {
  jarvisRssBytes: number
  jarvisRssMb: number
  totalRamMb: number
  jarvisPercentOfTotal: number
  systemUsedPercent: number
  systemUsedMb: number
  processCount: number
  launching: boolean
  servicesActive: boolean
  processes: JarvisProcessInfo[]
  qwenRamLoading: boolean
  loadTargetMb: number
  loadProgressPercent: number
  loadBaselineMb: number
}

/** Встроенный headless Chromium (Playwright) для fetch_url. */
export interface ChromiumBrowserState {
  playwrightInstalled: boolean
  browserInstalled: boolean
  ready: boolean
  statusLabel: string
  detail: string
  installPhase: string
  installProgress: number
  installMessage: string
  installInProgress: boolean
  installError: string | null
  /** Интернет Windows (не фаза установки Chromium). */
  systemInternetOk?: boolean | null
  systemInternetDetail?: string
}

export interface JarvisNetworkState {
  internetOk: boolean
  internetDetail: string
}

/** Google Chrome на Windows — оконный режим Jarvis. */
export interface GoogleChromeState {
  requiredOnWindows: boolean
  installed: boolean
  ready: boolean
  executablePath: string | null
  statusLabel: string
  detail: string
  installPhase: string
  installMessage: string
  installInProgress: boolean
  installError: string | null
}

/** Счётчик оскорблений Jarvis в текущем сеансе UI. */
export interface JarvisInsultState {
  sessionCount: number
  threshold: number
  offended: boolean
  offendedUntil: number | null
  angryUntil: number | null
  offendedRemainingSec: number
}

export type JarvisMoodTier =
  | 'critical'
  | 'chilly'
  | 'reserved'
  | 'neutral'
  | 'pleasant'
  | 'warm'
  | 'radiant'

/** Шкала настроения Jarvis (−50 … +50). */
export interface JarvisMoodState {
  score: number
  min: number
  max: number
  tier: JarvisMoodTier
  tierLabel: string
  canRestart: boolean
  isCritical: boolean
  isRadiant: boolean
}

export interface JarvisRouterState {
  lastIntent: string | null
  lastEngine: string | null
}

export interface AgentState {
  edition?: 'free' | 'pro'
  editionLabel?: string
  deepseekBundled?: boolean
  router?: JarvisRouterState
  status: AgentStatus
  insult?: JarvisInsultState
  mood?: JarvisMoodState
  sessionTokens: number
  model: string
  neuralReady?: boolean
  qwenReady?: boolean
  chatLlmReady?: boolean
  chatModeLabel?: string
  chatModeDetail?: string
  qwen: LocalQwenState
  ramUsage: JarvisRamUsage
  chromiumBrowser: ChromiumBrowserState
  googleChrome: GoogleChromeState
  net?: JarvisNetworkState
  backendStatus: BackendStatus
  mode: AgentMode
  voiceEnabled: boolean
  voiceListening: boolean
  chatSpeechEnabled: boolean
  deepseekConfigured: boolean
  deepseekActive?: boolean
  deepseekUsable?: boolean
  nanobananaConfigured: boolean
  ideogramConfigured?: boolean
  ideogramActive?: boolean
  ideogramUsable?: boolean
  mediaImageReady?: boolean
  mediaVideoReady?: boolean
  openaiConfigured: boolean
  perplexityConfigured: boolean
  perplexityUsable: boolean
  xaiConfigured: boolean
  voiceBase: VoiceBaseInfo
  xtts: XttsStatus
  memory: MemoryStores
  toolLogs: ToolLogEntry[]
  telegram: TelegramState
  avito: AvitoState
  mail: MailState
  telephony: TelephonyState
}

export interface VoiceSlot {
  slot: number
  status: VoiceSlotStatus
  message: string
  durationSec: number | null
  filename: string | null
}

export interface AppSettings {
  provider: string
  defaultModel: string
  openaiKey: string
  openaiModel: string
  anthropicKey: string
  deepseekKey: string
  perplexityKey: string
  perplexityModel: string
  xaiKey: string
  xaiModel: string
  deepseekConfigured?: boolean
  deepseekActive?: boolean
  deepseekUsable?: boolean
  openaiConfigured?: boolean
  openaiActive?: boolean
  openaiUsable?: boolean
  perplexityConfigured?: boolean
  perplexityActive?: boolean
  perplexityUsable?: boolean
  xaiConfigured?: boolean
  xaiActive?: boolean
  xaiUsable?: boolean
  nanobananaKey: string
  nanobananaConfigured?: boolean
  nanobananaActive?: boolean
  nanobananaUsable?: boolean
  ideogramKey: string
  ideogramConfigured?: boolean
  ideogramActive?: boolean
  ideogramUsable?: boolean
  mediaImageReady?: boolean
  mediaVideoReady?: boolean
  xttsActive?: boolean
}
