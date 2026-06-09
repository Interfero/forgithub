import { DownloadProgress } from '@/components/ui/DownloadProgress'
import {
  Activity,
  BarChart3,
  Brain,
  Cloud,
  Cpu,
  Image,
  Globe,
  Mail,
  Mic,
  Phone,
  Send,
  Sparkles,
  Volume2,
  Wifi,
  WifiOff,
  type ReactNode,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Hint } from '@/components/ui/hint'
import { cn } from '@/lib/utils'
import type {
  AgentMode,
  AgentState,
  AgentStatus,
  AvitoState,
  BackendStatus,
  ChromiumBrowserState,
  GoogleChromeState,
  MailAccountSlot,
  TelegramState,
} from '@/types'

export type BadgeVariant = 'success' | 'warning' | 'secondary' | 'muted' | 'default'

const CHIP_BOX =
  'flex h-[88px] w-[12.25rem] shrink-0 cursor-default flex-col justify-between rounded-md border border-border/50 bg-background/60 px-2 py-1.5'

const CHIP_BOX_COMPACT =
  'flex h-[44px] w-[6.125rem] shrink-0 cursor-default flex-col justify-between rounded-md border border-border/50 bg-background/60 px-1.5 py-1'

export interface StatusChipProps {
  label: string
  /** Коротко: зачем этот индикатор (видно без наведения). */
  purpose?: string
  hint: string
  value: string
  variant: BadgeVariant
  icon?: ReactNode
}

export function StatusChip({ label, purpose, hint, value, variant, icon }: StatusChipProps) {
  return (
    <Hint text={hint}>
      <div className={CHIP_BOX}>
        <div className="min-h-0 shrink-0">
          <p className="line-clamp-1 text-[13px] font-medium leading-snug text-muted-foreground">
            {label}
          </p>
          {purpose ? (
            <p className="line-clamp-1 text-[9px] leading-snug text-muted-foreground/75">
              {purpose}
            </p>
          ) : null}
        </div>
        <Badge variant={variant} className="h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal">
          {icon}
          <span className="truncate">{value}</span>
        </Badge>
      </div>
    </Hint>
  )
}

export function StatusLegend({
  className,
  embedded = false,
}: {
  className?: string
  /** Внутри общей рамки панели — без отдельной левой обводки. */
  embedded?: boolean
}) {
  const items: { color: string; label: string }[] = [
    { color: 'bg-emerald-500', label: 'Всё в порядке / подключено' },
    { color: 'bg-amber-500', label: 'Нужно действие (ключ, настройка)' },
    { color: 'bg-blue-500', label: 'В процессе (думает, синхронизация)' },
    { color: 'bg-muted-foreground/50', label: 'Выключено или не используется' },
    { color: 'bg-destructive/80', label: 'Ошибка (редко)' },
  ]
  return (
    <div
      className={cn(
        embedded
          ? 'h-full rounded-none border-0 border-r border-sky-400/45 bg-card/25 px-2.5 py-2'
          : 'rounded-md border-2 border-sky-400/75 bg-card/50 p-2.5 shadow-[0_0_14px_rgba(56,189,248,0.35)]',
        className,
      )}
    >
      <p
        className={cn(
          'mb-2 border-b border-sky-400/30 pb-1.5 text-[9px] font-semibold uppercase tracking-wide text-foreground/90',
          embedded ? 'px-0.5' : '',
        )}
      >
        Легенда
      </p>
      <table className="w-full min-w-[7.5rem] border-collapse text-[9px] leading-snug">
        <tbody>
          {items.map((it) => (
            <tr key={it.label} className="border-b border-border/25 last:border-0">
              <td className="w-5 py-1.5 pl-0.5 pr-2 align-middle">
                <span
                  className={cn('block h-2.5 w-2.5 shrink-0 rounded-full', it.color)}
                  aria-hidden
                />
              </td>
              <td className="py-1.5 pr-0.5 text-muted-foreground">{it.label}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function backendChip(status: BackendStatus): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  if (status === 'connected') {
    return {
      value: 'На связи',
      variant: 'success',
      hint: 'Локальный сервер Jarvis запущен и отвечает на запросы.',
      icon: <Wifi className="h-5 w-5" />,
    }
  }
  if (status === 'connecting') {
    return {
      value: 'Связь…',
      variant: 'warning',
      hint: 'Идёт проверка связи с сервером.',
      icon: <Wifi className="h-5 w-5 animate-pulse" />,
    }
  }
  return {
    value: 'Нет связи',
    variant: 'secondary',
    hint: 'Сервер не отвечает. Запустите start.bat или restart.bat.',
    icon: <WifiOff className="h-5 w-5" />,
  }
}

/** Облачный DeepSeek (не путать с локальной Qwen). */
export function deepseekCloudChip(agent: AgentState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Cloud className="h-5 w-5" />

  if (agent.backendStatus !== 'connected') {
    return {
      value: 'Нет связи',
      variant: 'secondary',
      hint: 'DeepSeek — после подключения к серверу Jarvis.',
      icon,
    }
  }
  const localChatReady =
    agent.qwenReady ||
    agent.qwen.ready ||
    agent.qwen.ollamaModelLoaded ||
    agent.qwen.ramUsable ||
    agent.qwen.embeddedReady

  if (!agent.deepseekConfigured && !agent.deepseekBundled) {
    if (localChatReady) {
      return {
        value: 'Не нужен',
        variant: 'muted',
        hint:
          'Облачный DeepSeek не настроен — обычный чат идёт через локальную Qwen (см. «Последний ответ» после сообщения). Ключ sk-… — только для сложных задач в облаке.',
        icon,
      }
    }
    return {
      value: 'Нужен ключ',
      variant: 'warning',
      hint: 'Нет локальной Qwen и нет ключа DeepSeek — добавьте sk-… в Настройках или install-qwen.bat + Ollama.',
      icon,
    }
  }
  if (agent.deepseekBundled && agent.deepseekUsable) {
    return {
      value: 'Встроен',
      variant: 'success',
      hint: 'DeepSeek настроен — облачные ответы доступны.',
      icon,
    }
  }
  if (agent.deepseekActive === false) {
    return {
      value: 'Выключен',
      variant: 'muted',
      hint: 'Сервис DeepSeek отключён тумблером в Настройках.',
      icon,
    }
  }
  if (agent.status === 'Thinking...') {
    return {
      value: 'Думает…',
      variant: 'default',
      hint: 'DeepSeek формирует ответ в облаке.',
      icon,
    }
  }
  if (agent.deepseekUsable === false) {
    return {
      value: 'Неактивен',
      variant: 'warning',
      hint: 'Ключ есть, но сервис DeepSeek не включён.',
      icon,
    }
  }
  return {
    value: 'Готов',
    variant: 'success',
    hint: `DeepSeek в облаке · ${agent.model || 'deepseek-chat'}.`,
    icon,
  }
}

/** @deprecated Используйте deepseekCloudChip в ядре; в API-блоке — тот же чип. */
export function neuralChip(agent: AgentState) {
  return deepseekCloudChip(agent)
}

export function agentChip(
  status: AgentStatus,
  backendStatus: AgentState['backendStatus'],
): {
  value: string
  variant: BadgeVariant
  hint: string
} {
  if (backendStatus !== 'connected') {
    return {
      value: '—',
      variant: 'secondary',
      hint: 'Состояние агента видно после подключения к серверу.',
    }
  }
  switch (status) {
    case 'Listening...':
      return {
        value: 'Слушает',
        variant: 'success',
        hint: 'Микрофон включён — скажите «Джарвис» и команду.',
      }
    case 'Thinking...':
      return { value: 'Думает', variant: 'default', hint: 'Агент обрабатывает сообщение.' }
    case 'Searching Web...':
      return { value: 'Поиск', variant: 'warning', hint: 'Агент ищет в интернете.' }
    case 'Generating image...':
      return {
        value: 'Картинка',
        variant: 'default',
        hint: 'Генерация изображения (медиа-роутер).',
      }
    case 'Generating video...':
      return {
        value: 'Видео',
        variant: 'default',
        hint: 'Генерация видео (медиа-роутер).',
      }
    default:
      return { value: 'Ждёт', variant: 'muted', hint: 'Агент готов принять сообщение.' }
  }
}

export type QwenChipState = {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
  /** 0–100 или null = неопределённый (загрузка в ОЗУ) */
  progress?: number | null
  progressLabel?: string
  /** Полоса вместо бейджа с текстом */
  barMode?: 'download' | 'ram' | 'none'
}

export function isQwenDownloading(q: AgentState['qwen']): boolean {
  if (q.downloadPhase === 'downloading' || q.status === 'downloading') return true
  if (q.downloadProgress > 0 && q.downloadProgress < 100) return true
  if (/скачиван/i.test(q.statusLabel) || /скачиван/i.test(q.message)) return true
  return /^\d+%$/.test((q.value || '').trim())
}

export function qwenDownloadPercent(q: AgentState['qwen']): number {
  if (q.downloadBytesTotal > 0 && q.downloadBytesDone >= 0) {
    return Math.min(
      99,
      Math.round((q.downloadBytesDone * 100) / q.downloadBytesTotal),
    )
  }
  if (q.downloadProgress > 0) return Math.min(99, q.downloadProgress)
  const m = (q.value || '').match(/(\d+)%/)
  if (m) return Math.min(99, parseInt(m[1], 10))
  return 0
}

function QwenProgressBar({
  percent,
  indeterminate,
  caption,
  bytesDone,
  bytesTotal,
}: {
  percent: number
  indeterminate?: boolean
  caption: string
  bytesDone?: number
  bytesTotal?: number
}) {
  return (
    <div className="relative h-8 w-full overflow-hidden rounded-md border border-amber-500/40 bg-amber-950/50 px-1 py-1">
      <DownloadProgress
        percent={percent}
        indeterminate={indeterminate}
        message={caption}
        bytesDone={bytesDone}
        bytesTotal={bytesTotal}
        size="md"
        className="[&_span]:text-amber-50 [&_.text-muted-foreground]:text-amber-100/80"
      />
    </div>
  )
}

/** Локальная «мозги» Jarvis — Qwen 2.5 14B (скачивание в приложение + ОЗУ ПК). */
export function qwenResponseModelChip(agent: AgentState): QwenChipState {
  const icon = <Brain className="h-5 w-5" />
  const q = agent.qwen

  if (agent.backendStatus !== 'connected') {
    return {
      value: '—',
      variant: 'secondary',
      hint: 'Статус локальной модели виден после подключения к серверу.',
      icon,
      barMode: 'none',
    }
  }

  const localAnswers =
    agent.qwenReady ||
    q.ready ||
    q.ramUsable ||
    q.ollamaModelLoaded ||
    q.embeddedReady

  if (!q.ramEnabled) {
    if (localAnswers) {
      const viaOllama = q.ollamaModelLoaded && !q.embeddedReady
      return {
        value: viaOllama
          ? q.statusLabel || 'Jarvis+Ollama'
          : q.value || 'Qwen 2.5 14B',
        variant: 'success',
        hint: [
          viaOllama
            ? 'Ответы в чате идут через Ollama (файл Qwen в Jarvis). Тумблер «ОЗУ» выключен — это нормально.'
            : 'Локальная Qwen готова (файл в Jarvis). Тумблер загрузки в ОЗУ выключен.',
          q.message,
          q.ollamaModelName ? `Ollama: ${q.ollamaModelName}` : null,
        ]
          .filter(Boolean)
          .join(' · '),
        icon,
        barMode: 'none',
      }
    }
    if (q.filesPresent) {
      return {
        value: q.value || 'Файл в Jarvis',
        variant: 'warning',
        hint:
          q.message ||
          'Модель на диске, но движок не запущен. Включите «Qwen в ОЗУ» в настройках или запустите Ollama (qwen2.5:14b).',
        icon,
        barMode: 'none',
      }
    }
    return {
      value: 'Нет модели',
      variant: 'warning',
      hint:
        [
          q.message,
          'Без GGUF (~9 ГБ, install-qwen.bat) и без Ollama полноценный чат недоступен — только справка и короткие шаблоны.',
          'Альтернатива: ключ DeepSeek (sk-…) в Настройках или backend/config/deepseek_free.key.',
        ]
          .filter(Boolean)
          .join(' '),
      icon,
      barMode: 'none',
    }
  }

  if (isQwenDownloading(q)) {
    const pct = qwenDownloadPercent(q)
    return {
      value: `${pct}%`,
      variant: 'warning',
      hint:
        q.downloadMessage ||
        q.message ||
        'Скачивание GGUF внутрь Jarvis (backend/data/models), не на весь ПК.',
      icon,
      progress: pct,
      progressLabel: 'Файл в Jarvis',
      barMode: 'download',
    }
  }

  if (q.ramPhase === 'loading') {
    return {
      value: q.value || 'В ОЗУ…',
      variant: 'warning',
      hint: q.ramMessage || q.message || 'Загрузка весов Qwen в память ПК (может занять 1–3 мин).',
      icon,
      progress: null,
      progressLabel: 'В память ПК',
      barMode: 'ram',
    }
  }

  if (q.ramPhase === 'pending' || q.status === 'pending_ram') {
    return {
      value: q.value || 'Ожидание…',
      variant: 'warning',
      hint: q.ramMessage || q.message || 'Файл в Jarvis — скоро загрузка в ОЗУ.',
      icon,
      progress: 0,
      progressLabel: 'В память ПК',
    }
  }

  if (q.ready && q.ramPhase === 'ready') {
    return {
      value: q.value || 'Qwen 2.5 14B',
      variant: 'success',
      hint: [q.ramMessage, q.message].filter(Boolean).join(' · ') || 'Модель в Jarvis и в ОЗУ ПК.',
      icon,
      progress: 100,
      progressLabel: 'В память ПК',
    }
  }

  if (q.ready || q.ollamaModelLoaded) {
    return {
      value: q.value || 'Qwen 2.5 14B',
      variant: 'success',
      hint: [
        q.message,
        q.ramMessage,
        q.ollamaModelName ? `Ollama: ${q.ollamaModelName}` : null,
        q.filesPresent && q.filesPath ? `Файл: ${q.filesPath}` : null,
      ]
        .filter(Boolean)
        .join(' · '),
      icon,
    }
  }

  if (q.ramPhase === 'error' || q.status === 'ram_error') {
    return {
      value: q.value || 'Файл OK',
      variant: q.ready ? 'success' : 'warning',
      hint:
        q.ramMessage ||
        q.message ||
        'Модель в Jarvis на диске. Если llama-cpp не подходит для CPU — нужен Ollama (qwen2.5:14b).',
      icon,
      barMode: q.ready ? 'none' : 'ram',
      progress: q.ready ? 100 : 0,
    }
  }

  if (q.filesPresent) {
    return {
      value: q.value || 'Файл OK',
      variant: 'warning',
      hint:
        q.message ||
        'Файл в Jarvis есть — идёт или нужна загрузка в ОЗУ (restart.bat / start.bat).',
      icon,
      progress: 0,
      progressLabel: 'В память ПК',
    }
  }

  if (q.ollamaReachable && !q.ollamaModelLoaded && !isQwenDownloading(q)) {
    return {
      value: 'Нужен install-qwen',
      variant: 'warning',
      hint:
        q.message ||
        `Модель ставится внутрь Jarvis: install-qwen.bat → backend/data/models (~9 ГБ). Ollama — только запас.`,
      icon,
      barMode: 'none',
    }
  }

  return {
    value: q.value || 'Не подключена',
    variant: 'muted',
    hint:
      q.message ||
      'Qwen 2.5 14B — внутрь Jarvis (install-qwen.bat → backend/data/models, ~9 ГБ).',
    icon,
  }
}

const CHROMIUM_ACTIVE_PHASES = new Set([
  'checking_internet',
  'installing_playwright',
  'downloading',
])

export function isChromiumInstalling(browser: ChromiumBrowserState): boolean {
  if (browser.ready) return false
  if (browser.installInProgress) return true
  return CHROMIUM_ACTIVE_PHASES.has(browser.installPhase)
}

export function chromiumInstallPercent(browser: ChromiumBrowserState): number {
  if (browser.installProgress > 0) return Math.min(99, browser.installProgress)
  if (browser.installPhase === 'checking_internet') return 5
  if (browser.installPhase === 'installing_playwright') return 12
  return 0
}

export type ChromiumChipState = {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
  barMode?: 'install' | 'none'
  progress?: number | null
}

/** Встроенный Chromium (Playwright) — страницы с JavaScript, fetch_url. */
export function chromiumBrowserChip(
  browser: ChromiumBrowserState,
  backendOk: boolean,
  agentStatus?: AgentStatus,
): ChromiumChipState {
  const icon = <Globe className="h-5 w-5" />

  if (!backendOk) {
    return {
      value: 'Нет связи',
      variant: 'secondary',
      hint: 'Статус браузера — после запуска сервера Jarvis.',
      icon,
      barMode: 'none',
    }
  }
  if (agentStatus === 'Searching Web...') {
    return {
      value: 'Страница…',
      variant: 'default',
      hint: 'Встроенный Chromium открывает ссылку (fetch_url).',
      icon,
      barMode: 'none',
    }
  }
  if (isChromiumInstalling(browser)) {
    const pct = chromiumInstallPercent(browser)
    return {
      value: `${pct}%`,
      variant: 'warning',
      hint:
        browser.installMessage ||
        browser.detail ||
        'Jarvis скачивает Chromium (как install-chromium.bat). Полоса — здесь.',
      icon,
      barMode: 'install',
      progress: pct,
    }
  }
  if (browser.installPhase === 'no_internet') {
    if (browser.systemInternetOk) {
      const pct = Math.max(8, browser.installProgress || 8)
      return {
        value: `${pct}%`,
        variant: 'warning',
        hint:
          browser.installMessage ||
          browser.detail ||
          'Интернет Windows есть — Jarvis повторяет скачивание Chromium.',
        icon,
        barMode: 'install',
        progress: pct,
      }
    }
    return {
      value: 'Скачивание…',
      variant: 'warning',
      hint:
        browser.installMessage ||
        browser.detail ||
        'Для Chromium нужен выход в сеть. Jarvis повторит установку автоматически.',
      icon,
      barMode: 'none',
    }
  }
  if (browser.installPhase === 'error') {
    return {
      value: 'Ошибка',
      variant: 'warning',
      hint:
        [browser.installMessage, browser.installError].filter(Boolean).join(' ') ||
        browser.detail ||
        'Перезапустите Jarvis или install-chromium.bat.',
      icon,
      barMode: 'none',
    }
  }
  if (browser.statusLabel === 'Ошибка запуска') {
    return {
      value: 'Ошибка запуска',
      variant: 'warning',
      hint:
        browser.detail ||
        'Chromium скачан, но Playwright не смог его запустить. restart.bat или install-chromium.bat.',
      icon,
      barMode: 'none',
    }
  }
  if (browser.ready) {
    return {
      value: browser.statusLabel || 'Chromium',
      variant: 'success',
      hint:
        browser.detail ||
        'Headless Chromium внутри Jarvis. Страницы — лучший ответ из Chromium + Chrome Jarvis.',
      icon,
      barMode: 'none',
    }
  }
  if (browser.playwrightInstalled && !browser.browserInstalled) {
    if (browser.installInProgress) {
      const pct = chromiumInstallPercent(browser)
      return {
        value: `${pct}%`,
        variant: 'warning',
        hint: browser.installMessage || browser.detail || 'Скачивание Chromium…',
        icon,
        barMode: 'install',
        progress: pct,
      }
    }
    const label = browser.statusLabel?.trim() || 'Chromium…'
    return {
      value: label,
      variant: 'warning',
      hint:
        [browser.installMessage, browser.detail].filter(Boolean).join(' · ') ||
        'Jarvis ставит Chromium (~180 МБ). Если долго на «Старт» — install-chromium.bat или restart.bat.',
      icon,
      barMode: 'none',
    }
  }
  if (!browser.playwrightInstalled) {
    if (browser.installInProgress) {
      const pct = chromiumInstallPercent(browser)
      return {
        value: `${pct}%`,
        variant: 'warning',
        hint: browser.installMessage || browser.detail || 'Установка Playwright…',
        icon,
        barMode: 'install',
        progress: pct,
      }
    }
    const label = browser.statusLabel?.trim() || 'Playwright…'
    return {
      value: label,
      variant: 'warning',
      hint:
        [browser.installMessage, browser.detail].filter(Boolean).join(' · ') ||
        'Установка Playwright и Chromium. Зависло >2 мин — install-chromium.bat.',
      icon,
      barMode: 'none',
    }
  }
  return {
    value: browser.statusLabel || '—',
    variant: 'muted',
    hint: browser.detail || 'Модуль браузера',
    icon,
    barMode: 'none',
  }
}

/** Google Chrome — оконный режим (2ГИС и сложные сайты). */
export function googleChromeChip(
  chrome: GoogleChromeState,
  backendOk: boolean,
): ChromiumChipState {
  const icon = <Globe className="h-5 w-5" />
  if (!backendOk) {
    return {
      value: 'Нет связи',
      variant: 'secondary',
      hint: 'Статус Chrome — после запуска сервера.',
      icon,
      barMode: 'none',
    }
  }
  if (!chrome.requiredOnWindows) {
    return {
      value: 'Не нужен',
      variant: 'muted',
      hint: 'Google Chrome для оконного режима — только Windows.',
      icon,
      barMode: 'none',
    }
  }
  if (chrome.installInProgress) {
    return {
      value: 'Установка…',
      variant: 'warning',
      hint: chrome.installMessage || chrome.detail || 'winget install Google.Chrome',
      icon,
      barMode: 'none',
    }
  }
  if (chrome.ready) {
    return {
      value: chrome.statusLabel || 'Chrome',
      variant: 'success',
      hint:
        chrome.detail ||
        'Chrome внутри Jarvis: UI приложения и оконный режим для сложных сайтов.',
      icon,
      barMode: 'none',
    }
  }
  return {
    value: 'Нужен Chrome',
    variant: 'warning',
    hint:
      chrome.detail ||
        'Jarvis скачает Chrome в свою папку (start.bat / install-google-chrome.bat).',
    icon,
    barMode: 'none',
  }
}

export function GoogleChromeStatusChip({ agent }: { agent: AgentState }) {
  return <JarvisBrowserStatusChip agent={agent} />
}

export function ChromiumBrowserStatusChip({ agent }: { agent: AgentState }) {
  return <JarvisBrowserStatusChip agent={agent} />
}

/** Единый индикатор: headless Chromium (fetch_url) + Chrome Jarvis (окна на Windows). */
export function JarvisBrowserStatusChip({ agent }: { agent: AgentState }) {
  const browser = agent.chromiumBrowser
  const chrome = agent.googleChrome
  const backendOk = agent.backendStatus === 'connected'
  const ch = chromiumBrowserChip(browser, backendOk, agent.status)
  const gc = googleChromeChip(chrome, backendOk)
  const installing = browser.installInProgress || chrome.installInProgress
  const pct = installing ? chromiumInstallPercent(browser) : 0

  let value = ch.value
  let variant = ch.variant
  let hint = ch.hint

  if (backendOk && browser.ready && (!chrome.requiredOnWindows || chrome.ready)) {
    value = 'На связи'
    variant = 'success'
    hint =
      'Браузер Jarvis: headless Chromium (ссылки, fetch_url) и Chrome для оконного режима на Windows.'
  } else if (installing) {
    value = browser.installInProgress ? ch.value : gc.value
    variant = 'warning'
    hint = browser.installMessage || chrome.installMessage || hint
  } else if (!browser.ready) {
    value = ch.value
    variant = ch.variant
    hint = ch.hint
  } else if (chrome.requiredOnWindows && !chrome.ready) {
    value = gc.value
    variant = gc.variant
    hint = gc.hint
  }

  const barCaption = installing
    ? browser.installMessage?.slice(0, 40) || `Chromium ${pct}%`
    : value

  return (
    <Hint text={hint}>
      <div className="flex h-[88px] w-[12.25rem] shrink-0 cursor-default flex-col justify-between rounded-md border border-border/50 bg-background/60 px-2 py-1.5">
        <p className="line-clamp-1 text-[13px] font-medium leading-snug text-muted-foreground">
          Браузер Jarvis
        </p>
        {installing ? (
          <QwenProgressBar
            percent={pct}
            indeterminate={pct <= 0}
            caption={barCaption}
          />
        ) : (
          <Badge
            variant={variant}
            className="h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal"
          >
            {ch.icon}
            <span className="truncate">{value}</span>
          </Badge>
        )}
      </div>
    </Hint>
  )
}

const ENGINE_LABELS: Record<string, string> = {
  qwen: 'Qwen (локально)',
  ollama: 'Qwen через Ollama',
  ollama_runtime: 'Qwen · Ollama',
  embedded: 'Qwen в Jarvis',
  capabilities: 'Справка Jarvis',
  greeting: 'Приветствие',
  story: 'Qwen · сказка',
  neural_stack: 'Справка · нейросети',
  dialog: 'Правила Jarvis',
  icq_smileys: 'Смайлики ICQ',
  deepseek: 'DeepSeek (облако)',
  perplexity: 'Perplexity',
  'no_deepseek': 'Qwen (нет DeepSeek)',
  'no_perplexity': 'Qwen (нет Perplexity)',
  media_guard: 'Подсказка · медиа',
  fallback: 'Справка без LLM',
  keywords: 'Qwen · эвристика',
  avito_caps: 'Справка · Авито',
  avito_overview: 'Авито · обзор API',
  avito_action: 'Авито · действие',
  avito_stats: 'Авито · статистика',
  avito_hr: 'Авито · HR',
  avito_audit: 'Авито · аудит',
  'qwen+tools': 'Qwen + инструменты',
}

function resolveEngineLabel(engine: string, intent: string): string {
  const eng = engine.toLowerCase()
  const base = eng.split('+')[0]
  if (ENGINE_LABELS[eng]) return ENGINE_LABELS[eng]
  if (ENGINE_LABELS[base]) return ENGINE_LABELS[base]
  if (intent === 'COMPLEX_TEXT') return 'Облако (API)'
  if (intent === 'GEN_IMAGE') return 'Генерация картинки'
  if (intent === 'DOC_ACTION') return 'Документ / файл'
  return engine || 'Jarvis'
}

function engineChipVariant(engine: string, intent: string): BadgeVariant {
  const eng = engine.toLowerCase()
  const base = eng.split('+')[0]
  if (eng.includes('no_deepseek') || eng.includes('no_perplexity')) return 'warning'
  if (base === 'fallback') return 'warning'
  if (
    base.startsWith('ollama') ||
    base === 'qwen' ||
    base === 'embedded' ||
    base === 'dialog' ||
    base === 'capabilities' ||
    base === 'greeting' ||
    base === 'story' ||
    base === 'keywords'
  ) {
    return 'success'
  }
  if (base === 'deepseek' || intent === 'COMPLEX_TEXT') return 'default'
  if (base === 'media_guard' || base === 'url_page') return 'warning'
  return 'default'
}

/** Режим чата: полная нейросеть или только справка без LLM. */
export function chatModeChip(agent: AgentState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Cpu className="h-5 w-5" />
  if (agent.backendStatus !== 'connected') {
    return {
      value: '—',
      variant: 'secondary',
      hint: 'Режим чата — после подключения к серверу.',
      icon,
    }
  }
  const ready =
    agent.chatLlmReady ??
    agent.qwenReady ??
    agent.neuralReady ??
    (agent.deepseekUsable && agent.deepseekConfigured)
  if (ready) {
    return {
      value: agent.chatModeLabel || 'Нейросеть',
      variant: 'success',
      hint:
        agent.chatModeDetail ||
        'Qwen и/или DeepSeek доступны — обычные ответы в чате.',
      icon,
    }
  }
  return {
    value: agent.chatModeLabel || 'Только справка',
    variant: 'warning',
    hint:
      agent.chatModeDetail ||
      'Нет модели Qwen и нет DeepSeek — ответы из шаблонов, не «умный» диалог.',
    icon,
  }
}

export function lastReplySourceChip(agent: AgentState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Sparkles className="h-5 w-5" />
  const r = agent.router
  const thinking =
    agent.backendStatus === 'connected' &&
    (agent.status === 'Thinking...' ||
      agent.status === 'Searching Web...' ||
      agent.status === 'Generating image...')

  if (!r?.lastEngine && !r?.lastIntent) {
    return {
      value: thinking ? 'Готовится…' : '—',
      variant: thinking ? 'default' : 'muted',
      hint: thinking
        ? 'Идёт ответ — источник появится сразу после классификации запроса.'
        : 'Напишите в чат — здесь будет, кто ответил: Qwen, DeepSeek или правило Jarvis (не путать с «включено в настройках»).',
      icon,
    }
  }
  const eng = r.lastEngine || ''
  const intent = r.lastIntent || ''
  const label = resolveEngineLabel(eng, intent)
  const hint = [
    thinking ? 'Сейчас формируется ответ по этому маршруту.' : null,
    r.lastIntent ? `Интент: ${r.lastIntent}` : null,
    r.lastEngine ? `Движок: ${r.lastEngine}` : null,
    agent.model && intent === 'COMPLEX_TEXT' ? `Модель API: ${agent.model}` : null,
    'Показывает последний завершённый или текущий маршрут на этом сервере.',
  ]
    .filter(Boolean)
    .join(' · ')
  const value = thinking ? `→ ${label}` : label
  return {
    value,
    variant: thinking ? 'default' : engineChipVariant(eng, intent),
    hint,
    icon,
  }
}

/** Чип Qwen: при скачивании — полоса прогресса вместо бейджа «Нужен install-qwen». */
export function DeepSeekStatusChip({ agent }: { agent: AgentState }) {
  const chip = deepseekCloudChip(agent)
  return (
    <Hint text={chip.hint}>
      <div className={CHIP_BOX}>
        <div>
          <p className="line-clamp-1 text-[13px] font-medium leading-snug text-muted-foreground">
            DeepSeek
          </p>
          <p className="line-clamp-1 text-[9px] leading-snug text-muted-foreground/75">
            Облачный текст (интернет)
          </p>
        </div>
        <Badge variant={chip.variant} className="h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal">
          {chip.icon}
          <span className="truncate">{chip.value}</span>
        </Badge>
      </div>
    </Hint>
  )
}

export function sttGigaamChip(agent: AgentState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Mic className="h-4 w-4" />
  const stt = agent.stt
  if (agent.backendStatus !== 'connected') {
    return {
      value: '—',
      variant: 'muted',
      hint: 'STT (речь → текст): после запуска сервера Jarvis.',
      icon,
    }
  }
  if (stt.error) {
    return {
      value: 'Ошибка',
      variant: 'warning',
      hint: `${stt.error.slice(0, 120)} · install-chat-voice.bat (GigaAM-v3).`,
      icon,
    }
  }
  if (stt.loading) {
    return {
      value: 'Загрузка…',
      variant: 'default',
      hint: 'GigaAM-v3 загружается в память (~430 МБ).',
      icon,
    }
  }
  if (stt.gigaamActive && stt.engine === 'gigaam') {
    return {
      value: 'GigaAM-v3',
      variant: 'success',
      hint: stt.message || 'Распознавание русской речи — микрофон → текст.',
      icon,
    }
  }
  if (stt.gigaamInstalled && stt.ffmpeg) {
    return {
      value: stt.ready ? 'Готов' : 'Ожидание',
      variant: stt.ready ? 'success' : 'warning',
      hint:
        stt.message ||
        'GigaAM-v3 установлен. Скажите фразу в микрофон — модель загрузится при первом запросе.',
      icon,
    }
  }
  return {
    value: 'Нужен install',
    variant: 'warning',
    hint: 'STT: install-chat-voice.bat (GigaAM-v3 + ffmpeg). Превращает речь в текст.',
    icon,
  }
}

export function SttGigaamStatusChip({ agent }: { agent: AgentState }) {
  const chip = sttGigaamChip(agent)
  return (
    <Hint text={chip.hint}>
      <div className={CHIP_BOX}>
        <div>
          <p className="line-clamp-1 text-[13px] font-medium leading-snug text-muted-foreground">
            GigaAM-v3 (STT)
          </p>
          <p className="line-clamp-1 text-[9px] leading-snug text-muted-foreground/75">
            Речь → текст (микрофон)
          </p>
        </div>
        <Badge variant={chip.variant} className="h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal">
          {chip.icon}
          <span className="truncate">{chip.value}</span>
        </Badge>
      </div>
    </Hint>
  )
}

export function ttsSpeechChip(agent: AgentState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Volume2 className="h-4 w-4" />
  const cv = agent.chatVoice
  const x = agent.xtts

  if (agent.backendStatus !== 'connected') {
    return {
      value: '—',
      variant: 'muted',
      hint: 'TTS (текст → голос): после запуска сервера.',
      icon,
    }
  }

  if (x.status === 'installing_deps' || x.status === 'downloading_model') {
    return {
      value: `Silero ${x.progress || 0}%`,
      variant: 'default',
      hint: x.message || 'Установка Silero TTS v5…',
      icon,
    }
  }

  if (cv.ready) {
    const voice = cv.speaker || 'aidar'
    const model = cv.model || 'v5_ru'
    return {
      value: 'На связи',
      variant: 'success',
      hint: `${cv.message || 'Silero готов'} · ${model}, голос ${voice}. Ссылки не озвучиваются.`,
      icon,
    }
  }

  if (!cv.sileroReady && !cv.xttsReady) {
    return {
      value: 'Нужен Silero',
      variant: 'warning',
      hint: 'Настройки → Голос и озвучка → «Установить Silero».',
      icon,
    }
  }

  return {
    value: 'Настройка',
    variant: 'warning',
    hint: cv.message || 'Выберите голос Silero в настройках.',
    icon,
  }
}

export function TtsSpeechStatusChip({ agent }: { agent: AgentState }) {
  const chip = ttsSpeechChip(agent)
  return (
    <Hint text={chip.hint}>
      <div className={CHIP_BOX}>
        <div>
          <p className="line-clamp-1 text-[13px] font-medium leading-snug text-muted-foreground">
            Озвучка (TTS)
          </p>
          <p className="line-clamp-1 text-[9px] leading-snug text-muted-foreground/75">
            Silero TTS · текст → голос
          </p>
        </div>
        <Badge variant={chip.variant} className="h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal">
          {chip.icon}
          <span className="truncate">{chip.value}</span>
        </Badge>
      </div>
    </Hint>
  )
}

export function SessionTokensChip({
  tokens,
  compact = false,
}: {
  tokens: number
  compact?: boolean
}) {
  const box = compact ? CHIP_BOX_COMPACT : CHIP_BOX
  const labelCls = compact
    ? 'line-clamp-1 text-[10px] font-medium text-muted-foreground'
    : 'line-clamp-2 text-[13px] font-medium leading-snug text-muted-foreground'
  const badgeCls = compact
    ? 'h-5 w-full justify-center gap-0.5 px-1 text-[11px] font-normal'
    : 'h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal'
  return (
    <Hint text="Расход токенов в текущем сеансе чата.">
      <div className={box}>
        <p className={labelCls}>Токены</p>
        <Badge variant="muted" className={badgeCls}>
          <Cpu className={compact ? 'h-3 w-3 text-muted-foreground' : 'h-4 w-4 text-muted-foreground'} />
          <span className="truncate tabular-nums">{tokens.toLocaleString('ru-RU')}</span>
        </Badge>
      </div>
    </Hint>
  )
}

const CHIP_BOX_SIDEBAR =
  'flex h-[44px] w-full min-w-[6.125rem] max-w-full shrink-0 cursor-default flex-col items-center justify-between rounded-md border border-border/50 bg-background/60 px-1.5 py-1'

export function AgentStatusChip({
  agent,
  compact = false,
  square = false,
}: {
  agent: AgentState
  compact?: boolean
  /** Квадратный чип для сайдбара — подпись «Агент» по центру */
  square?: boolean
}) {
  const ag = agentChip(agent.status, agent.backendStatus)
  const box = square ? CHIP_BOX_SIDEBAR : compact ? CHIP_BOX_COMPACT : CHIP_BOX
  const labelCls = square
    ? 'w-full text-center text-[10px] font-medium leading-none text-muted-foreground'
    : compact
      ? 'line-clamp-1 text-[10px] font-medium text-muted-foreground'
      : 'line-clamp-2 text-[15px] font-medium leading-snug text-muted-foreground'
  const badgeCls = compact || square
    ? 'h-5 w-full justify-center gap-0.5 px-0.5 text-[11px] font-normal'
    : 'h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal'
  return (
    <Hint text={ag.hint}>
      <div className={box}>
        <p className={labelCls}>Агент</p>
        <Badge variant={ag.variant} className={badgeCls}>
          <Activity className={compact || square ? 'h-3 w-3' : 'h-4 w-4'} />
          <span className={square ? 'whitespace-nowrap' : 'truncate'}>{ag.value}</span>
        </Badge>
      </div>
    </Hint>
  )
}

export function mailAccountChip(slot: MailAccountSlot, backendOk: boolean) {
  const icon = <Mail className="h-4 w-4" />
  if (!backendOk) {
    return {
      value: '—',
      variant: 'secondary' as BadgeVariant,
      hint: 'Почта — после запуска сервера.',
      icon,
    }
  }
  if (!slot.configured) {
    return {
      value: 'Пусто',
      variant: 'muted' as BadgeVariant,
      hint: `Ящик ${slot.slot}: добавьте email и пароль в Настройках → Почтовый клиент.`,
      icon,
    }
  }
  if (!slot.enabled) {
    return {
      value: 'Выкл',
      variant: 'muted' as BadgeVariant,
      hint: `${slot.label}: отключён.`,
      icon,
    }
  }
  if (slot.status === 'ok') {
    const prov = slot.provider ? String(slot.provider).toUpperCase() : 'ПОЧТА'
    return {
      value: 'OK',
      variant: 'success' as BadgeVariant,
      hint: slot.lastEvent || `${slot.label} (${slot.email}) — ${prov} подключён.`,
      icon,
    }
  }
  if (slot.status === 'need_creds') {
    return {
      value: 'Нет данных',
      variant: 'warning' as BadgeVariant,
      hint: 'Укажите email и пароль (для Gmail — пароль приложения).',
      icon,
    }
  }
  if (slot.status === 'error') {
    return {
      value: 'Ошибка',
      variant: 'warning' as BadgeVariant,
      hint: slot.error || slot.lastEvent || 'Не удалось войти по IMAP.',
      icon,
    }
  }
  return {
    value: slot.statusLabel || '—',
    variant: 'secondary' as BadgeVariant,
    hint: slot.lastEvent || 'Нажмите «Проверить» в настройках.',
    icon,
  }
}

export function MailAccountStatusChip({
  slot,
  backendOk,
  compact = false,
}: {
  slot: MailAccountSlot
  backendOk: boolean
  compact?: boolean
}) {
  const chip = mailAccountChip(slot, backendOk)
  const box = compact ? CHIP_BOX_COMPACT : CHIP_BOX
  const title = slot.email ? slot.label || slot.email : `Почта ${slot.slot}`
  return (
    <Hint text={chip.hint}>
      <div className={box}>
        <p className="line-clamp-1 text-[10px] font-medium text-muted-foreground">{title}</p>
        <Badge
          variant={chip.variant}
          className={
            compact
              ? 'h-5 w-full justify-center gap-0.5 px-1 text-[10px] font-normal'
              : 'h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal'
          }
        >
          {chip.icon}
          <span className="truncate">{chip.value}</span>
        </Badge>
      </div>
    </Hint>
  )
}

export function QwenStatusChip({ agent }: { agent: AgentState }) {
  const chip = qwenResponseModelChip(agent)
  const q = agent.qwen
  const downloading = chip.barMode === 'download' || isQwenDownloading(q)
  const ramLoad = chip.barMode === 'ram' || q.ramPhase === 'loading'
  const pct = downloading ? qwenDownloadPercent(q) : chip.progress ?? 0

  let barCaption = chip.value
  if (downloading) {
    const mb =
      q.downloadBytesTotal > 0
        ? `${Math.round(q.downloadBytesDone / (1024 * 1024))} / ${Math.round(q.downloadBytesTotal / (1024 * 1024))} МБ`
        : null
    barCaption = mb ? `${pct}% · ${mb}` : `Скачивание ${pct}%`
  } else if (ramLoad) {
    barCaption = 'В память ПК…'
  }

  return (
    <Hint text={chip.hint}>
      <div className="flex h-[88px] w-[12.25rem] shrink-0 cursor-default flex-col justify-between rounded-md border border-border/50 bg-background/60 px-2 py-1.5">
        <div>
          <p className="line-clamp-1 text-[13px] font-medium leading-snug text-muted-foreground">
            Qwen 2.5 14B
          </p>
          <p className="line-clamp-1 text-[9px] leading-snug text-muted-foreground/75">
            Локальный текст (без интернета)
          </p>
        </div>
        {downloading || ramLoad ? (
          <QwenProgressBar
            percent={pct}
            indeterminate={(downloading && pct <= 0) || (ramLoad && chip.progress === null)}
            caption={barCaption}
            bytesDone={downloading ? q.downloadBytesDone : undefined}
            bytesTotal={downloading ? q.downloadBytesTotal : undefined}
          />
        ) : (
          <Badge
            variant={chip.variant}
            className="h-8 w-full justify-center gap-1 px-1.5 text-[15px] font-normal"
          >
            {chip.icon}
            <span className="truncate">{chip.value}</span>
          </Badge>
        )}
      </div>
    </Hint>
  )
}

function ValueChip({
  label,
  hint,
  value,
  icon,
  warn,
}: {
  label: string
  hint: string
  value: string
  icon: ReactNode
  warn?: boolean
}) {
  return (
    <Hint text={hint}>
      <div className={CHIP_BOX}>
        <p className="line-clamp-2 text-[15px] font-medium leading-snug text-muted-foreground">
          {label}
        </p>
        <div
          className={cn(
            'flex h-10 items-center justify-center gap-1 font-mono text-[18px]',
            warn && 'text-amber-700 dark:text-amber-300',
          )}
        >
          {icon}
          <span className="truncate">{value}</span>
        </div>
      </div>
    </Hint>
  )
}

export function motherCoreChip(tg: TelegramState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Send className="h-5 w-5" />

  if (!tg.botTokenConfigured) {
    return {
      value: 'Нет токена',
      variant: 'warning',
      hint: 'Токен BotFather в сайдбаре → «Сохранить токен».',
      icon,
    }
  }
  if (tg.status === 'error') {
    return {
      value: 'Ошибка',
      variant: 'warning',
      hint: tg.error ?? tg.lastEvent ?? 'Проверьте токен и api.telegram.org',
      icon,
    }
  }
  if (tg.status === 'waiting' || (tg.enabled && !tg.pollingActive)) {
    return {
      value: 'Запуск…',
      variant: 'default',
      hint: tg.lastEvent || 'Подключение к Telegram API',
      icon,
    }
  }
  if (tg.status === 'active' && tg.pollingActive) {
    return {
      value: tg.botUsername ? `@${tg.botUsername}` : 'Работает',
      variant: 'success',
      hint: `Бот активен · ${tg.botLogicName ?? 'bot_logic.json'}`,
      icon,
    }
  }
  if (tg.enabled && tg.status === 'active') {
    return { value: 'На связи', variant: 'success', hint: tg.lastEvent || 'Бот подключён', icon }
  }
  if (tg.botTokenConfigured) {
    return {
      value: 'Токен OK',
      variant: 'muted',
      hint: 'Включите «Сервер бота» в Настройках → Коннектор Телеграм.',
      icon,
    }
  }
  return { value: 'Выкл', variant: 'muted', hint: 'Коннектор Телеграм остановлен', icon }
}

export function avitoApiChip(avito: AvitoState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <BarChart3 className="h-5 w-5" />
  const ok = avito.clientIdConfigured && avito.clientSecretConfigured
  if (ok) {
    return {
      value: 'Ключи OK',
      variant: 'success',
      hint: 'Client ID и Secret Авито сохранены (developers.avito.ru).',
      icon,
    }
  }
  if (avito.clientIdConfigured || avito.clientSecretConfigured) {
    return {
      value: 'Частично',
      variant: 'warning',
      hint: 'Укажите оба ключа в Настройках → Коннектор Авито.',
      icon,
    }
  }
  return {
    value: 'Нет ключей',
    variant: 'warning',
    hint: 'Ключи API Авито не заданы — Настройки → Коннектор Авито.',
    icon,
  }
}

export function avitoSyncChip(avito: AvitoState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <BarChart3 className="h-5 w-5" />
  if (!avito.clientIdConfigured || !avito.clientSecretConfigured) {
    return {
      value: '—',
      variant: 'muted',
      hint: 'Синхронизация статистики — после сохранения ключей API.',
      icon,
    }
  }
  if (avito.status === 'error') {
    return {
      value: 'Ошибка',
      variant: 'warning',
      hint: avito.error ?? avito.lastEvent ?? 'Ошибка API Авито',
      icon,
    }
  }
  if (avito.enabled && avito.status === 'active') {
    return {
      value: 'Активна',
      variant: 'success',
      hint: `Сбор статистики объявлений${avito.lastSyncDate ? ` · ${avito.lastSyncDate}` : ''}.`,
      icon,
    }
  }
  if (avito.enabled) {
    return {
      value: 'Запуск…',
      variant: 'default',
      hint: avito.lastEvent || 'Включение синхронизации',
      icon,
    }
  }
  return {
    value: 'Выкл',
    variant: 'muted',
    hint: 'Включите синхронизацию в Настройках → Коннектор Авито.',
    icon,
  }
}

export function tgTokenChip(tg: TelegramState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Send className="h-5 w-5" />
  if (tg.botTokenConfigured) {
    return {
      value: 'Загружен',
      variant: 'success',
      hint: 'Токен BotFather сохранён. Настройка — Коннектор Телеграм.',
      icon,
    }
  }
  return {
    value: 'Требуется',
    variant: 'warning',
    hint: 'Настройки → Коннектор Телеграм: вставьте токен и «Сохранить токен».',
    icon,
  }
}

export function tgServerChip(tg: TelegramState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  return motherCoreChip(tg)
}

export function tgLogicChip(tg: TelegramState): {
  value: string
  variant: BadgeVariant
  hint: string
} {
  if (!tg.botLogicConfigured) {
    return {
      value: 'Нет файла',
      variant: 'muted',
      hint: 'Сохраните bot_logic.json — Настройки → Коннектор Телеграм.',
    }
  }
  if (tg.botLogicValid) {
    const name = tg.botLogicName ?? 'bot_logic'
    return {
      value: 'Валидна',
      variant: 'success',
      hint: `JSON корректен и проходит проверку схемы («${name}»). Бот использует этот файл.`,
    }
  }
  const err = tg.botLogicError?.trim()
  return {
    value: 'Ошибка',
    variant: 'warning',
    hint: err
      ? `Файл есть, но не «компилируется»: ${err}`
      : 'Файл bot_logic.json не проходит проверку схемы — исправьте JSON в сайдбаре.',
  }
}

export function mediaGenerationChip(agent: AgentState): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Image className="h-5 w-5" />
  if (agent.backendStatus !== 'connected') {
    return {
      value: '—',
      variant: 'secondary',
      hint: 'Медиа-провайдеры — после подключения к серверу.',
      icon,
    }
  }
  if (agent.mediaImageReady || agent.mediaVideoReady) {
    const parts: string[] = []
    if (agent.mediaImageReady) parts.push('картинки')
    if (agent.mediaVideoReady) parts.push('видео')
    return {
      value: 'Готов',
      variant: 'success',
      hint: `Доступна генерация: ${parts.join(' и ')} (Ideogram, Nano Banana, OpenAI, xAI — что включено).`,
      icon,
    }
  }
  const hasAnyKey =
    agent.ideogramConfigured ||
    agent.nanobananaConfigured ||
    agent.openaiConfigured ||
    agent.xaiConfigured
  if (hasAnyKey) {
    return {
      value: 'Выключено',
      variant: 'muted',
      hint: 'Ключи есть, но медиа-сервисы выключены тумблерами в Настройках.',
      icon,
    }
  }
  return {
    value: 'Нужен ключ',
    variant: 'warning',
    hint: 'Добавьте Ideogram, Nano Banana, OpenAI или xAI в ⚙️ Настройках для картинок/видео.',
    icon,
  }
}

/** @deprecated Используйте mediaGenerationChip */
export function nanobananaChip(
  configured: boolean,
  mode: AgentMode,
): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  void configured
  void mode
  return mediaGenerationChip({
    backendStatus: 'connected',
    mediaImageReady: configured,
    ideogramConfigured: false,
    nanobananaConfigured: configured,
    openaiConfigured: false,
    xaiConfigured: false,
  } as AgentState)
}

function genericApiKeyChip(
  configured: boolean,
  backendOk: boolean,
  label: string,
  hintOk: string,
  hintMissing: string,
  icon: ReactNode,
): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  if (!backendOk) {
    return {
      value: '—',
      variant: 'secondary',
      hint: 'Сначала запустите сервер Jarvis.',
      icon,
    }
  }
  if (configured) {
    return { value: 'Ключ OK', variant: 'success', hint: hintOk, icon }
  }
  return { value: 'Нет ключа', variant: 'warning', hint: hintMissing, icon }
}

export function perplexityKeyChip(configured: boolean, backendOk: boolean) {
  return genericApiKeyChip(
    configured,
    backendOk,
    'Perplexity',
    'Ключ pplx-… сохранён — поиск с источниками.',
    'Ключ Perplexity (pplx-…) в Настройках.',
    <Sparkles className="h-5 w-5" />,
  )
}

export function xaiKeyChip(configured: boolean, backendOk: boolean) {
  return genericApiKeyChip(
    configured,
    backendOk,
    'Grok',
    'Ключ xAI сохранён.',
    'Ключ Grok (xai-…) в Настройках.',
    <Sparkles className="h-5 w-5" />,
  )
}

export function openaiKeyChip(configured: boolean, backendOk: boolean) {
  return genericApiKeyChip(
    configured,
    backendOk,
    'OpenAI',
    'Ключ OpenAI (sk-…) сохранён.',
    'Ключ ChatGPT (sk-…) в Настройках.',
    <Brain className="h-5 w-5" />,
  )
}

export function telephonyChip(
  tel: import('@/types').TelephonyState,
  backendOk: boolean,
): {
  value: string
  variant: BadgeVariant
  hint: string
  icon: ReactNode
} {
  const icon = <Phone className="h-5 w-5" />
  if (!backendOk) {
    return {
      value: '—',
      variant: 'secondary',
      hint: 'АТС видна после подключения к серверу.',
      icon,
    }
  }
  if (!tel.enabled) {
    return {
      value: 'Выкл',
      variant: 'muted',
      hint: 'Включите АТС в Настройках → «АТС — звонки на Джарвис».',
      icon,
    }
  }
  if (tel.status === 'active') {
    return {
      value: 'На линии',
      variant: 'default',
      hint: tel.lastEvent || 'Обработка входящего звонка.',
      icon,
    }
  }
  if (tel.status === 'error') {
    return {
      value: 'Ошибка',
      variant: 'warning',
      hint: tel.lastEvent || 'Проверьте webhook и ключи Mango/Zadarma.',
      icon,
    }
  }
  const creds =
    tel.mangoApiKeyConfigured || tel.webhookSecretConfigured || Boolean(tel.publicBaseUrl)
  if (tel.greetingReady && creds) {
    return {
      value: 'Готов',
      variant: 'success',
      hint: `${tel.statusLabel}. ${tel.lastEvent || 'Webhook и приветствие настроены.'}`,
      icon,
    }
  }
  if (creds) {
    return {
      value: tel.statusLabel || 'Настройка',
      variant: 'warning',
      hint: tel.lastEvent || 'Синтезируйте приветствие в Настройках.',
      icon,
    }
  }
  return {
    value: 'Нужны ключи',
    variant: 'warning',
    hint: 'Укажите публичный URL и ключи провайдера АТС в Настройках.',
    icon,
  }
}
