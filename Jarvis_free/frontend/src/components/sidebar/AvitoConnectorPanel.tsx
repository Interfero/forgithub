import { useEffect, useState } from 'react'
import { JARVIS_UI_EVENT, type UiCommand } from '@/lib/uiBridge'
import { BarChart3, ChevronDown, ChevronUp } from 'lucide-react'
import { ServiceEnableToggle } from '@/components/ui/ServiceEnableToggle'
import { cn } from '@/lib/utils'
import {
  analyzeAvitoChats,
  probeAvitoApi,
  runAvitoChatPipeline,
  saveAvitoConfig,
  syncAvitoChats,
  syncAvitoNow,
} from '@/api/client'
import type { AvitoConfig, AvitoState } from '@/types'

const PANEL_STORAGE_KEY = 'jarvis-avito-panel-expanded'

const AVITO_COLORS: Record<string, string> = {
  off: 'bg-muted-foreground/40',
  waiting: 'bg-amber-400',
  active: 'bg-emerald-500',
  need_creds: 'bg-orange-500',
  error: 'bg-destructive',
}

interface AvitoConnectorPanelProps {
  avito: AvitoState
  config: AvitoConfig | null
  avitoLoading?: boolean
  embedded?: boolean
  inSettings?: boolean
  onToggle: () => void
  onConfigSaved?: (cfg: AvitoConfig) => void
  onSystemLog?: (text: string) => void
}

export function AvitoConnectorPanel({
  avito,
  config,
  avitoLoading,
  embedded = false,
  inSettings = false,
  onToggle,
  onConfigSaved,
  onSystemLog,
}: AvitoConnectorPanelProps) {
  const [expanded, setExpanded] = useState(() => {
    if (inSettings) return true
    try {
      return localStorage.getItem(PANEL_STORAGE_KEY) !== 'false'
    } catch {
      return false
    }
  })
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [userId, setUserId] = useState('')
  const [saving, setSaving] = useState(false)
  const [syncingStats, setSyncingStats] = useState(false)
  const [syncingChats, setSyncingChats] = useState(false)
  const [probing, setProbing] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [pipelining, setPipelining] = useState(false)

  const hasCreds =
    Boolean(config?.clientIdConfigured ?? avito.clientIdConfigured) &&
    Boolean(config?.clientSecretConfigured ?? avito.clientSecretConfigured)
  const serverOn = avito.status === 'active' && avito.enabled

  useEffect(() => {
    if (inSettings) return
    try {
      localStorage.setItem(PANEL_STORAGE_KEY, String(expanded))
    } catch {
      /* ignore */
    }
  }, [expanded, inSettings])

  useEffect(() => {
    setUserId(config?.userId ?? avito.userId ?? '')
  }, [config?.userId, avito.userId])

  useEffect(() => {
    const norm = (f: string) =>
      f
        .trim()
        .toLowerCase()
        .replace(/\s+/g, '_')
        .replace(/[^a-z0-9_]/g, '')

    const onUi = (e: Event) => {
      const cmd = (e as CustomEvent<UiCommand>).detail
      if (cmd.action === 'expand_panel' && cmd.panel === 'avito') {
        setExpanded(true)
      }
      if (cmd.action === 'set_field' && cmd.target === 'avito') {
        setExpanded(true)
        const f = norm(cmd.field)
        if (f === 'client_id' || f === 'clientid') setClientId(cmd.value)
        else if (f === 'client_secret' || f === 'secret') setClientSecret(cmd.value)
        else if (f === 'user_id' || f === 'userid') setUserId(cmd.value)
      }
      if (
        cmd.action === 'click' &&
        cmd.target === 'avito' &&
        cmd.control === 'sync_toggle'
      ) {
        const wantOn = cmd.on ?? !avito.enabled
        if (wantOn !== avito.enabled && hasCreds) onToggle()
      }
    }
    window.addEventListener(JARVIS_UI_EVENT, onUi)
    return () => window.removeEventListener(JARVIS_UI_EVENT, onUi)
  }, [avito.enabled, hasCreds, onToggle])

  const handleSave = async () => {
    if (!clientId.trim() && !hasCreds) {
      onSystemLog?.('❌ Укажите Client ID из кабинета разработчика Авито')
      return
    }
    if (!clientSecret.trim() && !hasCreds) {
      onSystemLog?.('❌ Укажите Client Secret')
      return
    }
    setSaving(true)
    try {
      const res = await saveAvitoConfig({
        clientId: clientId.trim() || undefined,
        clientSecret: clientSecret.trim() || undefined,
        userId: userId.trim(),
      })
      onConfigSaved?.(res)
      setClientId('')
      setClientSecret('')
      onSystemLog?.(`🟠 ${res.message ?? 'Настройки Авито сохранены'}`)
    } catch (e) {
      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
    } finally {
      setSaving(false)
    }
  }

  const isOpen = inSettings || expanded

  const panelBody = (
    <div className={cn('space-y-3', !inSettings && 'border-t border-border/60 pt-2')}>
          <div
            className={cn(
              'rounded-md border px-2.5 py-2 text-[10px]',
              hasCreds
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
                : 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100',
            )}
          >
            <p className="font-medium">
              {hasCreds ? '✓ Ключи API загружены' : '⚠ Ключи API не загружены'}
            </p>
            <p className="mt-1 opacity-90">
              {hasCreds
                ? 'В панели разработчика индикатор «Авито API» покажет «Загружены». Включите синхронизацию ниже.'
                : 'Получите Client ID и Client Secret в developers.avito.ru → вставьте и «Сохранить ключи».'}
            </p>
          </div>

          <p className="text-[9px] text-muted-foreground">
            OAuth2: статистика объявлений (avito_stats) и архив чатов (avito_chats / avito_messages)
            в accountant.db. Для чатов нужны права messenger:read в developers.avito.ru.
          </p>

          {(avito.chatsInDb ?? 0) > 0 && (
            <p className="text-[10px] text-muted-foreground">
              В архиве: <strong>{avito.chatsInDb}</strong> чатов,{' '}
              <strong>{avito.messagesInDb ?? 0}</strong> сообщений
              {avito.lastChatsSyncAt && (
                <>
                  {' '}
                  · синхр. чатов: {avito.lastChatsSyncAt.slice(0, 19).replace('T', ' ')}
                </>
              )}
            </p>
          )}

          <div>
            <label className="mb-1 block text-[10px] font-medium">Client ID (из developers.avito.ru)</label>
            <input
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder={hasCreds ? 'Новый Client ID для замены' : 'Вставьте Client ID'}
              className="w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-[11px]"
              autoComplete="off"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-medium">Client Secret</label>
            <input
              type="password"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder={hasCreds ? 'Новый Secret для замены' : 'Вставьте Client Secret'}
              className="w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-[11px]"
              autoComplete="off"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-medium">
              User ID (номер профиля Авито, можно пусто — подставится сам)
            </label>
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="123456789"
              className="w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-[11px]"
            />
          </div>

          <button
            type="button"
            disabled={saving}
            onClick={() => void handleSave()}
            className="w-full rounded-md border border-border bg-muted/40 py-1 text-[10px] font-medium hover:bg-muted/70 disabled:opacity-50"
          >
            {saving ? 'Сохранение…' : hasCreds ? 'Обновить ключи' : 'Сохранить ключи'}
          </button>

          {avito.lastSyncDate && (
            <p className="text-[10px] text-muted-foreground">
              Последняя синхронизация: <strong>{avito.lastSyncDate}</strong>
              {avito.itemsSynced > 0 && ` · ${avito.itemsSynced} объявлений`}
            </p>
          )}

          {avito.error && (
            <p className="rounded border border-destructive/30 bg-destructive/5 p-1.5 text-[10px] text-destructive">
              {avito.error}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!hasCreds || syncingStats}
              onClick={() => {
                void (async () => {
                  setSyncingStats(true)
                  try {
                    const res = await syncAvitoNow()
                    onSystemLog?.(
                      res.ok
                        ? `🟠 Статистика: ${res.items ?? 0} объявлений за ${res.date ?? '?'}`
                        : `❌ ${res.error ?? 'ошибка статистики'}`,
                    )
                  } catch (e) {
                    onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
                  } finally {
                    setSyncingStats(false)
                  }
                })()
              }}
              className="flex-1 rounded-md border border-border bg-muted/40 py-1.5 text-[10px] font-medium hover:bg-muted/70 disabled:opacity-50"
            >
              {syncingStats ? 'Статистика…' : 'Синхр. статистику'}
            </button>
            <button
              type="button"
              disabled={!hasCreds || syncingChats}
              onClick={() => {
                void (async () => {
                  setSyncingChats(true)
                  try {
                    const res = await syncAvitoChats(500, 30)
                    onSystemLog?.(
                      res.ok
                        ? `🟠 Чаты: ${res.chats_saved ?? 0} чатов, ${res.messages_saved ?? 0} сообщений`
                        : `❌ ${res.error ?? 'ошибка чатов'}`,
                    )
                  } catch (e) {
                    onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
                  } finally {
                    setSyncingChats(false)
                  }
                })()
              }}
              className="flex-1 rounded-md border border-orange-500/40 bg-orange-500/10 py-1.5 text-[10px] font-medium hover:bg-orange-500/20 disabled:opacity-50"
            >
              {syncingChats ? 'Чаты…' : 'Синхр. чаты'}
            </button>
            <button
              type="button"
              disabled={!hasCreds || pipelining}
              onClick={() => {
                void (async () => {
                  setPipelining(true)
                  try {
                    const res = await runAvitoChatPipeline(30)
                    onSystemLog?.(`🟠 Пайплайн: ${res.report ?? 'готово'}`)
                  } catch (e) {
                    onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
                  } finally {
                    setPipelining(false)
                  }
                })()
              }}
              className="w-full rounded-md border border-orange-500/50 bg-orange-500/15 py-1.5 text-[10px] font-medium hover:bg-orange-500/25 disabled:opacity-50"
            >
              {pipelining ? 'Загрузка+анализ…' : 'Чаты за месяц (загрузка + анализ)'}
            </button>
            <button
              type="button"
              disabled={!hasCreds || analyzing}
              onClick={() => {
                void (async () => {
                  setAnalyzing(true)
                  try {
                    const res = await analyzeAvitoChats(30)
                    onSystemLog?.(`🟠 ${res.report ?? 'Анализ завершён'}`)
                  } catch (e) {
                    onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
                  } finally {
                    setAnalyzing(false)
                  }
                })()
              }}
              className="w-full rounded-md border border-border py-1 text-[9px] hover:bg-muted/30 disabled:opacity-50"
            >
              {analyzing ? 'Анализ…' : 'Только анализ архива'}
            </button>
            <button
              type="button"
              disabled={!hasCreds || probing}
              onClick={() => {
                void (async () => {
                  setProbing(true)
                  try {
                    const p = await probeAvitoApi()
                    const msg = [
                      `Ключи: ${p.credentials ? 'OK' : 'нет'}`,
                      `Профиль: ${p.profile?.ok ? 'OK' : p.profile?.error || 'нет'}`,
                      `Messenger: ${p.messenger_chats?.ok ? 'OK' : p.messenger_chats?.error || 'нет'}`,
                      `Статистика: ${p.stats?.ok ? 'OK' : p.stats?.error || 'нет'}`,
                    ].join(' · ')
                    onSystemLog?.(`🟠 API Авито: ${msg}`)
                  } catch (e) {
                    onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
                  } finally {
                    setProbing(false)
                  }
                })()
              }}
              className="w-full rounded-md border border-border/60 py-1 text-[9px] text-muted-foreground hover:bg-muted/30 disabled:opacity-50"
            >
              {probing ? 'Проверка API…' : 'Проверить права API'}
            </button>
          </div>

          <ServiceEnableToggle
            label="Активная синхронизация Авито"
            description="Раз в сутки + фоновый планировщик. Ключи API не удаляются. Ручные кнопки «Синхр.» работают отдельно."
            enabled={avito.enabled}
            ready={hasCreds}
            busy={avitoLoading}
            onToggle={(next) => {
              if (!hasCreds) {
                onSystemLog?.('❌ Сначала сохраните Client ID и Client Secret')
                return
              }
              if (next !== avito.enabled) onToggle()
            }}
          />
          <p className="text-[9px] text-muted-foreground">{avito.statusLabel}</p>

          {avito.lastEvent && (
            <p className="truncate text-[9px] text-muted-foreground" title={avito.lastEvent}>
              {avito.lastEvent}
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
              serverOn && 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)]',
              !serverOn && (AVITO_COLORS[avito.status] ?? AVITO_COLORS.off),
            )}
          />
          <span className="font-medium text-foreground">{avito.statusLabel}</span>
          <span className="text-muted-foreground">
            {hasCreds ? '· ключи на сервере' : '· нужны Client ID и Secret'}
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
        embedded ? 'border-t border-border/60' : 'rounded-lg border border-border bg-card/50',
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={cn(
          'flex w-full items-center gap-2 text-left hover:bg-muted/40',
          embedded ? 'px-4 py-2.5' : 'px-3 py-2',
        )}
      >
        <BarChart3 className="h-3.5 w-3.5 shrink-0 text-orange-500/90" />
        <span className="text-[11px] font-medium">Коннектор Авито</span>
        {!expanded && (
          <span className="truncate text-[10px] text-muted-foreground">
            {hasCreds ? avito.statusLabel : 'Нужны ключи API'}
          </span>
        )}
        <span
          className={cn(
            'ml-auto h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-background',
            serverOn && 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)]',
            !serverOn && (AVITO_COLORS[avito.status] ?? AVITO_COLORS.off),
          )}
        />
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {isOpen && (
        <div className={cn(embedded ? 'px-4 pb-3' : 'px-3 pb-3')}>{panelBody}</div>
      )}
    </div>
  )
}
