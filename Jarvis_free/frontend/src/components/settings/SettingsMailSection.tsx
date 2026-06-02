import { Mail, PlugZap } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import {
  fetchMailConfig,
  saveMailConfig,
  testMailAccount,
  type MailAccountConfig,
} from '@/api/client'
import { Button } from '@/components/ui/button'
import { Hint } from '@/components/ui/hint'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

const PRESET_LABELS: Record<string, string> = {
  gmail: 'Gmail',
  yandex: 'Яндекс',
  mailru: 'Mail.ru',
  outlook: 'Outlook',
  rambler: 'Rambler',
}

type AccountForm = MailAccountConfig & { password_configured?: boolean }

function emptySlot(i: number): AccountForm {
  return {
    id: '',
    label: `Ящик ${i + 1}`,
    email: '',
    password: '',
    imap_host: '',
    imap_port: 993,
    imap_ssl: true,
    enabled: true,
    preset: '',
  }
}

interface SettingsMailSectionProps {
  onSystemLog?: (text: string) => void
  onRefresh?: () => void
}

export function SettingsMailSection({ onSystemLog, onRefresh }: SettingsMailSectionProps) {
  const [accounts, setAccounts] = useState<AccountForm[]>([emptySlot(0), emptySlot(1), emptySlot(2)])
  const [maxAccounts, setMaxAccounts] = useState(3)
  const [presets, setPresets] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)

  const load = useCallback(() => {
    fetchMailConfig()
      .then((cfg) => {
        setMaxAccounts(cfg.max_accounts)
        setPresets(cfg.presets)
        const rows: AccountForm[] = []
        for (let i = 0; i < cfg.max_accounts; i++) {
          const a = cfg.accounts[i]
          if (a) {
            rows.push({
              id: a.id ?? '',
              label: a.label,
              email: a.email,
              password: '',
              imap_host: a.imap_host,
              imap_port: a.imap_port,
              imap_ssl: a.imap_ssl,
              enabled: a.enabled,
              preset: a.preset ?? '',
              password_configured: a.password_configured,
            })
          } else {
            rows.push(emptySlot(i))
          }
        }
        setAccounts(rows)
      })
      .catch(() => {
        setAccounts([emptySlot(0), emptySlot(1), emptySlot(2)])
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
      const payload = accounts
        .filter((a) => a.email.trim() || a.password.trim() || a.password_configured)
        .map((a) => ({
          id: a.id || undefined,
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
      onSystemLog?.('✅ Почтовые ящики сохранены на сервере')
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
    if (!a.id && !a.email.trim()) {
      onSystemLog?.('⚠️ Сначала сохраните ящик')
      return
    }
    setTestingId(a.id || `idx-${index}`)
    try {
      if (!a.id) {
        await save()
      }
      const id = accounts[index].id || a.id
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

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-muted-foreground">
        До {maxAccounts} ящиков через <strong className="text-foreground">IMAP</strong> (логин и пароль
        пользователя). Jarvis не открывает браузер — только стандартный протокол, как в почтовом
        клиенте. Для Gmail используйте{' '}
        <a
          href="https://support.google.com/accounts/answer/185833"
          target="_blank"
          rel="noreferrer"
          className="text-primary underline"
        >
          пароль приложения
        </a>
        .
      </p>

      {accounts.map((acc, index) => (
        <div
          key={index}
          className="rounded-lg border border-border/60 bg-muted/10 p-3 space-y-2"
        >
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{acc.label || `Ящик ${index + 1}`}</span>
            <label className="ml-auto flex items-center gap-1.5 text-[11px]">
              <input
                type="checkbox"
                checked={acc.enabled}
                onChange={(e) => patchAccount(index, { enabled: e.target.checked })}
              />
              Включён
            </label>
          </div>

          <Input
            placeholder="Название (Работа)"
            value={acc.label}
            onChange={(e) => patchAccount(index, { label: e.target.value })}
            className="h-8 text-xs"
          />
          <Input
            type="email"
            placeholder="email@example.com"
            value={acc.email}
            onChange={(e) => patchAccount(index, { email: e.target.value })}
            className="h-8 text-xs"
          />
          <Input
            type="password"
            placeholder={acc.password_configured ? 'Пароль сохранён — введите новый для смены' : 'Пароль IMAP'}
            value={acc.password}
            onChange={(e) => patchAccount(index, { password: e.target.value })}
            className="h-8 text-xs"
            autoComplete="off"
          />

          <div className="flex flex-wrap gap-1">
            {presets.map((p) => (
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
                {PRESET_LABELS[p] ?? p}
              </button>
            ))}
          </div>

          {!acc.preset && (
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
                onChange={(e) => patchAccount(index, { imap_port: Number(e.target.value) || 993 })}
                className="h-8 text-xs"
              />
            </div>
          )}

          <div className="flex gap-2">
            <Hint text="Проверить вход по IMAP без чтения писем агентом в браузере">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 text-[11px]"
                disabled={testingId !== null}
                onClick={() => void test(index)}
              >
                <PlugZap className="mr-1 h-3 w-3" />
                Проверить IMAP
              </Button>
            </Hint>
          </div>
        </div>
      ))}

      <Button type="button" disabled={saving} onClick={() => void save()} className="w-full sm:w-auto">
        {saving ? 'Сохранение…' : 'Сохранить почтовые ящики'}
      </Button>
    </div>
  )
}
