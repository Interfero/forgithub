import { useCallback, useEffect, useRef } from 'react'
import {
  createJarvisSpeechListener,
  isSpeechRecognitionSupported,
  type JarvisListenStatus,
  type JarvisSpeechListener,
} from '@/lib/jarvisWakeListen'

export function useJarvisVoiceListen(options: {
  enabled: boolean
  paused?: boolean
  onWakeCommand: (command: string) => void
  onError?: (message: string) => void
  onStatus?: (status: JarvisListenStatus) => void
  onMicReady?: (ready: boolean) => void
  onInterim?: (text: string) => void
}) {
  const listenerRef = useRef<JarvisSpeechListener | null>(null)
  const startingRef = useRef(false)
  const onWakeRef = useRef(options.onWakeCommand)
  const onErrorRef = useRef(options.onError)
  const onStatusRef = useRef(options.onStatus)
  const onMicReadyRef = useRef(options.onMicReady)
  const onInterimRef = useRef(options.onInterim)

  useEffect(() => {
    onWakeRef.current = options.onWakeCommand
    onErrorRef.current = options.onError
    onStatusRef.current = options.onStatus
    onMicReadyRef.current = options.onMicReady
    onInterimRef.current = options.onInterim
  }, [
    options.onWakeCommand,
    options.onError,
    options.onStatus,
    options.onMicReady,
    options.onInterim,
  ])

  const ensureListener = useCallback(() => {
    if (listenerRef.current) return listenerRef.current
    listenerRef.current = createJarvisSpeechListener({
      onWakeCommand: (cmd) => onWakeRef.current(cmd),
      onError: (msg) => onErrorRef.current?.(msg),
      onStatus: (s) => onStatusRef.current?.(s),
      onInterim: (t) => onInterimRef.current?.(t),
    })
    return listenerRef.current
  }, [])

  useEffect(() => {
    const listener = ensureListener()
    let cancelled = false

    const stopAll = () => {
      startingRef.current = false
      listener.stop()
      onMicReadyRef.current?.(false)
    }

    if (!options.enabled || options.paused) {
      stopAll()
      return stopAll
    }

    if (!isSpeechRecognitionSupported()) {
      onErrorRef.current?.(
        'Голосовой ввод: Chrome/Edge и рабочий микрофон. Откройте сайт как http://127.0.0.1:8000',
      )
      return stopAll
    }

    startingRef.current = true
    void listener.start().then((ok) => {
      startingRef.current = false
      if (cancelled) {
        listener.stop()
        return
      }
      const micLive = listener.hasMicrophoneStream()
      onMicReadyRef.current?.(micLive)
      if (!ok) {
        onErrorRef.current?.('Не удалось запустить прослушивание.')
      }
    })

    return () => {
      cancelled = true
      stopAll()
    }
  }, [options.enabled, options.paused, ensureListener])

  useEffect(
    () => () => {
      listenerRef.current?.stop()
    },
    [],
  )

  return {
    isSupported: isSpeechRecognitionSupported(),
    stop: () => listenerRef.current?.stop(),
    isStarting: () => startingRef.current,
  }
}
