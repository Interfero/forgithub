import {
  Brain,
  ChevronDown,
  Image,
  MessageCircle,
  Phone,
  Search,
  Send,
  Sparkles,
  Wifi,
  type ReactNode,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  StatusChip,
  StatusLegend,
  agentChip,
  avitoApiChip,
  avitoSyncChip,
  backendChip,
  motherCoreChip,
  mediaGenerationChip,
  openaiKeyChip,
  perplexityKeyChip,
  DeepSeekStatusChip,
  MailAccountStatusChip,
  QwenStatusChip,
  SttGigaamStatusChip,
  TtsSpeechStatusChip,
  sttGigaamChip,
  ttsSpeechChip,
  deepseekCloudChip,
  chatModeChip,
  lastReplySourceChip,
  qwenResponseModelChip,
  telephonyChip,
  tgLogicChip,
  tgTokenChip,
  xaiKeyChip,
} from '@/lib/statusIndicators'
import {
  NeuralSynapseGraph,
  neuralAnchorProps,
  type NeuralLink,
} from '@/components/top-bar/NeuralSynapseGraph'
import { Hint } from '@/components/ui/hint'
import type { AgentMode, AgentState } from '@/types'

const COLLAPSE_STORAGE = 'jarvis-indicator-sections'

type SectionKey = 'api' | 'telegram' | 'avito' | 'ats' | 'mail'

type GroupTone = { active: boolean; warn: boolean }

function groupTone(ok: boolean, warn: boolean): GroupTone {
  return { active: ok || warn, warn: warn && ok }
}

function borderFromTone(tone: GroupTone, bright = false): string {
  if (!tone.active) {
    return 'border-border/45 bg-card/25'
  }
  if (bright) {
    return cn(
      'border-sky-400/80 bg-sky-500/8',
      'shadow-[0_0_24px_rgba(56,189,248,0.5),inset_0_0_28px_rgba(56,189,248,0.12)]',
      'ring-1 ring-sky-400/40',
    )
  }
  if (tone.warn) {
    return 'border-amber-500/55 bg-amber-500/5 shadow-[0_0_12px_rgba(245,158,11,0.28)]'
  }
  return 'border-emerald-500/50 bg-emerald-500/5 shadow-[0_0_10px_rgba(16,185,129,0.22)]'
}

function CoreBlock({
  title,
  subtitle,
  tone,
  jarvisLive,
  children,
}: {
  title: string
  subtitle?: string
  tone: GroupTone
  jarvisLive: boolean
  children: ReactNode
}) {
  return (
    <section
      className={cn(
        'relative h-full min-h-[7.5rem] shrink-0 rounded-lg border p-1.5 transition-[border-color,box-shadow] duration-300',
        borderFromTone(tone, jarvisLive),
      )}
    >
      {jarvisLive && (
        <span
          className="pointer-events-none absolute -inset-px rounded-lg bg-sky-400/10 blur-md"
          aria-hidden
        />
      )}
      <header className="relative mb-1 border-b border-border/35 pb-1">
        <h3 className="text-[11px] font-semibold tracking-tight text-foreground">{title}</h3>
        {subtitle && (
          <p className="mt-0.5 line-clamp-2 text-[9px] leading-snug text-muted-foreground">{subtitle}</p>
        )}
      </header>
      <div className="relative flex flex-wrap gap-1">{children}</div>
    </section>
  )
}

function CollapsibleBlock({
  sectionKey,
  title,
  tone,
  expanded,
  onToggle,
  anchor,
  children,
}: {
  sectionKey: SectionKey
  title: string
  tone: GroupTone
  expanded: boolean
  onToggle: () => void
  anchor?: Parameters<typeof neuralAnchorProps>[0]
  children: ReactNode
}) {
  return (
    <section
      data-indicator-section={sectionKey}
      className={cn(
        'relative rounded-lg border transition-[border-color,box-shadow] duration-300',
        borderFromTone(tone),
      )}
    >
      {anchor && (
        <span
          className="pointer-events-none absolute left-0 top-3 h-px w-px"
          {...neuralAnchorProps(anchor)}
          aria-hidden
        />
      )}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-1 rounded-lg px-1.5 py-1 text-left hover:bg-muted/25"
        aria-expanded={expanded}
      >
        <ChevronDown
          className={cn(
            'mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform',
            !expanded && '-rotate-90',
          )}
        />
        <span className="min-w-0 flex-1 text-[11px] font-semibold text-foreground">{title}</span>
      </button>
      {expanded && (
        <div className="border-t border-border/30 px-1.5 pb-1.5 pt-1">{children}</div>
      )}
    </section>
  )
}

function ConnectionLamp({
  hint,
  active,
  warn,
}: {
  hint: string
  active: boolean
  warn?: boolean
}) {
  return (
    <Hint text={hint}>
      <div className="flex flex-col items-center py-1">
        <span
          className={cn(
            'block h-2.5 w-2.5 rounded-full transition-all duration-300',
            active &&
              !warn &&
              'bg-emerald-400 shadow-[0_0_10px_2px_rgba(52,211,153,0.75)] ring-2 ring-emerald-400/30',
            active &&
              warn &&
              'bg-amber-400 shadow-[0_0_10px_2px_rgba(251,191,36,0.7)] ring-2 ring-amber-400/30',
            !active && 'bg-muted-foreground/25 ring-1 ring-border/60',
          )}
          aria-hidden
        />
      </div>
    </Hint>
  )
}

function ConnectionRailCell({
  lamp,
  showSpineAbove,
}: {
  lamp: { hint: string; active: boolean; warn?: boolean }
  showSpineAbove?: boolean
}) {
  return (
    <div className="relative flex h-full min-h-[28px] items-center justify-center">
      {showSpineAbove && (
        <span
          className={cn(
            'pointer-events-none absolute bottom-[calc(50%+6px)] left-1/2 top-0 w-px -translate-x-1/2',
            lamp.active ? 'bg-emerald-400/60' : 'bg-border/45',
          )}
          aria-hidden
        />
      )}
      <ConnectionLamp hint={lamp.hint} active={lamp.active} warn={lamp.warn} />
    </div>
  )
}

function ApiCategory({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children: ReactNode
}) {
  return (
    <div className="rounded border border-border/35 bg-background/25 p-1">
      <p className="text-[9px] font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <p className="mb-1 text-[8px] leading-snug text-muted-foreground/80">{hint}</p>
      <div className="flex flex-wrap gap-1">{children}</div>
    </div>
  )
}

function AnchoredChip({
  anchor,
  children,
}: {
  anchor: Parameters<typeof neuralAnchorProps>[0]
  children: ReactNode
}) {
  return (
    <div className="relative inline-flex scale-[0.92] origin-top-left" {...neuralAnchorProps(anchor)}>
      {children}
    </div>
  )
}

function loadExpanded(): Record<SectionKey, boolean> {
  const defaults: Record<SectionKey, boolean> = {
    api: false,
    telegram: false,
    avito: false,
    ats: false,
    mail: false,
  }
  try {
    const raw = localStorage.getItem(COLLAPSE_STORAGE)
    if (raw) return { ...defaults, ...JSON.parse(raw) }
  } catch {
    /* ignore */
  }
  return defaults
}

export function AgentStatusIndicators({
  agent,
  mode,
}: {
  agent: AgentState
  mode: AgentMode
}) {
  const [expanded, setExpanded] = useState<Record<SectionKey, boolean>>(loadExpanded)

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_STORAGE, JSON.stringify(expanded))
    } catch {
      /* ignore */
    }
  }, [expanded])

  const toggle = (key: SectionKey) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const backendOk = agent.backendStatus === 'connected'
  const srv = backendChip(agent.backendStatus)
  const qwenMdl = qwenResponseModelChip(agent)
  const lastReply = lastReplySourceChip(agent)
  const chatMode = chatModeChip(agent)
  const ag = agentChip(agent.status, agent.backendStatus)
  const ds = deepseekCloudChip(agent)
  const nb = mediaGenerationChip(agent)
  const pplx = perplexityKeyChip(agent.perplexityConfigured, backendOk)
  const xai = xaiKeyChip(agent.xaiConfigured, backendOk)
  const oai = openaiKeyChip(agent.openaiConfigured, backendOk)
  const avApi = avitoApiChip(agent.avito)
  const avSync = avitoSyncChip(agent.avito)
  const tg = agent.telegram
  const tgTok = tgTokenChip(tg)
  const tgSrv = motherCoreChip(tg)
  const tgLog = tgLogicChip(tg)
  const tel = telephonyChip(agent.telephony, backendOk)

  const qwenEnabled = agent.qwen.ramEnabled
  const qwenReady =
    qwenMdl.variant === 'success' ||
    qwenMdl.variant === 'default' ||
    (qwenMdl.variant === 'warning' && qwenEnabled)
  const deepseekReady = ds.variant === 'success' || ds.variant === 'default'
  const sttChip = sttGigaamChip(agent)
  const ttsChip = ttsSpeechChip(agent)
  const sttOk = sttChip.variant === 'success' || sttChip.variant === 'default'
  const ttsOk = ttsChip.variant === 'success' || ttsChip.variant === 'default'
  const chatLlm =
    agent.chatLlmReady ?? agent.neuralReady ?? agent.qwenReady ?? deepseekReady
  const coreOk =
    backendOk &&
    (chatLlm ||
      (qwenEnabled && qwenReady) ||
      (agent.qwen.ready && !qwenEnabled) ||
      agent.qwen.ollamaModelLoaded)
  const coreWarn = backendOk && !coreOk
  const cloudActive =
    backendOk &&
    (ds.variant === 'success' ||
      pplx.variant === 'success' ||
      nb.variant === 'success' ||
      xai.variant === 'success' ||
      oai.variant === 'success')
  const apiOk = cloudActive
  const apiWarn =
    backendOk && [ds, pplx, nb, xai, oai].some((c) => c.variant === 'warning')
  const tgOk =
    backendOk && tgTok.variant === 'success' && tgSrv.variant === 'success' && tgLog.variant === 'success'
  const tgWarn =
    backendOk &&
    (tgTok.variant === 'warning' || tgSrv.variant === 'warning' || tgLog.variant === 'warning')
  const avOk = backendOk && avApi.variant === 'success'
  const avWarn = backendOk && (avApi.variant === 'warning' || avSync.variant === 'warning')
  const telOk = backendOk && tel.variant === 'success'
  const telWarn = backendOk && (tel.variant === 'warning' || tel.variant === 'default')

  const coreTone = groupTone(coreOk, coreWarn)
  const apiTone = groupTone(apiOk, apiWarn)
  const tgTone = groupTone(tgOk, tgWarn)
  const avTone = groupTone(avOk, avWarn)
  const telTone = groupTone(telOk, telWarn)

  const agentActive = backendOk && ag.variant !== 'muted'
  const qwenActive =
    backendOk &&
    (qwenMdl.variant === 'success' ||
      qwenMdl.variant === 'default' ||
      agent.qwenReady ||
      agent.qwen.ollamaModelLoaded)
  const mailSlots = agent.mail?.slots ?? []
  const mailOk =
    backendOk && mailSlots.some((s) => s.enabled && s.configured && s.status === 'ok')
  const mailWarn =
    backendOk &&
    mailSlots.some(
      (s) => s.enabled && s.configured && s.status !== 'ok' && s.status !== 'off',
    )
  const mailTone = groupTone(mailOk, mailWarn)
  const jarvisLive =
    backendOk && agentActive && (ag.variant === 'success' || ag.variant === 'default')

  const neuralLinks: NeuralLink[] = [
    { from: 'server', to: 'qwen', kind: 'core', active: backendOk },
    { from: 'qwen', to: 'stt', kind: 'core', active: qwenActive && sttOk },
    { from: 'stt', to: 'tts', kind: 'core', active: sttOk && ttsOk },
    {
      from: 'tts',
      to: 'agent',
      kind: 'core',
      active: ttsOk && agentActive,
    },
    {
      from: 'qwen',
      to: 'agent',
      kind: 'core',
      active: qwenActive && agentActive,
    },
    {
      from: 'api-cloud',
      to: 'agent',
      kind: 'cloud',
      active: cloudActive && agentActive,
      warn: apiWarn,
    },
    { from: 'agent', to: 'telegram', kind: 'connector', active: tgTone.active && agentActive, warn: tgTone.warn },
    { from: 'agent', to: 'avito', kind: 'connector', active: avTone.active && agentActive, warn: avTone.warn },
    { from: 'agent', to: 'ats', kind: 'connector', active: telTone.active && agentActive, warn: telTone.warn },
    { from: 'agent', to: 'mail', kind: 'connector', active: mailTone.active && agentActive, warn: mailTone.warn },
  ]

  const connectionLamps = [
    {
      hint: cloudActive
        ? apiWarn
          ? 'Облако API → агент: есть ключи, проверьте предупреждения'
          : 'Облако API → агент: связь активна'
        : 'Облако API → агент: нет активных ключей',
      active: cloudActive && agentActive,
      warn: apiWarn,
    },
    {
      hint: tgTone.active
        ? tgTone.warn
          ? 'Агент → Telegram: частично, см. чипы'
          : 'Агент → Telegram: канал активен'
        : 'Агент → Telegram: не подключено',
      active: tgTone.active && agentActive,
      warn: tgTone.warn,
    },
    {
      hint: avTone.active
        ? avTone.warn
          ? 'Агент → Авито: ключи есть, синхронизация требует внимания'
          : 'Агент → Авито: связь активна'
        : 'Агент → Авито: нет ключей',
      active: avTone.active && agentActive,
      warn: avTone.warn,
    },
    {
      hint: telTone.active
        ? telTone.warn
          ? 'Агент → АТС: настроено частично'
          : 'Агент → АТС: телефония активна'
        : 'Агент → АТС: выключено',
      active: telTone.active && agentActive,
      warn: telTone.warn,
    },
    {
      hint: mailTone.active
        ? mailTone.warn
          ? 'Агент → Почта: ящики требуют проверки IMAP'
          : 'Агент → Почта: IMAP подключён'
        : 'Агент → Почта: ящики не настроены',
      active: mailTone.active && agentActive,
      warn: mailTone.warn,
    },
  ]

  return (
    <div className="relative w-full">
      <NeuralSynapseGraph links={neuralLinks} />

      <div
        className={cn(
          'relative z-10 w-full overflow-hidden rounded-lg border-2 border-sky-400/70',
          'bg-card/35 shadow-[0_0_18px_rgba(56,189,248,0.22)]',
        )}
      >
        <div
          className="grid gap-x-3 gap-y-1.5 p-1.5 pl-0 pr-1.5 pt-1.5"
          style={{
            gridTemplateColumns:
              'minmax(7.5rem, auto) minmax(180px, 28%) 2.5rem minmax(0, 1fr)',
            gridTemplateRows: 'repeat(5, minmax(28px, auto))',
          }}
        >
          <div
            className="flex min-h-0 items-stretch self-stretch"
            style={{ gridColumn: 1, gridRow: '1 / span 5' }}
          >
            <StatusLegend embedded className="w-full max-w-[10.5rem]" />
          </div>

          <div className="min-h-0" style={{ gridColumn: 2, gridRow: '1 / span 5' }}>
            <CoreBlock
              title="Ядро Jarvis"
              subtitle="Сервер · Qwen · STT (речь→текст) · TTS (текст→голос) · DeepSeek · ответ"
              tone={coreTone}
              jarvisLive={jarvisLive}
            >
              <AnchoredChip anchor="server">
                <StatusChip
                  label="Режим чата"
                  purpose="Как Jarvis отвечает сейчас"
                  hint={chatMode.hint}
                  value={chatMode.value}
                  variant={chatMode.variant}
                  icon={chatMode.icon}
                />
              </AnchoredChip>
              <AnchoredChip anchor="server">
                <StatusChip
                  label="Сервер"
                  purpose="Backend Jarvis на вашем ПК"
                  hint={srv.hint}
                  value={srv.value}
                  variant={srv.variant}
                  icon={srv.icon ?? <Wifi className="h-4 w-4" />}
                />
              </AnchoredChip>
              <AnchoredChip anchor="qwen">
                <QwenStatusChip agent={agent} />
              </AnchoredChip>
              <AnchoredChip anchor="stt">
                <SttGigaamStatusChip agent={agent} />
              </AnchoredChip>
              <AnchoredChip anchor="tts">
                <TtsSpeechStatusChip agent={agent} />
              </AnchoredChip>
              <DeepSeekStatusChip agent={agent} />
              <AnchoredChip anchor="agent">
                <StatusChip
                  label="Последний ответ"
                  purpose="Откуда пришёл текст (Qwen / DeepSeek / …)"
                  hint={lastReply.hint}
                  value={lastReply.value}
                  variant={lastReply.variant}
                  icon={lastReply.icon}
                />
              </AnchoredChip>
            </CoreBlock>
          </div>

          <div style={{ gridColumn: 3, gridRow: 1 }}>
            <ConnectionRailCell lamp={connectionLamps[0]} />
          </div>
          <div style={{ gridColumn: 4, gridRow: 1 }}>
            <CollapsibleBlock
              sectionKey="api"
              title="API-ключи"
              tone={apiTone}
              expanded={expanded.api}
              onToggle={() => toggle('api')}
              anchor="api-cloud"
            >
              <div className="mb-1 flex justify-end">
                <span className="inline-flex items-center gap-0.5 rounded-full border border-violet-500/25 bg-violet-500/10 px-1.5 py-0.5 text-[8px] text-violet-200/90">
                  <Sparkles className="h-2.5 w-2.5" />
                  облако
                </span>
              </div>
              <div className="grid gap-1 sm:grid-cols-3">
                <ApiCategory title="Разговор" hint="Диалог, бухгалтерия.">
                  <StatusChip
                    label="DeepSeek"
                    hint={ds.hint}
                    value={ds.value}
                    variant={ds.variant}
                    icon={ds.icon ?? <Brain className="h-4 w-4" />}
                  />
                  <StatusChip
                    label="Grok"
                    hint={xai.hint}
                    value={xai.value}
                    variant={xai.variant}
                    icon={<MessageCircle className="h-4 w-4" />}
                  />
                  <StatusChip
                    label="ChatGPT"
                    hint={oai.hint}
                    value={oai.value}
                    variant={oai.variant}
                    icon={<Brain className="h-4 w-4" />}
                  />
                </ApiCategory>
                <ApiCategory title="Код" hint="Perplexity + DeepSeek.">
                  <StatusChip
                    label="Perplexity"
                    hint={pplx.hint}
                    value={pplx.value}
                    variant={pplx.variant}
                    icon={<Search className="h-4 w-4" />}
                  />
                </ApiCategory>
                <ApiCategory title="Картинки" hint="Ideogram, Nano Banana, OpenAI, xAI.">
                  <StatusChip
                    label="Медиа (картинки/видео)"
                    hint={nb.hint}
                    value={nb.value}
                    variant={nb.variant}
                    icon={nb.icon ?? <Image className="h-4 w-4" />}
                  />
                </ApiCategory>
              </div>
            </CollapsibleBlock>
          </div>

          <div style={{ gridColumn: 3, gridRow: 2 }}>
            <ConnectionRailCell lamp={connectionLamps[1]} showSpineAbove />
          </div>
          <div style={{ gridColumn: 4, gridRow: 2 }}>
            <CollapsibleBlock
              sectionKey="telegram"
              title="Telegram"
              tone={tgTone}
              expanded={expanded.telegram}
              onToggle={() => toggle('telegram')}
              anchor="telegram"
            >
              <div className="flex flex-wrap gap-1">
                <StatusChip
                  label="Токен"
                  hint={tgTok.hint}
                  value={tgTok.value}
                  variant={tgTok.variant}
                  icon={tgTok.icon}
                />
                <StatusChip
                  label="Сервер"
                  hint={tgSrv.hint}
                  value={tgSrv.value}
                  variant={tgSrv.variant}
                  icon={tgSrv.icon}
                />
                <StatusChip
                  label="JSON"
                  hint={tgLog.hint}
                  value={tgLog.value}
                  variant={tgLog.variant}
                  icon={<Send className="h-4 w-4" />}
                />
              </div>
            </CollapsibleBlock>
          </div>

          <div style={{ gridColumn: 3, gridRow: 3 }}>
            <ConnectionRailCell lamp={connectionLamps[2]} showSpineAbove />
          </div>
          <div style={{ gridColumn: 4, gridRow: 3 }}>
            <CollapsibleBlock
              sectionKey="avito"
              title="Авито"
              tone={avTone}
              expanded={expanded.avito}
              onToggle={() => toggle('avito')}
              anchor="avito"
            >
              <div className="flex flex-wrap gap-1">
                <StatusChip
                  label="Ключи"
                  hint={avApi.hint}
                  value={avApi.value}
                  variant={avApi.variant}
                  icon={avApi.icon}
                />
                <StatusChip
                  label="Синхр."
                  hint={avSync.hint}
                  value={avSync.value}
                  variant={avSync.variant}
                  icon={avSync.icon}
                />
              </div>
            </CollapsibleBlock>
          </div>

          <div style={{ gridColumn: 3, gridRow: 4 }}>
            <ConnectionRailCell lamp={connectionLamps[3]} showSpineAbove />
          </div>
          <div style={{ gridColumn: 4, gridRow: 4 }}>
            <CollapsibleBlock
              sectionKey="ats"
              title="Jarvis-ATS"
              tone={telTone}
              expanded={expanded.ats}
              onToggle={() => toggle('ats')}
              anchor="ats"
            >
              <StatusChip
                label="Звонки"
                hint={tel.hint}
                value={tel.value}
                variant={tel.variant}
                icon={tel.icon ?? <Phone className="h-4 w-4" />}
              />
            </CollapsibleBlock>
          </div>

          <div style={{ gridColumn: 3, gridRow: 5 }}>
            <ConnectionRailCell lamp={connectionLamps[4]} showSpineAbove />
          </div>
          <div style={{ gridColumn: 4, gridRow: 5 }}>
            <CollapsibleBlock
              sectionKey="mail"
              title="Почтовый клиент"
              tone={mailTone}
              expanded={expanded.mail}
              onToggle={() => toggle('mail')}
              anchor="mail"
            >
              <div className="flex flex-wrap gap-1">
                {mailSlots.map((slot) => (
                  <MailAccountStatusChip
                    key={slot.slot}
                    slot={slot}
                    backendOk={backendOk}
                    compact
                  />
                ))}
              </div>
            </CollapsibleBlock>
          </div>
        </div>
      </div>
    </div>
  )
}
