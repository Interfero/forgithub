import { useEffect, useState } from 'react'
import { Phone, PhoneCall, Play, Save, Webhook } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ServiceEnableToggle } from '@/components/ui/ServiceEnableToggle'
import {
  fetchTelephonyConfig,
  saveTelephonyConfig,
  synthesizeTelephonyGreeting,
  telephonyTestCall,
  telephonyTestWebhook,
} from '@/api/client'
import type { TelephonyConfig } from '@/types'

const PROVIDERS = [
  { id: 'mango', label: 'Mango Office' },
  { id: 'zadarma', label: 'Zadarma' },
  { id: 'generic', label: 'Generic (JSON webhook)' },
] as const

interface SettingsTelephonySectionProps {
  onSystemLog?: (text: string) => void
  onRefresh?: () => void
}

/** АТС — звонки на Джарвис (из панели разработчика перенесено в Настройки). */
export function SettingsTelephonySection({
  onSystemLog,
  onRefresh,
}: SettingsTelephonySectionProps) {
  const [cfg, setCfg] = useState<TelephonyConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [testPhone, setTestPhone] = useState('')

  const load = () => {
    fetchTelephonyConfig()
      .then(setCfg)
      .catch(() => setCfg(null))
  }

  useEffect(() => {
    load()
  }, [])

  const save = async (patch: Partial<TelephonyConfig> & { enabled?: boolean }) => {
    setSaving(true)
    try {
      const res = await saveTelephonyConfig({
        enabled: patch.enabled ?? cfg?.enabled,
        provider: patch.provider ?? cfg?.provider,
        publicBaseUrl: patch.publicBaseUrl ?? cfg?.publicBaseUrl,
        webhookSecret: patch.webhookSecret ?? cfg?.webhookSecret,
        greetingText: patch.greetingText ?? cfg?.greetingText,
        mangoApiKey: patch.mangoApiKey ?? cfg?.mangoApiKey,
        mangoApiSalt: patch.mangoApiSalt ?? cfg?.mangoApiSalt,
        mangoLineNumber: patch.mangoLineNumber ?? cfg?.mangoLineNumber,
        mangoExtension: patch.mangoExtension ?? cfg?.mangoExtension,
        zadarmaApiKey: patch.zadarmaApiKey ?? cfg?.zadarmaApiKey,
        zadarmaApiSecret: patch.zadarmaApiSecret ?? cfg?.zadarmaApiSecret,
        zadarmaIvrFileId: patch.zadarmaIvrFileId ?? cfg?.zadarmaIvrFileId,
        useLlmOnCall: patch.useLlmOnCall ?? cfg?.useLlmOnCall,
      })
      setCfg(res)
      onSystemLog?.('📞 Настройки АТС сохранены')
      onRefresh?.()
    } catch (e) {
      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`)
    } finally {
      setSaving(false)
    }
  }

  if (!cfg) {
    return (
      <p className="text-xs text-muted-foreground">Загрузка настроек АТС…</p>
    )
  }

  return (
    <div className="space-y-3 rounded-lg border border-border/80 bg-muted/15 p-3 shadow-sm">
      <div className="flex items-center gap-2 border-b border-border/60 pb-2">
        <Phone className="h-4 w-4 text-primary" />
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-medium">АТС — звонки на Джарвис</h4>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            Входящий звонок → HTTP на Jarvis → озвучка приветствия (edge-tts).
          </p>
        </div>
      </div>

      <ServiceEnableToggle
        label="Активная телефония"
        description="Webhook и сценарии АТС; ключи Mango/Zadarma не удаляются"
        enabled={cfg.enabled}
        ready
        busy={saving}
        onToggle={(on) => void save({ enabled: on })}
      />

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        Для звонков из интернета укажите публичный URL (ngrok) и пропишите webhook в кабинете АТС.
      </p>

      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium">Провайдер</label>
          <select
            value={cfg.provider}
            onChange={(e) => setCfg({ ...cfg, provider: e.target.value })}
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium">Публичный URL (ngrok)</label>
          <input
            value={cfg.publicBaseUrl}
            onChange={(e) => setCfg({ ...cfg, publicBaseUrl: e.target.value })}
            placeholder="https://xxxx.ngrok-free.app"
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-sm"
          />
        </div>
      </div>

      <div className="space-y-1 rounded border border-dashed border-border/70 bg-muted/20 p-2 font-mono text-[10px]">
        <p>
          <Webhook className="mr-1 inline h-3 w-3" />
          Webhook: {cfg.webhookUrl}
        </p>
        <p>Сценарий Mango: {cfg.scenarioUrl}</p>
        <p>Аудио: {cfg.greetingMediaUrl}</p>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium">Секрет webhook (опционально)</label>
        <input
          type="password"
          value={cfg.webhookSecret}
          onChange={(e) => setCfg({ ...cfg, webhookSecret: e.target.value })}
          placeholder={cfg.webhookSecretConfigured ? '•••• сохранён' : 'секрет'}
          className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
        />
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium">Текст приветствия Джарвис</label>
        <textarea
          value={cfg.greetingText}
          onChange={(e) => setCfg({ ...cfg, greetingText: e.target.value })}
          rows={3}
          className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
        />
      </div>

      <details className="text-xs">
        <summary className="cursor-pointer font-medium">Mango Office API</summary>
        <div className="mt-2 grid gap-2">
          <input
            placeholder="API key"
            value={cfg.mangoApiKey}
            onChange={(e) => setCfg({ ...cfg, mangoApiKey: e.target.value })}
            className="rounded-md border border-input bg-background px-2 py-1.5 font-mono text-sm"
          />
          <input
            type="password"
            placeholder="API salt"
            value={cfg.mangoApiSalt}
            onChange={(e) => setCfg({ ...cfg, mangoApiSalt: e.target.value })}
            className="rounded-md border border-input bg-background px-2 py-1.5 font-mono text-sm"
          />
          <input
            placeholder="Линия (АОН)"
            value={cfg.mangoLineNumber}
            onChange={(e) => setCfg({ ...cfg, mangoLineNumber: e.target.value })}
            className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
          />
          <input
            placeholder="Добавочный extension сотрудника"
            value={cfg.mangoExtension}
            onChange={(e) => setCfg({ ...cfg, mangoExtension: e.target.value })}
            className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
          />
        </div>
      </details>

      <details className="text-xs">
        <summary className="cursor-pointer font-medium">Zadarma API</summary>
        <div className="mt-2 grid gap-2">
          <input
            placeholder="API key"
            value={cfg.zadarmaApiKey}
            onChange={(e) => setCfg({ ...cfg, zadarmaApiKey: e.target.value })}
            className="rounded-md border border-input bg-background px-2 py-1.5 font-mono text-sm"
          />
          <input
            type="password"
            placeholder="API secret"
            value={cfg.zadarmaApiSecret}
            onChange={(e) => setCfg({ ...cfg, zadarmaApiSecret: e.target.value })}
            className="rounded-md border border-input bg-background px-2 py-1.5 font-mono text-sm"
          />
          <input
            placeholder="ID файла IVR (из кабинета Zadarma)"
            value={cfg.zadarmaIvrFileId}
            onChange={(e) => setCfg({ ...cfg, zadarmaIvrFileId: e.target.value })}
            className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
          />
        </div>
      </details>

      <label className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={cfg.useLlmOnCall}
          onChange={(e) => setCfg({ ...cfg, useLlmOnCall: e.target.checked })}
        />
        Отвечать голосом через DeepSeek (кратко, при DTMF/речи)
      </label>

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 gap-1 text-xs"
          disabled={saving}
          onClick={() => void save({})}
        >
          <Save className="h-3.5 w-3.5" />
          Сохранить
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 gap-1 text-xs"
          onClick={() => {
            void synthesizeTelephonyGreeting()
              .then(() => {
                onSystemLog?.('🔊 Приветствие синтезировано')
                load()
              })
              .catch((e) =>
                onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`),
              )
          }}
        >
          <Play className="h-3.5 w-3.5" />
          Синтез речи
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 gap-1 text-xs"
          onClick={() => {
            void telephonyTestWebhook()
              .then((r) =>
                onSystemLog?.(
                  `📞 Тест webhook: ${r.ok ? 'OK' : 'ошибка'} ${r.audio_url ?? ''}`,
                ),
              )
              .catch((e) =>
                onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`),
              )
          }}
        >
          <Webhook className="h-3.5 w-3.5" />
          Тест webhook
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[140px] flex-1">
          <label className="mb-1 block text-xs font-medium">Тест исходящего (Mango)</label>
          <input
            value={testPhone}
            onChange={(e) => setTestPhone(e.target.value)}
            placeholder="+79..."
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
          />
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 gap-1 text-xs"
          onClick={() => {
            void telephonyTestCall(testPhone)
              .then((r) =>
                onSystemLog?.(
                  r.ok
                    ? `📞 ${r.message ?? 'Звонок запущен'}`
                    : `❌ ${r.error ?? 'ошибка Mango API'}`,
                ),
              )
              .catch((e) =>
                onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка'}`),
              )
          }}
        >
          <PhoneCall className="h-3.5 w-3.5" />
          Позвонить
        </Button>
      </div>

      {cfg.statusLabel && (
        <p className="text-[11px] text-muted-foreground">
          Статус: <strong>{cfg.statusLabel}</strong>
          {cfg.lastCaller && ` · последний: ${cfg.lastCaller}`}
        </p>
      )}
    </div>
  )
}
