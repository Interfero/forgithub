import { Cloud, Mail, PlugZap } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import {
  fetchMailConfig,
  saveMailConfig,
  testMailAccount,
  type MailAccountConfig,
  type MailSlotMeta,
} from '@/api/client'
import { Button } from '@/components/ui/button'
import { Hint } from '@/components/ui/hint'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

const PROVIDER_ICONS: Record<string, string> = {
  gmail: 'G',
  yandex: 'Я',
  icloud: '',
  mailru: '@',
  legacy: 'IMAP',
}

const LEGACY_PRESETS: Record<string, string> = {
  outlook: 'Outlook',
  rambler: 'Rambler',
}

type AccountForm = MailAccountConfig & { password_configured?: boolean }

function emptySlot(meta: MailSlotMeta, index: number): AccountForm {
  return {
    id: `mail-${meta.provider}`,
    slot: meta.slot,
    provider: meta.provider,
    label: meta.label,
    email: '',
    password: '',
    imap_host: meta.provider === 'legacy' ? '' : '',
    imap_port: 993,
    imap_ssl: true,
    enabled: true,
    preset: meta.preset ?? '',
  }
}

interface SettingsMailSectionProps {
  onSystemLog?: (text: string) => void
  onRefresh?: () => void
}

export function SettingsMailSection({ onSystemLog, onRefresh }: SettingsMailSectionProps) {
  const [accounts, setAccounts] = useState<AccountForm[]>([])
  const [slotMeta, setSlotMeta] = useState<MailSlotMeta[]>([])
  const [saving, setSaving] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)

  const load = useCallback(() => {
    fetchMailConfig()
      .then((cfg) => {
        setSlotMeta(cfg.slots)
        const rows: AccountForm[] = []
        for (let i = 0; i < cfg.max_accounts; i++) {
          const meta = cfg.slots[i]
          const a = cfg.accounts[i]
          if (a && meta) {
            rows.push({
              id: a.id ?? `mail-${meta.provider}`,
              slot: a.slot ?? meta.slot,
              provider: a.provider ?? meta.provider,
              label: a.label || meta.label,
              email: a.email,
              password: '',
              imap_host: a.imap_host,
              imap_port: a.imap_port,
              imap_ssl: a.imap_ssl,
              enabled: a.enabled,
              preset: a.preset ?? meta.preset ?? '',
              password_configured: a.password_configured,
            })
          } else if (meta) {
            rows.push(emptySlot(meta, i))
          }
        }
        setAccounts(rows)
      })
      .catch(() => {
        setAccounts([])
        setSlotMeta([])
      })
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const patchAccount = (index: number, patch: Partial<AccountForm>) => {
    setAccounts((prev) => prev.map((a, i) => (i === index ? { ...a, ...patch } : a)))
  }

  const save = async () => {
    setSaving(true)
    try {
      const payload = accounts.map((a) => ({
        id: a.id || undefined,
        slot: a.slot,
        provider: a.provider,
        label: a.label,
        email: a.email.trim(),
        password: a.password,
        imap_host: a.imap_host,
        imap_port: a.imap_port,
        imap_ssl: a.imap_ssl,
        enabled: a.enabled,
        preset: a.preset,
      }))
      await saveMailConfig(payload)
      onSystemLog?.('✅ Почтовые ящики сохранены')
      load()
      onRefresh?.()
    } catch (e) {
      onSystemLog?.(`❌ Почта: ${e instanceof Error ? e.message : 'ошибка сохранения'}`)
    } finally {
      setSaving(false)
    }
  }

  const test = async (index: number) => {
    const a = accounts[index]
    if (!a.email.trim()) {
      onSystemLog?.('⚠️ Укажите email')
      return
    }
    setTestingId(a.id || `idx-${index}`)
    try {
      if (!a.password.trim() && !a.password_configured) {
        onSystemLog?.('⚠️ Укажите пароль (или пароль приложения)')
        return
      }
      await save()
      const id = accounts[index]?.id || a.id
      if (!id) return
      const res = await testMailAccount(id)
      onSystemLog?.(res.ok ? `✅ ${res.message}` : `⚠️ ${res.message}`)
      onRefresh?.()
      load()
    } catch (e) {
      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'проверка не удалась'}`)
    } finally {
      setTestingId(null)
    }
  }

  const providerHint = (provider: string) => {
    const meta = slotMeta.find((s) => s.provider === provider)
    return meta?.hint ?? ''
  }

  const providerLink = (provider: string) => {
    if (provider === 'gmail') {
      return {
        href: 'https://support.google.com/accounts/answer/185833',
        label: 'пароль приложения Google',
      }
    }
    if (provider === 'yandex') {
      return {
        href: 'https://yandex.ru/support/id/authorization/app-passwords.html',
        label: 'пароль приложения Яндекса',
      }
    }
    if (provider === 'icloud') {
      return {
        href: 'https://support.apple.com/ru-ru/102654',
        label: 'пароль для приложений Apple',
      }
    }
    if (provider === 'mailru') {
      return {
        href: 'https://help.mail.ru/mail/security/protection/external',
        label: 'пароль для внешнего клиента',
      }
    }
    return null
  }

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-muted-foreground">
        Четыре слота для <strong className="text-foreground">Google Gmail</strong>,{' '}
        <strong className="text-foreground">Яндекс</strong>,{' '}
        <strong className="text-foreground">Apple iCloud</strong> и{' '}
        <strong className="text-foreground">Mail.ru</strong>. Jarvis читает почту через защищённое
        подключение (как почтовый клиент) — без браузера. Пятый слот —{' '}
        <strong className="text-foreground">legacy IMAP</strong> для редких провайдеров.
      </p>

      {accounts.map((acc, index) => {
        const isLegacy = acc.provider === 'legacy'
        const link = providerLink(acc.provider)
        const hint = providerHint(acc.provider)
        const badge = PROVIDER_ICONS[acc.provider] ?? acc.provider

        return (
          <div
            key={acc.provider || index}
            className="rounded-lg border border-border/60 bg-muted/10 p-3 space-y-2"
          >
            <div className="flex items-center gap-2">
              {acc.provider === 'icloud' ? (
                <Cloud className="h-4 w-4 text-primary" />
              ) : (
                <Mail className="h-4 w-4 text-primary" />
              )}
              <span className="inline-flex h-5 min-w-5 items-center justify-center rounded bg-primary/15 px-1 text-[10px] font-semibold text-primary">
                {badge}
              </span>
              <span className="text-sm font-medium">{acc.label}</span>
              <label className="ml-auto flex items-center gap-1.5 text-[11px]">
                <input
                  type="checkbox"
                  checked={acc.enabled}
                  onChange={(e) => patchAccount(index, { enabled: e.target.checked })}
                />
                Включён
              </label>
            </div>

            {!isLegacy && hint && (
              <p className="text-[10px] leading-relaxed text-muted-foreground">
                {hint}
                {link && (
                  <>
                    {' '}
                    <a
                      href={link.href}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary underline"
                    >
                      {link.label}
                    </a>
                  </>
                )}
                .
              </p>
            )}

            {isLegacy && (
              <p className="text-[10px] leading-relaxed text-muted-foreground">
                Ручной IMAP-сервер для Outlook, Rambler и других провайдеров без отдельного слота.
              </p>
            )}

            <Input
              type="email"
              placeholder="email@example.com"
              value={acc.email}
              onChange={(e) => patchAccount(index, { email: e.target.value })}
              className="h-8 text-xs"
            />
            <Input
              type="password"
              placeholder={
                acc.password_configured
                  ? 'Пароль сохранён — введите новый для смены'
                  : isLegacy
                    ? 'Пароль IMAP'
                    : 'Пароль приложения / внешнего клиента'
              }
              value={acc.password}
              onChange={(e) => patchAccount(index, { password: e.target.value })}
              className="h-8 text-xs"
              autoComplete="off"
            />

            {isLegacy && (
              <>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(LEGACY_PRESETS).map(([p, label]) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => patchAccount(index, { preset: p })}
                      className={cn(
                        'rounded-md border px-2 py-0.5 text-[10px]',
                        acc.preset === p
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border text-muted-foreground hover:bg-muted/40',
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div className="grid gap-2 sm:grid-cols-3">
                  <Input
                    placeholder="imap.server.com"
                    value={acc.imap_host}
                    onChange={(e) => patchAccount(index, { imap_host: e.target.value })}
                    className="h-8 text-xs sm:col-span-2"
                  />
                  <Input
                    type="number"
                    placeholder="993"
                    value={acc.imap_port}
                    onChange={(e) =>
                      patchAccount(index, { imap_port: Number(e.target.value) || 993 })
                    }
                    className="h-8 text-xs"
                  />
                </div>
              </>
            )}

            <div className="flex gap-2">
              <Hint
                text={
                  isLegacy
                    ? 'Проверить вход по IMAP'
                    : `Проверить вход в ${acc.label} — Jarvis сможет читать и помечать письма`
                }
              >
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px] transition-all hover:border-primary/50 hover:bg-primary/5 active:scale-[0.98]"
                  disabled={testingId !== null}
                  onClick={() => void test(index)}
                >
                  <PlugZap className="mr-1 h-3 w-3" />
                  {testingId === (acc.id || `idx-${index}`) ? 'Проверка…' : 'Проверить вход'}
                </Button>
              </Hint>
            </div>
          </div>
        )
      })}

      <Button
        type="button"
        disabled={saving}
        onClick={() => void save()}
        className="w-full transition-all hover:brightness-110 active:scale-[0.99] sm:w-auto"
      >
        {saving ? 'Сохранение…' : 'Сохранить почтовые ящики'}
      </Button>
    </div>
  )
}
