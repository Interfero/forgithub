import { useCallback, useEffect, useRef } from 'react'
import { transcribeVoiceAudio } from '@/api/client'
import {
  createMicCapture,
  type MicCaptureController,
  type MicCaptureStatus,
} from '@/lib/jarvisMicCapture'
import { createVoiceCommandQueue } from '@/lib/jarvisVoiceQueue'
import { isVoiceStopCommand } from '@/lib/voiceStop'

const DIALOG_WINDOW_MS = 45_000

export type JarvisListenStatus =
  | 'off'
  | 'starting'
  | 'waiting_wake'
  | 'recording'
  | 'error'

function mapStatus(s: MicCaptureStatus): JarvisListenStatus {
  if (s === 'listening' || s === 'transcribing') return 'waiting_wake'
  if (s === 'starting') return 'starting'
  if (s === 'recording') return 'recording'
  if (s === 'error') return 'error'
  return 'off'
}

export function useJarvisVoiceDialog(options: {
  enabled: boolean
  /** Не останавливать микрофон — только очередь отправки */
  sendPaused?: boolean
  /** Jarvis озвучивает ответ — микрофон остаётся активным для перебивания. */
  ttsActive?: boolean
  requireWakeWord?: boolean
  onCommand: (text: string) => void
  /** Перебить озвучку и генерацию — услышали речь во время ответа Jarvis. */
  onBargeIn?: () => void
  onStop?: () => void
  onError?: (message: string) => void
  onStatus?: (status: JarvisListenStatus) => void
  onInterim?: (text: string) => void
  onHeard?: (text: string, sent: boolean) => void
  onQueueChange?: (size: number) => void
}) {
  const captureRef = useRef<MicCaptureController | null>(null)
  const queueRef = useRef(createVoiceCommandQueue())
  const dialogUntilRef = useRef(0)
  const transcribingRef = useRef(0)
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onCommandRef = useRef(options.onCommand)
  const onBargeInRef = useRef(options.onBargeIn)
  const onStopRef = useRef(options.onStop)
  const onErrorRef = useRef(options.onError)
  const onStatusRef = useRef(options.onStatus)
  const onInterimRef = useRef(options.onInterim)
  const onHeardRef = useRef(options.onHeard)
  const onQueueChangeRef = useRef(options.onQueueChange)
  const requireWakeRef = useRef(options.requireWakeWord ?? false)
  const sendPausedRef = useRef(options.sendPaused ?? false)
  const ttsActiveRef = useRef(options.ttsActive ?? false)

  useEffect(() => {
    onCommandRef.current = options.onCommand
    onBargeInRef.current = options.onBargeIn
    onStopRef.current = options.onStop
    onErrorRef.current = options.onError
    onStatusRef.current = options.onStatus
    onInterimRef.current = options.onInterim
    onHeardRef.current = options.onHeard
    onQueueChangeRef.current = options.onQueueChange
    requireWakeRef.current = options.requireWakeWord ?? false
    sendPausedRef.current = options.sendPaused ?? false
    ttsActiveRef.current = options.ttsActive ?? false
  }, [
    options.onCommand,
    options.onBargeIn,
    options.onStop,
    options.onError,
    options.onStatus,
    options.onInterim,
    options.onHeard,
    options.onQueueChange,
    options.requireWakeWord,
    options.sendPaused,
    options.ttsActive,
  ])

  const notifyQueue = useCallback(() => {
    onQueueChangeRef.current?.(queueRef.current.size())
  }, [])

  const flushQueue = useCallback(() => {
    if (sendPausedRef.current) return
    if (transcribingRef.current > 0) return
    if (queueRef.current.size() === 0) return
    const payload = queueRef.current.drainBatch()
    if (!payload) return
    onInterimRef.current?.('')
    onCommandRef.current(payload)
    notifyQueue()
  }, [notifyQueue])

  const scheduleFlush = useCallback(() => {
    if (flushTimerRef.current) clearTimeout(flushTimerRef.current)
    flushTimerRef.current = setTimeout(() => {
      flushTimerRef.current = null
      flushQueue()
    }, 700)
  }, [flushQueue])

  const enqueueCommand = useCallback(
    (command: string) => {
      queueRef.current.push(command)
      notifyQueue()
      const n = queueRef.current.size()
      if (sendPausedRef.current) {
        onInterimRef.current?.(
          n > 1 ? `В очереди (${n})… Jarvis отвечает` : `В очереди… Jarvis отвечает`,
        )
        return
      }
      scheduleFlush()
    },
    [notifyQueue, scheduleFlush],
  )

  const ensureCapture = useCallback(() => {
    if (captureRef.current) return captureRef.current
    captureRef.current = createMicCapture({
      onStatus: (s, detail) => {
        onStatusRef.current?.(mapStatus(s))
        if (detail && s === 'transcribing') onInterimRef.current?.(detail)
      },
      onInterim: (t) => onInterimRef.current?.(t),
      onError: (msg) => onErrorRef.current?.(msg),
      onUtterance: async (blob) => {
        transcribingRef.current += 1
        try {
          onInterimRef.current?.('Распознаю речь…')
          const result = await transcribeVoiceAudio(blob)
          const raw = (result.text || '').trim()
          if (!raw || raw.length < 2) {
            onInterimRef.current?.('Не расслышал — повторите')
            return
          }

          if (result.stop_command || isVoiceStopCommand(raw)) {
            onInterimRef.current?.('Стоп')
            queueRef.current.clear()
            notifyQueue()
            onBargeInRef.current?.()
            onStopRef.current?.()
            onHeardRef.current?.(raw, false)
            return
          }

          const jarvisSpeaking = ttsActiveRef.current || sendPausedRef.current
          if (jarvisSpeaking) {
            onBargeInRef.current?.()
          }

          let command = (result.command || raw).trim()
          const requireWake = requireWakeRef.current
          const inDialog = Date.now() < dialogUntilRef.current

          if (result.wake_found) {
            dialogUntilRef.current = Date.now() + DIALOG_WINDOW_MS
            const afterWake = (result.command || '').trim()
            if (afterWake.length >= 2) {
              command = afterWake
            } else if (/^(?:дж(?:а(?:р(?:в(?:ис?)?)?)?)?|jarvi?s)$/i.test(raw.trim())) {
              command = 'слушаю'
            } else if (jarvisSpeaking) {
              onInterimRef.current?.('Слушаю…')
              onHeardRef.current?.(raw, false)
              return
            }
          } else if (jarvisSpeaking && !requireWake) {
            onInterimRef.current?.(`🎤 ${command}`)
            onHeardRef.current?.(command, true)
            dialogUntilRef.current = Date.now() + DIALOG_WINDOW_MS
            enqueueCommand(command)
            return
          } else if (requireWake && !inDialog) {
            onInterimRef.current?.(
              raw.length > 2
                ? `Услышал: «${raw.slice(0, 72)}» — отправляю в Jarvis`
                : 'Говорите — Jarvis слушает',
            )
          }

          if (inDialog || !requireWake) {
            dialogUntilRef.current = Date.now() + DIALOG_WINDOW_MS
          }

          if (command.length < 2) {
            onInterimRef.current?.('Не расслышал — повторите')
            onHeardRef.current?.(raw, false)
            return
          }

          onInterimRef.current?.(`🎤 ${command}`)
          onHeardRef.current?.(command, true)
          dialogUntilRef.current = Date.now() + DIALOG_WINDOW_MS
          enqueueCommand(command)
        } catch (e) {
          onErrorRef.current?.(
            e instanceof Error ? e.message : 'Ошибка распознавания речи',
          )
        } finally {
          transcribingRef.current = Math.max(0, transcribingRef.current - 1)
          if (!sendPausedRef.current) scheduleFlush()
        }
      },
    })
    return captureRef.current
  }, [enqueueCommand, notifyQueue, scheduleFlush])

  useEffect(() => {
    const cap = ensureCapture()
    if (!options.enabled) {
      dialogUntilRef.current = 0
      queueRef.current.clear()
      notifyQueue()
      cap.stop()
      return () => cap.stop()
    }

    if (!requireWakeRef.current) {
      dialogUntilRef.current = Number.MAX_SAFE_INTEGER
    }

    let cancelled = false
    void cap.start().then((ok) => {
      if (!ok && !cancelled) {
        onErrorRef.current?.('Не удалось запустить микрофон')
      }
    })

    return () => {
      cancelled = true
    }
  }, [options.enabled, ensureCapture, notifyQueue])

  useEffect(() => {
    if (!options.enabled) {
      captureRef.current?.stop()
      queueRef.current.clear()
      notifyQueue()
    }
  }, [options.enabled, notifyQueue])

  useEffect(() => {
    const cap = captureRef.current
    if (!cap) return
    const barge = !!(options.ttsActive || options.sendPaused)
    cap.setBargeInMode(barge)
    cap.setTtsDucking(false)
  }, [options.ttsActive, options.sendPaused])

  useEffect(() => {
    if (!options.sendPaused) {
      flushQueue()
    }
  }, [options.sendPaused, flushQueue])

  useEffect(
    () => () => {
      if (flushTimerRef.current) clearTimeout(flushTimerRef.current)
      captureRef.current?.stop()
    },
    [],
  )

  return {
    isSupported: typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia,
    stop: () => {
      queueRef.current.clear()
      captureRef.current?.stop()
      notifyQueue()
    },
    clearQueue: () => {
      queueRef.current.clear()
      notifyQueue()
    },
  }
}
