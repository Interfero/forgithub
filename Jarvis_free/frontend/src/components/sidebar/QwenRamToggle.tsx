import { Brain, CheckCircle2, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { setQwenRamEnabled } from '@/api/client'
import { DownloadActionButton } from '@/components/ui/DownloadActionButton'
import { DownloadProgress } from '@/components/ui/DownloadProgress'
import { Hint } from '@/components/ui/hint'
import { useDownloadPoll } from '@/hooks/useDownloadPoll'
import {
  fetchQwenDownloadProgress,
  requestQwenModelDownload,
  type QwenDownloadProgress,
} from '@/lib/qwenInstall'
import { appBaseUrlWithSlash } from '@/lib/appUrl'
import { cn } from '@/lib/utils'
import type { LocalQwenState } from '@/types'

interface QwenRamToggleProps {
  qwen: LocalQwenState
  disabled?: boolean
  inSettings?: boolean
  onChanged?: () => void
}

function isRamReady(q: LocalQwenState): boolean {
  return Boolean(q.ramEnabled && q.ramUsable)
}

function isRamLoading(q: LocalQwenState): boolean {
  if (!q.ramEnabled || isRamReady(q)) return false
  return (
    q.ramPhase === 'loading' ||
    q.ramPhase === 'pending' ||
    q.status === 'loading_ram' ||
    q.status === 'pending_ram' ||
    (q.filesPresent && !q.ready)
  )
}

function isRamBlocked(q: LocalQwenState): boolean {
  if (!q.ramEnabled || isRamReady(q) || isRamLoading(q)) return false
  return q.ramPhase === 'skipped' || q.ramPhase === 'error' || q.status === 'ram_error'
}

const IDLE_DL: QwenDownloadProgress = {
  phase: 'idle',
  progress: 0,
  message: '',
  bytesDone: 0,
  bytesTotal: 0,
  filesPresent: false,
}

export function QwenRamToggle({ qwen, disabled, inSettings = false, onChanged }: QwenRamToggleProps) {
  const [busy, setBusy] = useState(false)
  const [downloadUiActive, setDownloadUiActive] = useState(false)
  const [downloadBusy, setDownloadBusy] = useState(false)
  const [dl, setDl] = useState<QwenDownloadProgress>(IDLE_DL)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [optimisticOn, setOptimisticOn] = useState<boolean | null>(null)

  const serverDownloading =
    qwen.downloadPhase === 'downloading' || qwen.status === 'downloading'
  const showDownloadPanel = downloadUiActive || serverDownloading

  const enabled = optimisticOn ?? qwen.ramEnabled
  const ready = isRamReady({ ...qwen, ramEnabled: enabled })
  const loading = isRamLoading({ ...qwen, ramEnabled: enabled })
  const blocked = isRamBlocked({ ...qwen, ramEnabled: enabled })

  const pollDownload = useCallback(async () => {
    try {
      const st = await fetchQwenDownloadProgress()
      setDl(st)
      if (st.filesPresent) {
        setDownloadUiActive(false)
        setDownloadError(null)
        onChanged?.()
        return
      }
      if (st.phase === 'error') {
        setDownloadUiActive(false)
        setDownloadError(st.message || 'Ошибка загрузки')
        onChanged?.()
        return
      }
      if (st.phase === 'downloading') {
        setDownloadError(null)
      }
      onChanged?.()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Нет связи с сервером'
      if (/HTML|не JSON|404|Failed to fetch/i.test(msg)) {
        setDownloadError(msg)
        setDownloadUiActive(false)
      }
    }
  }, [onChanged])

  useDownloadPoll(showDownloadPanel, pollDownload, 1000)

  useEffect(() => {
    if (optimisticOn !== null && optimisticOn === qwen.ramEnabled) {
      setOptimisticOn(null)
    }
  }, [optimisticOn, qwen.ramEnabled])

  useEffect(() => {
    if (qwen.filesPresent && downloadUiActive) {
      setDownloadUiActive(false)
    }
  }, [qwen.filesPresent, downloadUiActive])

  useEffect(() => {
    if (!enabled || ready || !onChanged) return
    const id = window.setInterval(() => onChanged(), 1500)
    return () => window.clearInterval(id)
  }, [enabled, ready, onChanged])

  const toggle = useCallback(async () => {
    if (disabled || busy || !qwen.filesPresent) return
    const next = !enabled
    setOptimisticOn(next)
    setBusy(true)
    try {
      await setQwenRamEnabled(next)
      onChanged?.()
    } catch {
      setOptimisticOn(null)
    } finally {
      setBusy(false)
    }
  }, [busy, disabled, enabled, onChanged, qwen.filesPresent])

  const startDownload = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      if (disabled || downloadBusy || showDownloadPanel) return

      setDownloadError(null)
      setDownloadUiActive(true)
      setDownloadBusy(true)
      setDl({
        phase: 'downloading',
        progress: 0,
        message: 'Запуск загрузки на сервере…',
        bytesDone: 0,
        bytesTotal: qwen.downloadBytesTotal || 8_900_000_000,
        filesPresent: false,
      })

      try {
        const res = await requestQwenModelDownload(qwen)
        if (res.kind === 'error') {
          setDownloadError(res.message)
          setDownloadUiActive(false)
          return
        }
        if (res.kind === 'already_installed') {
          setDownloadUiActive(false)
          onChanged?.()
          return
        }
        await pollDownload()
      } catch (err) {
        setDownloadError(
          err instanceof Error ? err.message : 'Не удалось начать загрузку',
        )
        setDownloadUiActive(false)
      } finally {
        setDownloadBusy(false)
      }
    },
    [disabled, downloadBusy, showDownloadPanel, onChanged, pollDownload, qwen],
  )

  const displayPct =
    dl.progress > 0
      ? dl.progress
      : qwen.downloadProgress > 0
        ? qwen.downloadProgress
        : 0
  const displayMessage =
    dl.message || qwen.downloadMessage || qwen.message || 'Скачивание Qwen 2.5 14B…'
  const displayBytesDone = dl.bytesDone || qwen.downloadBytesDone
  const displayBytesTotal = dl.bytesTotal || qwen.downloadBytesTotal

  const hint = !qwen.filesPresent
    ? showDownloadPanel
      ? `Скачивание… ${displayPct > 0 ? `${displayPct}%` : ''}`
      : 'Скачайте модель внутрь Jarvis (~9 ГБ)'
    : enabled
      ? 'Выключить — выгрузить Qwen из ОЗУ'
      : 'Включить — загрузить Qwen в память'

  const progressPct =
    qwen.ramProgress > 0
      ? Math.min(100, qwen.ramProgress)
      : loading
        ? undefined
        : 0

  return (
    <div
      className={cn(
        'flex flex-col gap-2.5',
        !inSettings && 'rounded-xl border border-border/80 bg-card/60 p-3 shadow-sm',
        !inSettings && enabled && 'border-primary/30 bg-primary/6',
        inSettings && 'rounded-lg border border-border/60 bg-muted/15 p-3',
        inSettings && enabled && 'border-primary/25 bg-primary/5',
        disabled && !showDownloadPanel && 'opacity-60',
      )}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            'flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors',
            enabled
              ? 'bg-primary/18 text-primary ring-1 ring-primary/35'
              : 'bg-muted text-muted-foreground ring-1 ring-border/60',
          )}
        >
          {busy || downloadBusy || showDownloadPanel || (loading && !ready) ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : ready ? (
            <CheckCircle2 className="h-4 w-4 text-primary" />
          ) : (
            <Brain className="h-4 w-4" strokeWidth={2} />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold leading-tight text-foreground">Qwen 2.5 14B</p>
          <p className="text-[10px] text-muted-foreground">нейросеть в ОЗУ</p>
        </div>
        <Hint text={hint}>
          <button
            type="button"
            role="switch"
            aria-checked={enabled}
            aria-label={enabled ? 'Выключить Qwen в ОЗУ' : 'Включить Qwen в ОЗУ'}
            disabled={disabled || busy || downloadBusy || !qwen.filesPresent || showDownloadPanel}
            onClick={() => void toggle()}
            className={cn(
              'relative h-7 w-[3.25rem] shrink-0 rounded-full p-0.5 transition-all duration-300 ease-out',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
              enabled
                ? 'bg-primary shadow-[inset_0_2px_6px_rgba(0,0,0,0.35),0_1px_0_rgba(255,255,255,0.12)_inset,0_2px_8px_rgba(45,212,191,0.35)]'
                : 'bg-muted/90 shadow-[inset_0_2px_6px_rgba(0,0,0,0.4),0_1px_0_rgba(255,255,255,0.06)_inset]',
              (disabled || busy || downloadBusy || !qwen.filesPresent || showDownloadPanel) &&
                'cursor-not-allowed opacity-60',
            )}
          >
            <span
              className={cn(
                'pointer-events-none block h-6 w-6 rounded-full bg-background transition-transform duration-300 ease-out',
                'shadow-[0_2px_5px_rgba(0,0,0,0.45),0_1px_0_rgba(255,255,255,0.85)_inset,0_-1px_0_rgba(0,0,0,0.08)_inset]',
                enabled ? 'translate-x-[1.35rem]' : 'translate-x-0',
              )}
            />
          </button>
        </Hint>
      </div>

      {disabled && !qwen.filesPresent && !showDownloadPanel ? (
        <p className="text-[10px] text-amber-700/90 dark:text-amber-300/90">
          Запустите сервер Jarvis (start.bat), затем откройте{' '}
          <strong className="font-medium">{appBaseUrlWithSlash()}</strong>
        </p>
      ) : !qwen.filesPresent ? (
        <div className="space-y-2">
          <p className="text-[10px] leading-snug text-muted-foreground">
            {qwen.modelMetaStale
              ? 'Файл модели отсутствует на диске. Скачайте снова (~9 ГБ в папку Jarvis).'
              : 'Файл модели не найден. Скачивание идёт в backend/data/models (~9 ГБ).'}
          </p>

          {showDownloadPanel && (
            <DownloadProgress
              percent={displayPct}
              indeterminate={displayPct <= 0 && dl.phase === 'downloading'}
              message={displayMessage}
              bytesDone={displayBytesDone}
              bytesTotal={displayBytesTotal}
            />
          )}

          {downloadError && (
            <p className="rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1.5 text-[10px] leading-snug text-destructive">
              {downloadError}
            </p>
          )}

          <DownloadActionButton
            label="Скачать модель"
            activeLabel="Загрузка…"
            loading={downloadBusy}
            active={showDownloadPanel}
            disabled={disabled || showDownloadPanel}
            onClick={(e) => void startDownload(e)}
          />
        </div>
      ) : ready ? (
        <p className="flex items-center gap-1.5 text-[11px] font-medium text-primary">
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          Готово к использованию
        </p>
      ) : enabled && loading ? (
        <DownloadProgress
          percent={progressPct ?? 0}
          indeterminate={progressPct === undefined}
          message={qwen.ramMessage || qwen.message || 'Загрузка модели в память…'}
        />
      ) : enabled && blocked ? (
        <p className="text-[10px] leading-snug text-amber-600/90 dark:text-amber-400/90">
          {qwen.ramMessage || qwen.message || 'Локальная загрузка недоступна на этом CPU.'}
        </p>
      ) : (
        <p className="text-[10px] leading-snug text-muted-foreground">
          {enabled
            ? qwen.message || 'Ожидание готовности…'
            : 'Выключено — RAM свободна. Включите, когда нужен локальный Qwen.'}
        </p>
      )}
    </div>
  )
}
