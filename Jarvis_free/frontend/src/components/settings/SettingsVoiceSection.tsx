import { useCallback, useEffect, useRef, useState } from 'react'
import { Square, Upload, Volume2 } from 'lucide-react'
import { DownloadActionButton } from '@/components/ui/DownloadActionButton'
import { DownloadProgress } from '@/components/ui/DownloadProgress'
import { Button } from '@/components/ui/button'
import { useDownloadPoll } from '@/hooks/useDownloadPoll'
import { Separator } from '@/components/ui/separator'
import { VoiceStudio } from '@/components/settings/VoiceStudio'
import { ServiceEnableToggle } from '@/components/ui/ServiceEnableToggle'
import {
  fetchXttsStatus,
  playVoicePreview,
  stopVoicePreview,
  uploadBaseVoice,
} from '@/api/client'
import { requestXttsInstall } from '@/lib/xttsInstall'
import type { VoiceBaseInfo, VoiceSlot, XttsStatus } from '@/types'

interface SettingsVoiceSectionProps {
  voiceBase: VoiceBaseInfo
  xtts: XttsStatus
  voiceSlots: VoiceSlot[]
  xttsActive?: boolean
  onXttsActiveChange?: (enabled: boolean) => void
  xttsServiceBusy?: boolean
  onXttsRefresh: () => void
  onVoiceSlotUpdate: (slot: VoiceSlot) => void
  onVoiceRefresh: () => void
  onBaseVoiceUploaded?: () => void
  onSystemLog?: (text: string) => void
}

export function SettingsVoiceSection({
  voiceBase,
  xtts,
  voiceSlots,
  xttsActive = true,
  onXttsActiveChange,
  xttsServiceBusy = false,
  onXttsRefresh,
  onVoiceSlotUpdate,
  onVoiceRefresh,
  onBaseVoiceUploaded,
  onSystemLog,
}: SettingsVoiceSectionProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [downloading, setDownloading] = useState(false)
  const [xttsLocal, setXttsLocal] = useState(xtts)
  const [xttsNotice, setXttsNotice] = useState<string | null>(null)
  const [basePreviewing, setBasePreviewing] = useState(false)

  const readySlots = voiceSlots.filter((s) => s.status === 'ready')
  const activeSlot = voiceBase.activeStudioSlot

  useEffect(() => {
    setXttsLocal(xtts)
    const busy =
      xtts.status === 'installing_deps' || xtts.status === 'downloading_model'
    if (busy) setDownloading(true)
  }, [xtts])

  const pollXtts = useCallback(async () => {
    const s = await fetchXttsStatus()
    setXttsLocal(s)
    onXttsRefresh()
    return s
  }, [onXttsRefresh])

  useDownloadPoll(downloading, pollXtts, 1000)

  const pythonBlocked = xttsLocal.pythonOkForXtts === false
  const isReady = xttsLocal.status === 'ready' || xttsLocal.importable
  const isBusy =
    xttsLocal.status === 'installing_deps' || xttsLocal.status === 'downloading_model'
  const showProgress = isBusy || downloading

  const handleDownloadVoice = async () => {
    if (pythonBlocked || downloading) return
    setXttsNotice(null)
    setDownloading(true)
    const result = await requestXttsInstall()
    setXttsLocal(result.kind !== 'error' ? result.status : xttsLocal)

    if (result.kind === 'blocked') {
      setXttsNotice(result.reason)
      return
    }
    if (result.kind === 'already_installed') {
      setXttsNotice(
        'Библиотеки XTTS-v2 уже установлены. Повторная загрузка не требуется.',
      )
      onSystemLog?.('✅ XTTS-v2 уже установлен — повторная загрузка не нужна')
      setDownloading(false)
      return
    }
    if (result.kind === 'in_progress') {
      setXttsNotice('Установка уже выполняется — дождитесь завершения.')
      setDownloading(true)
      return
    }
    if (result.kind === 'error') {
      onSystemLog?.(`❌ ${result.message}`)
      setDownloading(false)
      return
    }

    setDownloading(true)
    onSystemLog?.('📥 Докачивание библиотек (torch, TTS, ~1.8 ГБ)…')
    const deadline = Date.now() + 45 * 60 * 1000
    const interval = setInterval(async () => {
      const st = await pollXtts()
      if (st.status === 'ready' || st.importable) {
        onSystemLog?.('✅ XTTS-v2 установлен и готов')
        setXttsNotice(null)
        clearInterval(interval)
        setDownloading(false)
      } else if (st.status === 'error') {
        onSystemLog?.(`❌ XTTS: ${st.error ?? st.message}`)
        clearInterval(interval)
        setDownloading(false)
      } else if (st.status === 'unsupported_python') {
        clearInterval(interval)
        setDownloading(false)
      } else if (Date.now() > deadline) {
        onSystemLog?.('⚠️ Превышено время ожидания загрузки XTTS')
        clearInterval(interval)
        setDownloading(false)
      }
    }, 1500)
  }

  return (
    <div className="space-y-3">
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        <strong>Базовый голос</strong> ({voiceBase.filename ?? 'Кощей_silero.ogg'}) уже встроен —
        загрузка в настройках <strong>не обязательна</strong>, только если нужен другой запасной
        образец. Кнопка «Голос (Джарвис)» в шапке проигрывает именно этот файл. Для озвучки ответов
        в чате: если заполнены слоты студии, синтез идёт по <strong>вашему образцу</strong> (1 → 2 → 3);
        {activeSlot != null && (
          <>
            {' '}
            Сейчас активен: <strong>слот {activeSlot}</strong>.
          </>
        )}
        {readySlots.length === 0 && ' Слоты пусты — клон по базовому Кощею.'} Озвучка ответов в
        чате: «Речь в текст».
      </p>

      <div className="rounded-lg border border-border/80 bg-muted/15 p-3">
        <h4 className="text-sm font-medium">Запасной базовый голос (необязательно)</h4>
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          По умолчанию используется встроенный <strong>Кощей_silero.ogg</strong>. Загрузка нужна
          только чтобы заменить запасной образец · до 15 МБ · ogg, wav, mp3, webm, m4a, flac. То же
          можно прикрепить в чате (скрепка).
        </p>
        <input
          ref={fileRef}
          type="file"
          accept="audio/*,.ogg,.wav,.mp3,.webm,.m4a,.flac,.aac,.opus,.mpeg"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) {
              void uploadBaseVoice(f)
                .then((info) => {
                  const kb = info.size_bytes ? Math.round(info.size_bytes / 1024) : '?'
                  onSystemLog?.(`🎙️ Базовый голос: \`${f.name}\` (${kb} KB)`)
                  onBaseVoiceUploaded?.()
                })
                .catch((err) => {
                  onSystemLog?.(
                    `❌ ${err instanceof Error ? err.message : 'ошибка загрузки голоса'}`,
                  )
                })
            }
            e.target.value = ''
          }}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1 text-xs"
            disabled={!voiceBase.exists}
            onClick={() => {
              if (basePreviewing) {
                stopVoicePreview()
                setBasePreviewing(false)
                return
              }
              void playVoicePreview().then((audio) => {
                if (!audio) {
                  onSystemLog?.('❌ Базовый голос не найден на сервере')
                  return
                }
                setBasePreviewing(true)
                const done = () => setBasePreviewing(false)
                audio.onended = done
                audio.onerror = done
              })
            }}
          >
            {basePreviewing ? (
              <Square className="h-3 w-3 fill-current" />
            ) : (
              <Volume2 className="h-3.5 w-3.5" />
            )}
            {basePreviewing ? 'Остановить' : 'Прослушать'}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1 text-xs"
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="h-3.5 w-3.5" />
            Загрузить запасной
          </Button>
        </div>
      </div>

      <div id="settings-section-xtts" className="scroll-mt-4 rounded-lg border border-border/80 bg-muted/15 p-3">
        <h4 className="text-sm font-medium">Движок клонирования (XTTS-v2)</h4>
        {onXttsActiveChange && (
          <div className="mt-2">
            <ServiceEnableToggle
              label="Активный движок XTTS-v2"
              description="Выключено — озвучка через edge-tts (облако), без клонирования"
              enabled={xttsActive}
              ready
              busy={xttsServiceBusy}
              onToggle={onXttsActiveChange}
            />
          </div>
        )}
        <p className="mt-2 text-[11px] text-muted-foreground">
          Модель и веса сохраняются в <strong>backend/data/tts</strong> (внутри Jarvis), не в профиле
          Windows. Нужен для озвучки в тембре Кощея или ваших слотов. Без XTTS — временно edge-tts
          (облако Microsoft). Python: <strong>{xttsLocal.pythonVersion ?? '—'}</strong>
          {xttsLocal.pythonOkForXtts === false && ' — нужен 3.9–3.11'}.
        </p>
        {pythonBlocked && (
          <p className="mt-2 text-[11px] text-amber-800 dark:text-amber-200">{xttsLocal.message}</p>
        )}
        {isReady && !pythonBlocked && (
          <p className="mt-1 text-[11px] text-emerald-600 dark:text-emerald-400">
            ✓ Библиотеки установлены
          </p>
        )}
        {xttsNotice && (
          <p className="mt-2 text-[11px] text-amber-800 dark:text-amber-200">{xttsNotice}</p>
        )}
        {showProgress && (
          <DownloadProgress
            className="mt-2 max-w-md"
            percent={xttsLocal.progress}
            indeterminate={xttsLocal.progress <= 0}
            message={xttsLocal.message || 'Установка XTTS…'}
          />
        )}
        <DownloadActionButton
          className="mt-2 max-w-xs"
          label={pythonBlocked ? 'Недоступно' : isReady ? 'Уже установлено' : 'Докачать библиотеки'}
          activeLabel="Установка…"
          loading={downloading}
          active={showProgress}
          disabled={downloading || isReady || pythonBlocked}
          onClick={() => void handleDownloadVoice()}
        />
      </div>

      <Separator />

      <div>
        <h4 className="text-sm font-medium">Слоты образцов (3 × 15–20 с)</h4>
        <p className="mb-2 text-[11px] text-muted-foreground">
          ogg, wav, mp3, webm, m4a, flac — до 10 МБ. Можно записать здесь или прикрепить в чате.
        </p>
        <VoiceStudio slots={voiceSlots} onUpdate={onVoiceSlotUpdate} onRefresh={onVoiceRefresh} />
      </div>
    </div>
  )
}
