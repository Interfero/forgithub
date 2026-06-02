import {
  agentChip,
  chromiumInstallPercent,
  deepseekCloudChip,
  isQwenDownloading,
  qwenDownloadPercent,
  qwenResponseModelChip,
} from '@/lib/statusIndicators'
import { resolveJarvisAvatarAnim } from '@/lib/jarvisAvatarAnim'
import { insultOffendedRemainingMin, isJarvisOffended } from '@/lib/jarvisInsult'
import type { AgentMode, AgentState, AgentStatus } from '@/types'
import { MODE_LABELS } from '@/types'

export type JarvisAvatarAnim =
  | 'offline'
  | 'boot'
  | 'loading'
  | 'corePending'
  | 'angry'
  | 'idle'
  | 'listen'
  | 'think'
  | 'search'
  | 'image'

export type ReadinessTone = 'ok' | 'warn' | 'muted' | 'active' | 'error'

/** Деления линейки на полоске (10 равных частей, 0–100 %). */
export const READINESS_RULER_STEPS = 10

export interface ReadinessMetric {
  id: string
  label: string
  percent: number
  hint: string
  /** Что сделать, чтобы довести полоску до 100 %. */
  maxHint: string
  tone: ReadinessTone
  /** Подсказка простым языком (наведение на полоску). */
  userHint: string
  /** Идёт загрузка Qwen / рост ОЗУ — анимация полоски. */
  loading?: boolean
  indeterminate?: boolean
  /** Короткая строка под полоской (процессы). */
  subline?: string
  /** ОЗУ: полоска = факт нагрузки, не «цель 100%». */
  ramMeter?: boolean
}

export const READINESS_SCALES: Record<string, { userHint: string }> = {
  combat: { userHint: 'Сервер + Qwen/DeepSeek + Chromium + Google Chrome (Windows).' },
  code: { userHint: 'Режим чата и ядро.' },
  images: { userHint: 'Ideogram / Nano Banana / OpenAI / xAI — медиа-роутер Jarvis.' },
  voice: { userHint: 'XTTS, голос, микрофон.' },
  ram: { userHint: 'Факт ОЗУ Jarvis (не цель 100%).' },
}

type ReadinessCore = Omit<ReadinessMetric, 'userHint'>

function stepsToMax(steps: string[]): string {
  if (!steps.length) return '100% — готово.'
  return `До 100%: ${steps.join(' · ')}`
}

function withScale(metric: ReadinessCore): ReadinessMetric {
  const scale = READINESS_SCALES[metric.id]
  return {
    ...metric,
    userHint: scale?.userHint ?? metric.hint,
  }
}

export interface JarvisHealthSnapshot {
  avatarAnim: JarvisAvatarAnim
  /** Сервер есть, но Qwen / DeepSeek ещё не готовы. */
  corePending: boolean
  screenStatus: string
  agent: ReturnType<typeof agentChip>
  combat: ReadinessMetric
  metrics: ReadinessMetric[]
  connectivity: 'offline' | 'online' | 'hybrid' | 'none'
  connectivityLabel: string
}

export function isJarvisCoreReady(agent: AgentState): boolean {
  return coreReady(agent)
}

function clampPct(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)))
}

function qwenReady(agent: AgentState): boolean {
  const q = qwenResponseModelChip(agent)
  return q.variant === 'success' || q.variant === 'default'
}

function deepseekReady(agent: AgentState): boolean {
  const d = deepseekCloudChip(agent)
  return d.variant === 'success' || d.variant === 'default'
}

function coreReady(agent: AgentState): boolean {
  if (agent.backendStatus !== 'connected') return false
  if (agent.neuralReady) return true
  if (agent.qwen.ready && !agent.qwen.ramEnabled) return true
  const qwenOn = agent.qwen.ramEnabled
  return (qwenOn && qwenReady(agent)) || deepseekReady(agent)
}

function chromiumReady(agent: AgentState): boolean {
  const ch = agent.chromiumBrowser.ready
  const gc = agent.googleChrome
  if (gc.requiredOnWindows && !gc.ready) return false
  return ch
}

function statusToAnim(agent: AgentState): JarvisAvatarAnim {
  return resolveJarvisAvatarAnim(agent)
}

function statusScreenLabel(status: AgentStatus, agent: AgentState): string {
  if (isJarvisOffended(agent)) return 'Обида'
  if (agent.backendStatus === 'connecting') return 'Связь…'
  if (agent.backendStatus !== 'connected') return 'Нет связи'
  if (agent.voiceListening && status === 'IDLE') return 'Слушает'
  switch (status) {
    case 'Listening...':
      return 'Слушает'
    case 'Thinking...':
      return 'Думает'
    case 'Searching Web...':
      return 'Поиск'
    case 'Generating image...':
      return 'Картинка'
    default:
      return coreReady(agent) ? 'На связи' : 'Ядро…'
  }
}

function applyOffendedMetric(
  agent: AgentState,
  metric: ReadinessCore,
  labelWhenOffended?: string,
): ReadinessCore {
  if (!isJarvisOffended(agent)) return metric
  const mins = insultOffendedRemainingMin(agent)
  return {
    ...metric,
    percent: 12,
    hint: labelWhenOffended ?? 'Jarvis обиделся.',
    maxHint: `Обида ~${mins} мин · извинитесь или подождите.`,
    tone: 'error',
    loading: false,
    indeterminate: false,
  }
}

function computeCombat(agent: AgentState): ReadinessCore {
  const ag = agentChip(agent.status, agent.backendStatus)

  if (isJarvisOffended(agent)) {
    return applyOffendedMetric(agent, {
      id: 'combat',
      label: 'Боеготовность',
      percent: 12,
      hint: 'Обида — показатели прикрыты.',
      maxHint: `До снятия обиды ~${insultOffendedRemainingMin(agent)} мин.`,
      tone: 'error',
    })
  }

  if (agent.backendStatus === 'connecting') {
    return {
      id: 'combat',
      label: 'Боеготовность',
      percent: 10,
      hint: 'Проверка сервера.',
      maxHint: stepsToMax(['Дождитесь связи']),
      tone: 'warn',
    }
  }

  if (agent.backendStatus !== 'connected') {
    return {
      id: 'combat',
      label: 'Боеготовность',
      percent: 0,
      hint: 'Сервер выключен.',
      maxHint: stepsToMax(['start.bat', 'Qwen в ОЗУ или DeepSeek']),
      tone: 'error',
    }
  }

  const q = agent.qwen
  const qChip = qwenResponseModelChip(agent)
  const core = coreReady(agent)
  const ch = agent.chromiumBrowser
  const chOk = chromiumReady(agent)
  const chBusy = ch.installInProgress

  if (!core) {
    let percent = 28
    if (isQwenDownloading(q)) {
      percent = clampPct(18 + qwenDownloadPercent(q) * 0.55)
    } else if (q.ramPhase === 'loading') {
      percent = clampPct(40 + (q.ramProgress || 0) * 0.35)
    } else if (q.ramEnabled && !q.ready) {
      percent = 38
    }
    const todo = [
      !agent.qwen.ramEnabled && !agent.deepseekConfigured
        ? 'Qwen в ОЗУ или DeepSeek'
        : null,
      agent.qwen.ramEnabled && !q.ready ? 'Дождитесь Qwen' : null,
      agent.deepseekConfigured && !deepseekReady(agent)
        ? 'Включите DeepSeek'
        : null,
      !chOk && !chBusy ? 'Chromium «На связи»' : null,
      agent.googleChrome.requiredOnWindows &&
      !agent.googleChrome.ready &&
      !agent.googleChrome.installInProgress
        ? 'Google Chrome (окна)'
        : null,
    ].filter(Boolean) as string[]

    return {
      id: 'combat',
      label: 'Боеготовность',
      percent: clampPct(Math.round(percent / 10) * 10),
      hint: qChip.hint || 'Ядро или Chromium не готовы.',
      maxHint: stepsToMax(todo),
      tone: 'warn',
    }
  }

  if (!chOk) {
    const chPct = chBusy
      ? clampPct(62 + chromiumInstallPercent(ch) * 0.28)
      : 58
    const gc = agent.googleChrome
    const chTodo = chBusy || gc.installInProgress
      ? [
          chBusy ? 'Дождитесь Chromium' : null,
          gc.installInProgress ? 'Установка Chrome' : null,
        ].filter(Boolean) as string[]
      : gc.requiredOnWindows && !gc.ready
        ? ['install-google-chrome.bat']
        : ch.installPhase === 'no_internet' && ch.systemInternetOk === false
          ? ['Проверьте интернет Windows']
          : ch.installPhase === 'no_internet'
            ? ['Дождитесь Chromium']
            : ['Перезапустите Jarvis']
    return {
      id: 'combat',
      label: 'Боеготовность',
      percent: clampPct(Math.round(chPct / 10) * 10),
      hint: ch.installMessage || ch.detail || 'Нужен Chromium.',
      maxHint: stepsToMax(chTodo),
      tone: 'warn',
      loading: chBusy,
      indeterminate: chBusy && chromiumInstallPercent(ch) <= 0,
    }
  }

  const busy = agent.status !== 'IDLE'
  return {
    id: 'combat',
    label: 'Боеготовность',
    percent: busy ? 100 : 95,
    hint: busy ? ag.hint : 'Ядро и Chromium готовы.',
    maxHint: busy ? '100% — задача.' : '100% — пишите в чат.',
    tone: busy ? 'active' : 'ok',
  }
}

function computeCode(agent: AgentState): ReadinessCore {
  const mode = agent.mode
  const core = coreReady(agent)
  const backend = agent.backendStatus === 'connected'

  if (isJarvisOffended(agent)) {
    return applyOffendedMetric(agent, {
      id: 'code',
      label: mode === 'standard' ? 'Чат' : 'Режим',
      percent: 10,
      hint: 'Настроение…',
      maxHint: 'Jarvis не показывает готовность.',
      tone: 'error',
    })
  }

  if (!backend) {
    return {
      id: 'code',
      label: 'Код',
      percent: 0,
      hint: 'Диалог недоступен — сначала запустите сервер.',
      maxHint: stepsToMax(['Запустите сервер Jarvis', 'Дождитесь готовности ядра']),
      tone: 'muted',
    }
  }

  if (mode !== 'developer') {
    const pct = core ? (mode === 'standard' ? 90 : 70) : 20
    return {
      id: 'code',
      label: mode === 'standard' ? 'Чат' : 'Режим',
      percent: pct,
      hint: `Режим «${MODE_LABELS[mode]}» — ядро ${core ? 'готово' : 'не готово'}.`,
      maxHint: core
        ? 'Для 100% в этом режиме достаточно ядра — уже почти максимум.'
        : stepsToMax(['Подготовьте ядро: Qwen в ОЗУ или DeepSeek']),
      tone: core ? 'ok' : 'warn',
    }
  }

  if (qwenReady(agent)) {
    return {
      id: 'code',
      label: 'Код',
      percent: 100,
      hint: 'Локальная Qwen — можно писать код без интернета.',
      maxHint: 'Максимум: локальная модель для разработки готова.',
      tone: 'ok',
    }
  }
  if (deepseekReady(agent)) {
    return {
      id: 'code',
      label: 'Код',
      percent: 90,
      hint: 'Облачный DeepSeek — диалог и код через интернет.',
      maxHint: 'Для 100% можно дополнительно включить Qwen в ОЗУ (офлайн).',
      tone: 'ok',
    }
  }
  if (agent.perplexityUsable) {
    return {
      id: 'code',
      label: 'Код',
      percent: 70,
      hint: 'Доступен веб-поиск Perplexity (режим разработчика).',
      maxHint: stepsToMax([
        'Добавьте ключ DeepSeek для полноценного кода',
        'Или включите Qwen в ОЗУ',
      ]),
      tone: 'warn',
    }
  }
  return {
    id: 'code',
    label: 'Код',
    percent: 10,
    hint: 'Нет модели для режима разработчика.',
      maxHint: stepsToMax([
        'Включите Qwen в Настройках → Ядро',
        'Или ключ DeepSeek / Perplexity',
      ]),
    tone: 'warn',
  }
}

function computeImages(agent: AgentState): ReadinessCore {
  if (isJarvisOffended(agent)) {
    return applyOffendedMetric(agent, {
      id: 'images',
      label: 'Изображения',
      percent: 10,
      hint: 'Не в настроении.',
      maxHint: 'Jarvis обиделся.',
      tone: 'error',
    })
  }

  const backend = agent.backendStatus === 'connected'
  if (!backend) {
    return {
      id: 'images',
      label: 'Изображения',
      percent: 0,
      hint: 'Картинки — после запуска сервера Jarvis.',
      maxHint: stepsToMax([
        'Запустите сервер',
        'Ideogram / Nano Banana / OpenAI / xAI в ⚙️ Настройках',
      ]),
      tone: 'muted',
    }
  }

  if (agent.status === 'Generating image...' || agent.status === 'Generating video...') {
    return {
      id: 'images',
      label: 'Изображения',
      percent: 100,
      hint:
        agent.status === 'Generating video...'
          ? 'Сейчас генерируется видео (медиа-роутер).'
          : 'Сейчас рисуется картинка (медиа-роутер).',
      maxHint: 'Максимум — идёт генерация медиа.',
      tone: 'active',
    }
  }

  if (agent.mediaImageReady || agent.mediaVideoReady) {
    const parts: string[] = []
    if (agent.mediaImageReady) parts.push('картинки')
    if (agent.mediaVideoReady) parts.push('видео')
    return {
      id: 'images',
      label: 'Изображения',
      percent: 100,
      hint: `Медиа-роутер: ${parts.join(' и ')} (Ideogram, Nano Banana, OpenAI, xAI).`,
      maxHint: 'Максимум — хотя бы один медиа-провайдер активен.',
      tone: 'ok',
    }
  }

  const hasAnyKey =
    agent.ideogramConfigured ||
    agent.nanobananaConfigured ||
    agent.openaiConfigured ||
    agent.xaiConfigured
  if (hasAnyKey) {
    return {
      id: 'images',
      label: 'Изображения',
      percent: 35,
      hint: 'Ключи есть — включите медиа-сервис тумблером в ⚙️ Настройках.',
      maxHint: stepsToMax(['Включите Ideogram / Nano Banana / OpenAI / xAI в Настройках']),
      tone: 'warn',
    }
  }

  return {
    id: 'images',
    label: 'Изображения',
    percent: 10,
    hint: 'Добавьте Ideogram, Nano Banana, OpenAI или xAI в ⚙️ Настройках.',
    maxHint: stepsToMax(['Ideogram (ideogram.ai) или другой медиа-провайдер']),
    tone: 'warn',
  }
}

function xttsEngineReady(agent: AgentState): boolean {
  const x = agent.xtts
  return Boolean(x.importable || x.status === 'ready' || x.modelWeightsPresent)
}

function computeVoice(agent: AgentState): ReadinessCore {
  const label = 'Доступность голоса Джарвис'

  if (isJarvisOffended(agent)) {
    return applyOffendedMetric(agent, {
      id: 'voice',
      label,
      percent: 10,
      hint: 'Голос «замолчал» из обиды.',
      maxHint: 'Подождите или извинитесь.',
      tone: 'error',
    })
  }

  if (agent.backendStatus !== 'connected') {
    return {
      id: 'voice',
      label,
      percent: 0,
      hint: 'Голос недоступен — сервер не запущен.',
      maxHint: stepsToMax(['Запустите start.bat или restart.bat']),
      tone: 'error',
    }
  }

  if (agent.xtts.pythonOkForXtts === false) {
    return {
      id: 'voice',
      label,
      percent: 10,
      hint: 'Для озвучки нужен подходящий Python.',
      maxHint: stepsToMax([
        'Установите Python 3.10 или 3.11',
        'Скачайте XTTS в Настройках → Голос',
      ]),
      tone: 'warn',
    }
  }

  const x = agent.xtts
  if (x.status === 'installing_deps' || x.status === 'downloading_model') {
    const pct = clampPct(20 + Math.round((x.progress || 0) * 0.2))
    return {
      id: 'voice',
      label,
      percent: pct,
      hint: x.message || 'Установка голосового движка XTTS…',
      maxHint: 'Дождитесь окончания загрузки XTTS (Настройки → Голос → скачать).',
      tone: 'warn',
    }
  }

  const todo: string[] = []
  let percent = 20

  if (!xttsEngineReady(agent)) {
    todo.push('Скачайте и установите XTTS (Настройки → Голос)')
  } else {
    percent = 40
  }

  if (!agent.voiceBase.exists) {
    todo.push('Загрузите образец голоса (база для клонирования)')
  } else {
    percent = Math.max(percent, 50)
  }

  if (!agent.voiceEnabled) {
    todo.push('Включите «Голос (Джарвис)» у поля ввода')
  } else {
    percent = Math.max(percent, 70)
  }

  if (!agent.chatSpeechEnabled) {
    todo.push('Включите озвучку ответов Jarvis')
  } else {
    percent = Math.max(percent, 80)
  }

  if (agent.voiceListening || agent.status === 'Listening...') {
    return {
      id: 'voice',
      label,
      percent: 100,
      hint: 'Микрофон активен — Jarvis слушает команды.',
      maxHint: 'Максимум — wake-word и озвучка работают.',
      tone: 'active',
    }
  }

  if (!todo.length && percent >= 80) {
    return {
      id: 'voice',
      label,
      percent: 90,
      hint: 'Голос настроен — можно вызвать «Джарвис».',
      maxHint: 'Для 100% скажите «Джарвис» или нажмите кнопку микрофона в чате.',
      tone: 'ok',
    }
  }

  return {
    id: 'voice',
    label,
    percent: clampPct(Math.round(percent / 10) * 10),
    hint: todo.length ? 'Голос ещё настраивается.' : 'Почти готово.',
    maxHint: stepsToMax(todo),
    tone: todo.length ? 'warn' : 'ok',
  }
}

function isQwenRamLoading(agent: AgentState): boolean {
  const r = agent.ramUsage
  if (r.qwenRamLoading) return true
  const q = agent.qwen
  if (!q.ramEnabled) return false
  return (
    q.ramPhase === 'loading' ||
    q.ramPhase === 'pending' ||
    q.status === 'loading_ram' ||
    q.status === 'pending_ram'
  )
}

function formatRamProcesses(agent: AgentState): string {
  const list = agent.ramUsage.processes
  if (!list?.length) return ''
  return list
    .slice(0, 4)
    .map((p) => `${p.role} ${p.rssMb} МБ`)
    .join(' · ')
}

function computeRamLoad(agent: AgentState): ReadinessMetric {
  const label = 'ОЗУ Jarvis'
  const r = agent.ramUsage
  const ramLoading = isQwenRamLoading(agent)

  if (agent.backendStatus !== 'connected') {
    return withScale({
      id: 'ram',
      label,
      percent: 0,
      hint: '—',
      maxHint: 'Запустите start.bat — появятся МБ.',
      tone: 'muted',
      ramMeter: true,
    })
  }

  if (r.launching || !r.servicesActive) {
    return withScale({
      id: 'ram',
      label,
      percent: 0,
      hint: 'Старт…',
      maxHint: 'Скоро: МБ процессов Jarvis.',
      tone: 'muted',
      ramMeter: true,
    })
  }

  const pct = clampPct(r.jarvisPercentOfTotal)
  const fill = Math.max(ramLoading ? 4 : 2, pct)

  let tone: ReadinessTone = 'ok'
  if (ramLoading) tone = 'active'
  else if (pct >= 75) tone = 'warn'
  else if (pct >= 90) tone = 'error'

  const procLine = formatRamProcesses(agent)
  const hintShort = ramLoading
    ? `Загрузка Qwen · ${r.jarvisRssMb} МБ`
    : `${r.jarvisRssMb} МБ · ${pct}% RAM ПК`

  return {
    ...withScale({
      id: 'ram',
      label: ramLoading ? 'ОЗУ (загрузка)' : label,
      percent: fill,
      hint: hintShort,
      maxHint: `Факт: ${r.jarvisRssMb} МБ Jarvis, ${pct}% RAM ПК. Не цель 100%.`,
      tone,
    }),
    loading: ramLoading,
    indeterminate: ramLoading && r.jarvisRssMb < 50,
    subline: procLine || `${r.processCount} проц.`,
    ramMeter: true,
  }
}

function connectivityFrom(agent: AgentState): {
  connectivity: JarvisHealthSnapshot['connectivity']
  connectivityLabel: string
} {
  if (agent.backendStatus !== 'connected') {
    return { connectivity: 'none', connectivityLabel: 'Сервер недоступен' }
  }
  const offline = agent.qwen.ramEnabled && qwenReady(agent)
  const online = deepseekReady(agent)
  if (offline && online) return { connectivity: 'hybrid', connectivityLabel: 'Офлайн + онлайн' }
  if (offline) return { connectivity: 'offline', connectivityLabel: 'Офлайн · Qwen' }
  if (online) return { connectivity: 'online', connectivityLabel: 'Онлайн · облако' }
  return { connectivity: 'none', connectivityLabel: 'Ядро не готово' }
}

export function buildJarvisHealth(agent: AgentState): JarvisHealthSnapshot {
  const agentChipState = agentChip(agent.status, agent.backendStatus)
  const { connectivity, connectivityLabel } = connectivityFrom(agent)

  const pending =
    agent.backendStatus === 'connected' &&
    (!coreReady(agent) || !chromiumReady(agent))
  const combatCore = computeCombat(agent)

  return {
    avatarAnim: statusToAnim(agent),
    corePending: pending,
    screenStatus: statusScreenLabel(agent.status, agent),
    agent: agentChipState,
    combat: {
      ...withScale(combatCore),
      loading: combatCore.loading,
      indeterminate: combatCore.indeterminate,
    },
    metrics: [
      withScale(computeCode(agent)),
      withScale(computeImages(agent)),
      withScale(computeVoice(agent)),
      computeRamLoad(agent),
    ],
    connectivity,
    connectivityLabel,
  }
}

export const AVATAR_ANIM_CLASS: Record<JarvisAvatarAnim, string> = {
  offline: 'animate-jarvis-offline-avatar opacity-50 saturate-0',
  boot: 'animate-jarvis-loading',
  loading: 'animate-jarvis-loading',
  corePending: 'animate-jarvis-core-pending',
  angry: 'animate-jarvis-angry',
  idle: 'animate-jarvis-idle',
  listen: 'animate-jarvis-listen',
  think: 'animate-jarvis-think',
  search: 'animate-jarvis-search',
  image: 'animate-jarvis-image',
}

export const SCREEN_ANIM_CLASS: Record<JarvisAvatarAnim, string> = {
  offline: 'animate-jarvis-screen-offline jarvis-screen-offline-overlay',
  boot: 'animate-jarvis-screen-loading jarvis-screen-loading-overlay',
  loading: 'animate-jarvis-screen-loading jarvis-screen-loading-overlay',
  corePending: 'animate-jarvis-screen-core-warn jarvis-screen-core-warn-overlay',
  angry: 'animate-jarvis-screen-angry jarvis-screen-angry-overlay',
  idle: 'animate-jarvis-screen-idle jarvis-screen-idle-overlay',
  listen: 'animate-jarvis-screen-listen jarvis-screen-listen-overlay',
  think: 'animate-jarvis-screen-think jarvis-screen-think-overlay',
  search: 'animate-jarvis-screen-search jarvis-screen-search-overlay',
  image: 'animate-jarvis-screen-image jarvis-screen-image-overlay',
}

/** Подсветка строки статуса под заголовком экрана. */
export const STATUS_LINE_CLASS: Record<JarvisAvatarAnim, string> = {
  offline: 'text-red-200/90',
  boot: 'text-cyan-100 animate-pulse',
  loading: 'text-cyan-100 animate-pulse',
  corePending: 'text-amber-100 animate-pulse',
  angry: 'text-red-200 animate-pulse',
  idle: 'text-emerald-50/95',
  listen: 'text-emerald-200 animate-pulse',
  think: 'text-sky-200 animate-pulse',
  search: 'text-blue-200',
  image: 'text-fuchsia-200 animate-pulse',
}
