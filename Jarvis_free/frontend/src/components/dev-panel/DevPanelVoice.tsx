import { useCallback, useEffect, useState } from 'react'
import { DownloadActionButton } from '@/components/ui/DownloadActionButton'
import { DownloadProgress } from '@/components/ui/DownloadProgress'
import { Button } from '@/components/ui/button'
import { useDownloadPoll } from '@/hooks/useDownloadPoll'
import { Separator } from '@/components/ui/separator'
import { VoiceStudio } from '@/components/settings/VoiceStudio'
import { fetchXttsStatus } from '@/api/client'
import { requestXttsInstall } from '@/lib/xttsInstall'
import type { VoiceSlot, XttsStatus } from '@/types'

interface DevPanelVoiceProps {
  xtts: XttsStatus
  voiceSlots: VoiceSlot[]
  onXttsRefresh: () => void
  onVoiceSlotUpdate: (slot: VoiceSlot) => void
  onVoiceRefresh: () => void
  onSystemLog?: (text: string) => void
}

export function DevPanelVoice({
  xtts,
  voiceSlots,
  onXttsRefresh,
  onVoiceSlotUpdate,
  onVoiceRefresh,
  onSystemLog,
}: DevPanelVoiceProps) {
  const [downloading, setDownloading] = useState(false)
  const [xttsLocal, setXttsLocal] = useState(xtts)

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
  const showInstallError = xttsLocal.status === 'error' && xttsLocal.error

  const handleDownloadVoice = async () => {
    if (pythonBlocked || downloading) return
    setDownloading(true)
    const result = await requestXttsInstall()
    if (result.kind !== 'error') setXttsLocal(result.status)

    if (result.kind === 'already_installed') {
      onSystemLog?.('✅ XTTS-v2 уже установлен — повторная загрузка не нужна')
      return
    }
    if (result.kind === 'in_progress') {
      setDownloading(true)
      onSystemLog?.('⏳ Установка XTTS уже идёт…')
      return
    }
    if (result.kind === 'blocked') {
      onSystemLog?.(`⚠️ ${result.reason}`)
      return
    }
    if (result.kind === 'error') {
      onSystemLog?.(`❌ ${result.message}`)
      return
    }

    setDownloading(true)
    onSystemLog?.('📥 Докачивание библиотек (torch, TTS, ~1.8 ГБ)…')
    const deadline = Date.now() + 45 * 60 * 1000
    const interval = setInterval(async () => {
      const st = await pollXtts()
      if (st.status === 'ready' || st.importable) {
        onSystemLog?.('✅ XTTS-v2 установлен и готов')
        clearInterval(interval)
        setDownloading(false)
        return
      }
      if (st.status === 'error') {
        onSystemLog?.(`❌ XTTS: ${st.error ?? st.message}`)
        clearInterval(interval)
        setDownloading(false)
        return
      }
      if (st.status === 'unsupported_python') {
        clearInterval(interval)
        setDownloading(false)
        return
      }
      if (Date.now() > deadline) {
        onSystemLog?.('⚠️ Превышено время ожидания загрузки XTTS')
        clearInterval(interval)
        setDownloading(false)
      }
    }, 1500)
  }

  return (
    <div className="space-y-3 rounded-md border border-border/50 bg-background/40 p-3">
      <div>
        <h3 className="text-[11px] font-semibold text-foreground">Голос Jarvis (XTTS-v2)</h3>
        <p className="mt-1 text-[10px] text-muted-foreground">
          Установка TTS, torch, torchaudio и модель ~1.8 ГБ с Hugging Face. Python в venv:{' '}
          <strong>{xttsLocal.pythonVersion ?? '—'}</strong>
          {xttsLocal.pythonOkForXtts === false && ' — нужен 3.9–3.11'}.
        </p>

        {pythonBlocked && (
          <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-[10px] text-amber-900 dark:text-amber-100">
            <p className="font-medium">{xttsLocal.message}</p>
            {xttsLocal.detail && <p className="mt-1 opacity-90">{xttsLocal.detail}</p>}
          </div>
        )}

        {isReady && !pythonBlocked && (
          <p className="mt-1 text-[10px] text-emerald-600 dark:text-emerald-400">✓ XTTS-v2 готов</p>
        )}

        {showInstallError && (
          <p className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 p-2 text-[10px] text-destructive whitespace-pre-wrap break-words max-h-24 overflow-y-auto">
            {xttsLocal.error}
          </p>
        )}

        {showProgress && (
          <DownloadProgress
            className="mt-2"
            percent={xttsLocal.progress}
            indeterminate={xttsLocal.progress <= 0}
            message={xttsLocal.message || 'Установка XTTS…'}
          />
        )}
        <DownloadActionButton
          className="mt-2"
          label={pythonBlocked ? 'Недоступно' : isReady ? 'Уже установлено' : 'Докачать библиотеки'}
          activeLabel="Установка…"
          loading={downloading}
          active={showProgress}
          disabled={downloading || isReady || pythonBlocked}
          onClick={() => void handleDownloadVoice()}
        />
        {showProgress && (
          <p className="mt-1 text-[9px] text-muted-foreground">
            Первая установка может занять 10–30 минут — прогресс обновляется каждую секунду.
          </p>
        )}
      </div>

      <Separator />

      <div>
        <p className="mb-2 text-[10px] text-muted-foreground">
          Слоты: 3 образца 15–20 с. Пустые слоты → базовый Кощей. Озвучка: «Речь в текст».
        </p>
        <VoiceStudio slots={voiceSlots} onUpdate={onVoiceSlotUpdate} onRefresh={onVoiceRefresh} />
      </div>
    </div>
  )
}
