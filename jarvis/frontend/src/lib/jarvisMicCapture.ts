/**
 * Захват речи с микрофона: VAD (тишина/голос) + запись webm для STT на backend.
 */

export type MicCaptureStatus =
  | 'off'
  | 'starting'
  | 'listening'
  | 'recording'
  | 'transcribing'
  | 'error'

export interface MicCaptureHandlers {
  onStatus?: (status: MicCaptureStatus, detail?: string) => void
  onInterim?: (hint: string) => void
  onError?: (message: string) => void
  onUtterance: (blob: Blob, durationMs: number) => void
}

const SILENCE_MS = 1500
const MIN_SPEECH_MS = 450
const MAX_RECORD_MS = 14_000
const VAD_INTERVAL_MS = 120
const SPEECH_THRESHOLD = 0.011
/** Порог во время озвучки Jarvis — ниже, чтобы Шеф мог перебить голосом. */
const BARGE_IN_THRESHOLD = 0.014
const TTS_DUCK_THRESHOLD = 0.038

export interface MicCaptureController {
  start: () => Promise<boolean>
  stop: () => void
  isActive: () => boolean
  getStatus: () => MicCaptureStatus
  /** Повысить порог VAD, пока Jarvis озвучивает ответ (микрофон не выключается). */
  setTtsDucking: (on: boolean) => void
  /** Режим перебивания: чувствительный микрофон во время озвучки Jarvis. */
  setBargeInMode: (on: boolean) => void
}

function rmsFromAnalyser(analyser: AnalyserNode, buf: Float32Array): number {
  analyser.getFloatTimeDomainData(buf)
  let sum = 0
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
  return Math.sqrt(sum / buf.length)
}

export function createMicCapture(handlers: MicCaptureHandlers): MicCaptureController {
  let status: MicCaptureStatus = 'off'
  let active = false
  let stream: MediaStream | null = null
  let recorder: MediaRecorder | null = null
  let chunks: Blob[] = []
  let audioCtx: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let vadTimer: ReturnType<typeof setInterval> | null = null
  let recording = false
  let speechStartedAt = 0
  let lastLoudAt = 0
  let recordStartedAt = 0
  let ttsDucking = false
  let bargeInMode = false

  const setStatus = (s: MicCaptureStatus, detail?: string) => {
    status = s
    handlers.onStatus?.(s, detail)
  }

  const clearVad = () => {
    if (vadTimer != null) {
      clearInterval(vadTimer)
      vadTimer = null
    }
  }

  const release = () => {
    clearVad()
    if (recorder && recorder.state !== 'inactive') {
      try {
        recorder.stop()
      } catch {
        /* ignore */
      }
    }
    recorder = null
    chunks = []
    recording = false
    if (stream) {
      stream.getTracks().forEach((t) => t.stop())
      stream = null
    }
    if (audioCtx) {
      void audioCtx.close().catch(() => {})
      audioCtx = null
    }
    analyser = null
  }

  const finishRecording = () => {
    if (!recording || !recorder) return
    recording = false
    setStatus('transcribing', 'Распознавание…')
    try {
      recorder.stop()
    } catch {
      handlers.onError?.('Ошибка остановки записи')
      setStatus('listening')
    }
  }

  const startRecording = () => {
    if (!active || recording || !stream) return
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/ogg'
    chunks = []
    recorder = new MediaRecorder(stream, { mimeType: mime })
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: mime })
      chunks = []
      const durationMs = Date.now() - recordStartedAt
      recorder = null
      if (active) setStatus('listening')
      if (blob.size > 400 && durationMs >= MIN_SPEECH_MS) {
        handlers.onUtterance(blob, durationMs)
      }
    }
    recorder.onerror = () => {
      handlers.onError?.('Ошибка MediaRecorder')
      setStatus('error')
    }
    recorder.start(250)
    recording = true
    recordStartedAt = Date.now()
    setStatus('recording')
    handlers.onInterim?.('Говорите…')
  }

  const startVad = () => {
    if (!analyser || !audioCtx) return
    const buf = new Float32Array(analyser.fftSize)
    clearVad()
    vadTimer = setInterval(() => {
      if (!active || !analyser) return
      const level = rmsFromAnalyser(analyser, buf)
      const now = Date.now()
      const threshold = bargeInMode
        ? BARGE_IN_THRESHOLD
        : ttsDucking
          ? TTS_DUCK_THRESHOLD
          : SPEECH_THRESHOLD
      const loud = level >= threshold

      if (!recording) {
        if (loud) {
          if (!speechStartedAt) speechStartedAt = now
          if (now - speechStartedAt >= 120) startRecording()
        } else {
          speechStartedAt = 0
        }
        return
      }

      if (loud) {
        lastLoudAt = now
        return
      }

      const silentFor = now - (lastLoudAt || recordStartedAt)
      const total = now - recordStartedAt
      if (silentFor >= SILENCE_MS && total >= MIN_SPEECH_MS) {
        finishRecording()
        return
      }
      if (total >= MAX_RECORD_MS) finishRecording()
    }, VAD_INTERVAL_MS)
  }

  return {
    async start() {
      if (active) return true
      if (!navigator.mediaDevices?.getUserMedia) {
        handlers.onError?.('Браузер не поддерживает микрофон.')
        setStatus('error')
        return false
      }
      active = true
      setStatus('starting')
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false,
        })
        audioCtx = new AudioContext()
        const source = audioCtx.createMediaStreamSource(stream)
        analyser = audioCtx.createAnalyser()
        analyser.fftSize = 2048
        source.connect(analyser)
        speechStartedAt = 0
        lastLoudAt = 0
        setStatus('listening')
        handlers.onInterim?.('Слушаю…')
        startVad()
        return true
      } catch (e) {
        active = false
        release()
        const err = e as DOMException
        handlers.onError?.(err.message || 'Нет доступа к микрофону')
        setStatus('error')
        return false
      }
    },

    stop() {
      active = false
      release()
      setStatus('off')
    },

    isActive: () => active,
    getStatus: () => status,
    setTtsDucking(on: boolean) {
      ttsDucking = on
    },
    setBargeInMode(on: boolean) {
      bargeInMode = on
      if (on) ttsDucking = false
    },
  }
}

export function isMicCaptureSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined'
  )
}
