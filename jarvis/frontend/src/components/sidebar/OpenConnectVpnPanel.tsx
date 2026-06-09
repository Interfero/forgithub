import { useCallback, useEffect, useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Loader2,
  Lock,
  LockOpen,
  Shield,
} from 'lucide-react'
import {
  connectOpenConnectVpn,
  disconnectOpenConnectVpn,
  fetchOpenConnectVpnConfig,
  fetchOpenConnectVpnLog,
  fetchOpenConnectVpnStatus,
  saveOpenConnectVpnConfig,
} from '@/api/client'
import { Hint } from '@/components/ui/hint'
import { SidebarModuleSwitch } from '@/components/sidebar/SidebarModuleSwitch'
import { cn } from '@/lib/utils'
import type { OpenConnectVpnConfig, OpenConnectVpnState } from '@/types'

const COLLAPSED_KEY = 'jarvis-openconnect-vpn-collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

const defaultStatus: OpenConnectVpnState = {
  status: 'off',
  statusLabel: 'Выключен',
  message: '',
  error: null,
  server: '',
  managed: false,
  externalGui: false,
  systemVpnActive: false,
  openconnectFound: false,
  ready: false,
  useJarvisPreset: false,
  preset: {
    id: 'jarvis-paris',
    label: 'Сервер Jarvis за границей',
    server: '82.40.49.176',
    port: 443,
    username: 'vpn',
    protocol: 'anyconnect',
    hint: '',
    hasCertPin: true,
  },
}

interface OpenConnectVpnPanelProps {
  onSystemLog?: (text: string) => void
}

export function OpenConnectVpnPanel({ onSystemLog }: OpenConnectVpnPanelProps) {
  const [status, setStatus] = useState<OpenConnectVpnState>(defaultStatus)
  const [config, setConfig] = useState<OpenConnectVpnConfig | null>(null)
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [busy, setBusy] = useState(false)
  const [showLog, setShowLog] = useState(false)
  const [logLines, setLogLines] = useState<string[]>([])
  const [server, setServer] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [usePreset, setUsePreset] = useState(false)

  const switchOn = status.status === 'connected' && status.managed
  const settingUp = status.status === 'connecting'
  const canCollapse = !switchOn && !settingUp
  const expandLabel = collapsed
    ? 'Развернуть блок «OpenConnect VPN»'
    : 'Свернуть блок «OpenConnect VPN»'

  const handleToggleCollapse = () => {
    if (!canCollapse) return
    setCollapsed((v) => !v)
  }

  const refresh = useCallback(async () => {
    try {
      const s = await fetchOpenConnectVpnStatus()
      setStatus(s)
      return s
    } catch {
      return null
    }
  }, [])

  const loadConfig = useCallback(async () => {
    try {
      const c = await fetchOpenConnectVpnConfig()
      setConfig(c)
      setServer(c.server)
      setUsername(c.username)
      setUsePreset(c.useJarvisPreset)
      return c
    } catch {
      return null
    }
  }, [])

  useEffect(() => {
    void refresh()
    void loadConfig()
  }, [refresh, loadConfig])

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [collapsed])

  useEffect(() => {
    if (collapsed || status.status === 'off') return
    const t = window.setInterval(() => void refresh(), 2500)
    return () => window.clearInterval(t)
  }, [collapsed, status.status, refresh])

  useEffect(() => {
    if (!usePreset || !status.preset) return
    setServer(status.preset.server)
    setUsername(status.preset.username)
  }, [usePreset, status.preset])

  const handleSave = async () => {
    setBusy(true)
    try {
      const c = await saveOpenConnectVpnConfig({
        server,
        username,
        password: password || undefined,
        useJarvisPreset: usePreset,
      })
      setConfig(c)
      if (password) setPassword('')
      onSystemLog?.('🔒 Настройки VPN сохранены.')
      void refresh()
    } catch (e) {
      onSystemLog?.(`❌ VPN: ${e instanceof Error ? e.message : 'ошибка'}`)
    } finally {
      setBusy(false)
    }
  }

  const handleConnect = async () => {
    setBusy(true)
    try {
      if (!config?.passwordConfigured && !password.trim()) {
        await saveOpenConnectVpnConfig({
          server,
          username,
          password,
          useJarvisPreset: usePreset,
        })
      } else if (password.trim()) {
        await saveOpenConnectVpnConfig({
          server,
          username,
          password,
          useJarvisPreset: usePreset,
        })
        setPassword('')
      }
      onSystemLog?.('🔒 Подключение OpenConnect…')
      const s = await connectOpenConnectVpn()
      setStatus(s)
      if (s.error) onSystemLog?.(`❌ VPN: ${s.error}`)
      else if (s.status === 'connected') onSystemLog?.('✅ VPN подключён.')
    } catch (e) {
      onSystemLog?.(`❌ VPN: ${e instanceof Error ? e.message : 'ошибка'}`)
      void refresh()
    } finally {
      setBusy(false)
    }
  }

  const handleDisconnect = async () => {
    setBusy(true)
    try {
      const s = await disconnectOpenConnectVpn()
      setStatus(s)
      onSystemLog?.('🔒 VPN отключён.')
    } catch (e) {
      onSystemLog?.(`❌ VPN: ${e instanceof Error ? e.message : 'ошибка'}`)
    } finally {
      setBusy(false)
    }
  }

  const handleToggle = async () => {
    if (switchOn || settingUp) {
      await handleDisconnect()
      return
    }
    await handleConnect()
  }

  const handleToggleLog = async () => {
    const next = !showLog
    setShowLog(next)
    if (next) {
      try {
        const lines = await fetchOpenConnectVpnLog(50)
        setLogLines(lines)
      } catch {
        setLogLines([])
      }
    }
  }

  return (
    <section
      className="rounded-lg border border-border/80 bg-muted/15"
      aria-label="OpenConnect VPN"
    >
      <div
        className={cn(
          'flex items-start justify-between gap-2 border-b border-border/60 px-3 py-2.5',
          switchOn
            ? 'bg-emerald-500/10'
            : settingUp
              ? 'bg-amber-500/8'
              : 'bg-muted/25',
        )}
      >
        <div className="flex min-w-0 flex-1 items-start gap-2">
          {settingUp ? (
            <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-amber-600" />
          ) : switchOn ? (
            <Lock className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          ) : (
            <LockOpen className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          )}
          <div className="min-w-0 flex-1">
            <Hint text="Зелёный тумблер = туннель через Jarvis. OpenConnect — бесплатный клиент для ocserv / Cisco AnyConnect.">
              <p className="text-xs font-semibold leading-tight">OpenConnect VPN</p>
            </Hint>
            <p
              className="mt-0.5 text-[10px] leading-snug text-muted-foreground"
              title={status.message}
            >
              {status.statusLabel}
            </p>
            {status.message && (
              <p className="mt-1 text-[9px] leading-snug text-muted-foreground/90 line-clamp-2">
                {status.message}
              </p>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {canCollapse ? (
            <Hint text={expandLabel}>
              <button
                type="button"
                onClick={handleToggleCollapse}
                aria-expanded={!collapsed}
                aria-label={expandLabel}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border bg-muted/40 text-muted-foreground hover:bg-muted/70"
              >
                {collapsed ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronUp className="h-3.5 w-3.5" />
                )}
              </button>
            </Hint>
          ) : (
            <Hint text="Свернуть можно только когда VPN не подключён через Jarvis (тумблер выкл.).">
              <span
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-transparent opacity-35"
                aria-hidden
              >
                <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
              </span>
            </Hint>
          )}
          <SidebarModuleSwitch
            on={switchOn}
            busy={busy}
            onClick={() => void handleToggle()}
            onClass="bg-emerald-600"
            offClass={settingUp ? 'bg-amber-500/70' : 'bg-muted'}
            ariaOn="Отключить VPN"
            ariaOff={settingUp ? 'Отменить подключение' : 'Подключить VPN'}
          />
        </div>
      </div>

      <div
        className={cn(
          'grid transition-[grid-template-rows] duration-200 ease-out',
          collapsed ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]',
        )}
      >
        <div className="min-h-0 overflow-hidden">
          {status.error && (
            <p className="border-b border-destructive/20 bg-destructive/5 px-3 py-2 text-[10px] leading-snug text-destructive">
              {status.error}
            </p>
          )}

          {!status.openconnectFound && (
            <p className="border-b border-amber-500/25 bg-amber-500/8 px-3 py-2 text-[10px] leading-snug text-amber-900 dark:text-amber-100">
              Установите{' '}
              <a
                href="https://github.com/openconnect/openconnect-gui/releases"
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                OpenConnect GUI
              </a>{' '}
              — Jarvis найдёт openconnect.exe автоматически.
            </p>
          )}

          <div className="space-y-2 px-3 py-2.5">
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Настройки VPN
            </p>

            <div className="min-h-[7.5rem] space-y-1.5 rounded-md border border-dashed border-border/80 bg-background/70 p-2.5">
            <label className="flex cursor-pointer items-start gap-2 rounded-md border border-transparent bg-muted/30 px-2 py-2">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={usePreset}
                onChange={(e) => setUsePreset(e.target.checked)}
              />
              <span className="min-w-0">
                <span className="flex items-center gap-1 text-[11px] font-medium leading-tight">
                  <Shield className="h-3.5 w-3.5 shrink-0 text-primary" />
                  {status.preset?.label ?? 'Базовый сервер Jarvis'}
                </span>
                <span className="mt-0.5 block text-[9px] leading-snug text-muted-foreground">
                  {status.preset?.server}:{status.preset?.port} · логин{' '}
                  <span className="font-mono">{status.preset?.username}</span>. Пароль вводите
                  сами — не хранится в коде.
                </span>
              </span>
            </label>

            <div className="space-y-1.5">
              <label className="block text-[10px] text-muted-foreground">
                Сервер
                <input
                  type="text"
                  value={server}
                  onChange={(e) => setServer(e.target.value)}
                  disabled={usePreset}
                  placeholder="82.40.49.176"
                  className="mt-0.5 w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-[11px] disabled:opacity-60"
                />
              </label>
              <label className="block text-[10px] text-muted-foreground">
                Логин
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={usePreset}
                  placeholder="vpn"
                  className="mt-0.5 w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-[11px] disabled:opacity-60"
                />
              </label>
              <label className="block text-[10px] text-muted-foreground">
                Пароль
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={
                    config?.passwordConfigured ? '•••••• (сохранён)' : 'Введите пароль VPN'
                  }
                  className="mt-0.5 w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-[11px]"
                  autoComplete="off"
                />
              </label>
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleSave()}
                className="w-full rounded-md border border-border bg-background py-1.5 text-[10px] font-medium hover:bg-muted/50 disabled:opacity-50"
              >
                Сохранить настройки
              </button>

              <button
                type="button"
                onClick={() => void handleToggleLog()}
                className="flex w-full items-center justify-center gap-1.5 rounded-md border border-border bg-background py-2 text-[10px] font-medium hover:bg-muted/50"
              >
                <FileText className="h-3.5 w-3.5 shrink-0" />
                {showLog ? 'Скрыть лог' : 'Просмотр лога'}
              </button>
            </div>
            </div>

            {switchOn && (
              <p className="rounded border border-emerald-500/25 bg-emerald-500/8 px-2 py-1.5 text-[9px] text-emerald-800 dark:text-emerald-200">
                ✓ VPN через Jarvis активен. Отключение — тумблером в шапке.
              </p>
            )}

            {status.systemVpnActive && !switchOn && (
              <p className="text-[9px] leading-snug text-muted-foreground">
                На компьютере VPN уже активен (вне Jarvis). Блок Jarvis выключен — это не мешает
                сворачиванию и настройкам здесь.
              </p>
            )}

            {!switchOn && !settingUp && (
              <p className="text-[9px] leading-snug text-muted-foreground">
                Включите VPN тумблером сверху — здесь сервер, логин и пароль.
              </p>
            )}

            {showLog && (
              <pre className="max-h-28 overflow-auto rounded-md border border-border bg-muted/30 p-2 text-[8px] leading-snug text-muted-foreground">
                {logLines.length ? logLines.join('\n') : 'Лог пуст'}
              </pre>
            )}

          </div>
        </div>
      </div>
    </section>
  )
}
