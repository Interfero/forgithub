import { useEffect, useState } from 'react'
import { JARVIS_UI_EVENT, type UiCommand } from '@/lib/uiBridge'
import { ChevronDown, ChevronUp, Send } from 'lucide-react'
import { cn } from '@/lib/utils'
import { motherCoreChip } from '@/lib/statusIndicators'
import {
  fetchTelegramBotLogic,
  fetchTelegramBotLogicExample,
  saveTelegramBotLogic,
  saveTelegramConfig,
} from '@/api/client'
import type { TelegramConfig, TelegramState } from '@/types'

const PANEL_STORAGE_KEY = 'jarvis-tg-core-panel-expanded'

const TG_COLORS: Record<string, string> = {
  off: 'bg-muted-foreground/40',
  waiting: 'bg-amber-400',
  active: 'bg-emerald-500',
  need_token: 'bg-orange-500',
  error: 'bg-destructive',
}

interface TelegramConnectorPanelProps {
  telegram: TelegramState
  config: TelegramConfig | null
  tgLoading?: boolean
  embedded?: boolean
  /** В полноэкранных настройках — без свёрнутой шапки сайдбара */
  inSettings?: boolean
  onToggle: () => void
  onConfigSaved?: (cfg: TelegramConfig) => void
  onSystemLog?: (text: string) => void
}

export function TelegramConnectorPanel({
  telegram,
  config,
  tgLoading,
  embedded = false,
  inSettings = false,
  onToggle,
  onConfigSaved,
  onSystemLog,
}: TelegramConnectorPanelProps) {
  const [expanded, setExpanded] = useState(() => {
    if (inSettings) return true
    try {
      return localStorage.getItem(PANEL_STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })
  const [botToken, setBotToken] = useState('')
  const [telegramProxy, setTelegramProxy] = useState('')
  const [saving, setSaving] = useState(false)
  const [botLogicJson, setBotLogicJson] = useState('')
  const [logicConfigured, setLogicConfigured] = useState(false)

  const hasTokenOnDisk = Boolean(
    config?.botTokenConfigured ?? telegram.botTokenConfigured,
  )
  const mc = motherCoreChip(telegram)
  const serverRunning = telegram.status === 'active' && Boolean(telegram.pollingActive)

  useEffect(() => {
    if (inSettings) return
    try {
      localStorage.setItem(PANEL_STORAGE_KEY, String(expanded))
    } catch {
      /* ignore */
    }
  }, [expanded, inSettings])

  useEffect(() => {
    setTelegramProxy(config?.telegramProxy ?? '')
    setLogicConfigured(
      Boolean(config?.botLogicConfigured ?? telegram.botLogicConfigured),
    )
  }, [
    config?.botTokenConfigured,
    config?.telegramProxy,
    config?.botLogicConfigured,
    telegram.botTokenConfigured,
    telegram.botLogicConfigured,
  ])

  useEffect(() => {
    if (!expanded) return
    fetchTelegramBotLogic()
      .then((r) => {
        setLogicConfigured(r.botLogicConfigured)
        setBotLogicJson(JSON.stringify(r.logic, null, 2))
      })
      .catch(() => {
        void fetchTelegramBotLogicExample().then((ex) =>
          setBotLogicJson(JSON.stringify(ex, null, 2)),
        )
      })
  }, [expanded])

  useEffect(() => {
    if (!saving) return
    const t = window.setTimeout(() => setSaving(false), 12_000)
    return () => window.clearTimeout(t)
  }, [saving])

  useEffect(() => {
    const norm = (f: string) =>
      f
        .trim()
        .toLowerCase()
        .replace(/\s+/g, '_')
        .replace(/[^a-z0-9_]/g, '')

    const onUi = (e: Event) => {
      const cmd = (e as CustomEvent<UiCommand>).detail
      if (cmd.action === 'expand_panel' && cmd.panel === 'telegram') {
        setExpanded(true)
      }
      if (cmd.action === 'set_field' && cmd.target === 'telegram') {
        setExpanded(true)
        const f = norm(cmd.field)
        if (f === 'bot_token' || f === 'token') setBotToken(cmd.value)
        else if (f === 'telegram_proxy' || f === 'proxy') setTelegramProxy(cmd.value)
        else if (f === 'bot_logic' || f === 'logic') setBotLogicJson(cmd.value)
      }
      if (
        cmd.action === 'click' &&
        cmd.target === 'telegram' &&
        cmd.control === 'server_toggle'
      ) {
        const wantOn = cmd.on ?? !telegram.enabled
        if (wantOn !== telegram.enabled && hasTokenOnDisk) onToggle()
      }
    }
    window.addEventListener(JARVIS_UI_EVENT, onUi)
    return () => window.removeEventListener(JARVIS_UI_EVENT, onUi)
  }, [hasTokenOnDisk, onToggle, telegram.enabled])

  const handleSaveToken = async () => {
    const raw = botToken.trim()
    if (!raw || raw.includes('•')) {
      onSystemLog?.('❌ Вставьте полный токен от @BotFather (не маску ••••)')
      return
    }
    if (!/^\d+:[A-Za-z0-9_-]{20,}$/.test(raw)) {
      onSystemLog?.('❌ Формат токена: `123456789:AAH…`')
      return
    }
    setSaving(true)
    try {
      const res = await saveTelegramConfig({
        botToken: raw,
        blocklistIds: config?.blocklistIds ?? telegram.blocklistIds ?? [],
        telegramProxy: telegramProxy.trim(),
      })
      const d = res as TelegramConfig & { save_ok?: boolean; message?: string }
      if (d.save_ok === false) {
        onSystemLog?.(`❌ ${d.message ?? 'Токен не сохранён'}`)
        return
      }
      onConfigSaved?.(res)
      setBotToken('')
      onSystemLog?.(`📱 ${d.message ?? 'Токен сохранён — запускается сервер бота'}`)
    } catch (e) {
      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
    } finally {
      setSaving(false)
    }
  }

  const canStartServer = hasTokenOnDisk
  const isOpen = inSettings || expanded

  const panelBody = (
    <div className={cn('space-y-3', !inSettings && 'border-t border-border/60 pt-2')}>
          <div
            className={cn(
              'rounded-md border px-2.5 py-2 text-[10px]',
              hasTokenOnDisk
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
                : 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100',
            )}
          >
            <p className="font-medium">
              {hasTokenOnDisk ? '✓ Токен загружен на сервер' : '⚠ Токен не загружен'}
            </p>
            <p className="mt-1 opacity-90">
              {hasTokenOnDisk
                ? 'Тот же статус виден в панели разработчика («Токен BotFather → Загружен»). Можно включить сервер бота ниже.'
                : 'Вставьте токен от @BotFather и нажмите «Сохранить токен». Индикатор в панели разработчика покажет «Требуется».'}
            </p>
          </div>

          <p className="text-[9px] leading-relaxed text-muted-foreground">
            Backend для любого Telegram-бота: ваш токен +{' '}
            <code className="rounded bg-muted px-0.5">bot_logic.json</code> → опрос Telegram
            (getUpdates) и ответы по JSON.
          </p>

          <div>
            <label className="mb-1 block text-[10px] font-medium">
              Токен бота (BotFather)
            </label>
            <input
              type="password"
              value={botToken}
              onChange={(e) => setBotToken(e.target.value)}
              placeholder={
                hasTokenOnDisk
                  ? 'Токен уже на диске — вставьте новый, чтобы заменить'
                  : 'Вставьте токен: 123456789:AAH…'
              }
              className="w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-[11px]"
              spellCheck={false}
              autoComplete="off"
            />
            <button
              type="button"
              disabled={saving}
              onClick={() => void handleSaveToken()}
              className="mt-2 w-full rounded-md border border-border bg-muted/40 py-1 text-[10px] font-medium hover:bg-muted/70 disabled:opacity-50"
            >
              {saving ? 'Сохранение…' : hasTokenOnDisk ? 'Заменить токен' : 'Сохранить токен'}
            </button>
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-medium">
              Прокси для Telegram (если без VPN не подключается)
            </label>
            <input
              type="text"
              value={telegramProxy}
              onChange={(e) => setTelegramProxy(e.target.value)}
              placeholder="socks5://127.0.0.1:10808 или direct"
              className="w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-[11px]"
              spellCheck={false}
            />
            <button
              type="button"
              disabled={saving}
              onClick={async () => {
                setSaving(true)
                try {
                  const res = await saveTelegramConfig({
                    blocklistIds: config?.blocklistIds ?? telegram.blocklistIds ?? [],
                    telegramProxy: telegramProxy.trim(),
                  })
                  onConfigSaved?.(res)
                  onSystemLog?.('📱 Настройки прокси сохранены')
                } catch (e) {
                  onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
                } finally {
                  setSaving(false)
                }
              }}
              className="mt-2 w-full rounded-md border border-border bg-muted/40 py-1 text-[10px] font-medium hover:bg-muted/70 disabled:opacity-50"
            >
              Сохранить прокси
            </button>
          </div>

          <div className="rounded-md border border-border/60 bg-muted/20 p-2">
            <label className="mb-1 block text-[10px] font-medium">
              Логика бота (bot_logic.json)
            </label>
            <p className="mb-2 text-[9px] text-muted-foreground">
              Команды, ответы на фразы, fallback на DeepSeek. При первом запуске создаётся
              пример, если файла нет.
            </p>
            <textarea
              value={botLogicJson}
              onChange={(e) => setBotLogicJson(e.target.value)}
              rows={8}
              className="w-full rounded-md border border-input bg-background px-2 py-1 font-mono text-[10px]"
              spellCheck={false}
            />
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={saving}
                onClick={() => {
                  try {
                    const parsed = JSON.parse(botLogicJson) as Record<string, unknown>
                    setSaving(true)
                    void saveTelegramBotLogic(parsed)
                      .then((r) => {
                        setLogicConfigured(true)
                        onSystemLog?.(`📱 ${r.message ?? 'Логика сохранена'}`)
                      })
                      .catch((e) =>
                        onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`),
                      )
                      .finally(() => setSaving(false))
                  } catch {
                    onSystemLog?.('❌ Невалидный JSON')
                  }
                }}
                className="rounded-md border border-border bg-muted/40 px-2 py-1 text-[10px] hover:bg-muted/70"
              >
                Сохранить логику
              </button>
              <button
                type="button"
                onClick={() => {
                  void fetchTelegramBotLogicExample().then((ex) =>
                    setBotLogicJson(JSON.stringify(ex, null, 2)),
                  )
                }}
                className="rounded-md border border-border bg-muted/40 px-2 py-1 text-[10px] hover:bg-muted/70"
              >
                Пример
              </button>
            </div>
            {logicConfigured && (
              <p className="mt-1 text-[9px] text-emerald-600">✓ bot_logic.json на диске</p>
            )}
          </div>

          <div
            className={cn(
              'rounded-md border px-2 py-1.5 text-[10px]',
              serverRunning
                ? 'border-emerald-500/30 bg-emerald-500/5'
                : 'border-border/60 bg-muted/10',
            )}
          >
            <p>
              <strong>Сервер:</strong> {telegram.statusLabel}
              {telegram.botUsername && (
                <span className="text-emerald-600"> @{telegram.botUsername}</span>
              )}
            </p>
            {telegram.pollingActive && (
              <p className="text-muted-foreground">Опрос Telegram активен</p>
            )}
            {(telegram.messagesHandled ?? 0) > 0 && (
              <p className="text-muted-foreground">
                Обработано сообщений: {telegram.messagesHandled}
              </p>
            )}
          </div>

          {telegram.error && (
            <p className="rounded border border-destructive/30 bg-destructive/5 p-1.5 text-[10px] text-destructive">
              {telegram.error}
            </p>
          )}

          <div className="flex items-center justify-between gap-2 rounded-md border border-border/50 bg-background/30 px-2 py-2">
            <div>
              <p className="text-[10px] font-medium">Сервер бота</p>
              <p className="text-[9px] text-muted-foreground">
                {canStartServer
                  ? serverRunning
                    ? 'Работает — индикатор в панели разработчика зелёный'
                    : 'Включите — запустится опрос и bot_logic.json'
                  : 'Сначала сохраните токен'}
              </p>
            </div>
            <button
              type="button"
              disabled={tgLoading || !canStartServer}
              onClick={() => {
                if (!canStartServer) {
                  onSystemLog?.('❌ Сначала сохраните токен бота')
                  return
                }
                onToggle()
              }}
              className={cn(
                'relative h-7 w-12 shrink-0 rounded-full transition-colors',
                telegram.enabled && serverRunning ? 'bg-emerald-600' : telegram.enabled ? 'bg-primary' : 'bg-muted',
                !canStartServer && 'cursor-not-allowed opacity-50',
              )}
              aria-label={
                telegram.enabled ? 'Остановить сервер бота' : 'Запустить сервер бота'
              }
            >
              <span
                className={cn(
                  'absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform',
                  telegram.enabled ? 'left-5' : 'left-0.5',
                )}
              />
            </button>
          </div>

          {telegram.lastEvent && (
            <p className="truncate text-[9px] text-muted-foreground" title={telegram.lastEvent}>
              {telegram.lastEvent}
            </p>
          )}
    </div>
  )

  if (inSettings) {
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span
            className={cn(
              'h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-background',
              serverRunning
                ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)]'
                : TG_COLORS[telegram.status] ?? TG_COLORS.off,
            )}
            title={mc.hint}
          />
          <span className="font-medium text-foreground">{telegram.statusLabel}</span>
          {telegram.botUsername && (
            <span className="text-emerald-600 dark:text-emerald-400">@{telegram.botUsername}</span>
          )}
          <span className="text-muted-foreground">
            {hasTokenOnDisk ? '· токен на сервере' : '· нужен токен BotFather'}
          </span>
        </div>
        {panelBody}
      </div>
    )
  }

  return (
    <div
      className={cn(
        'overflow-hidden',
        embedded
          ? 'border-t border-border/60 bg-sidebar-accent/30'
          : 'rounded-lg border border-border bg-card/50',
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={cn(
          'flex w-full items-center gap-2 text-left hover:bg-muted/40',
          embedded ? 'px-4 py-2.5' : 'px-3 py-2',
        )}
        aria-expanded={expanded}
      >
        <Send className="h-3.5 w-3.5 shrink-0 text-primary/90" />
        <span className="text-[11px] font-medium text-foreground">Коннектор Телеграм</span>
        {!expanded && (
          <span className="truncate text-[10px] text-muted-foreground">
            {hasTokenOnDisk ? mc.value : 'Токен не загружен'}
          </span>
        )}
        <span
          className={cn(
            'ml-auto h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-background',
            serverRunning
              ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)]'
              : TG_COLORS[telegram.status] ?? TG_COLORS.off,
          )}
          title={mc.hint}
        />
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </span>
      </button>

      {isOpen && (
        <div className={cn(embedded ? 'px-4 pb-3' : 'px-3 pb-3')}>{panelBody}</div>
      )}
    </div>
  )
}
