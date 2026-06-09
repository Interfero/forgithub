/**
 * Голосовой ввод: микрофон (getUserMedia) + wake-word «Джарвис» (Web Speech API, ru-RU).
 * После wake-word — запись вопроса до паузы (макс. 10 с), затем снова ожидание имени.
 */

export type JarvisListenStatus =
  | 'off'
  | 'starting'
  | 'waiting_wake'
  | 'recording'
  | 'error'

export interface JarvisSpeechListener {
  start: () => Promise<boolean>
  stop: () => void
  isActive: () => boolean
  getStatus: () => JarvisListenStatus
  hasMicrophoneStream: () => boolean
}

interface SpeechRecognitionLike extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((ev: SpeechRecognitionEventLike) => void) | null
  onerror: ((ev: SpeechRecognitionErrorEventLike) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
}

interface SpeechRecognitionEventLike {
  resultIndex: number
  results: SpeechRecognitionResultListLike
}

interface SpeechRecognitionResultListLike {
  length: number
  [index: number]: SpeechRecognitionResultLike
}

interface SpeechRecognitionResultLike {
  isFinal: boolean
  length: number
  [index: number]: { transcript: string }
}

interface SpeechRecognitionErrorEventLike {
  error: string
  message?: string
}

const WAKE_RE =
  /(?:^|[\s,.!?])(?:дж(?:а(?:[\s,.!?]|$)|(?:арвис|рвис|рви|рв|р))|jarvis|жарвис|дарвис|ярвис|джавис|джаврис)(?:[\s,.!?]|$)?/i

/** Пауза в речи — конец вопроса */
const SILENCE_MS = 1400
/** Максимальная длина записи вопроса после wake-word */
const RECORD_MAX_MS = 10_000
const MIN_COMMAND_LEN = 2

function getRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === 'undefined') return null
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function isSpeechRecognitionSupported(): boolean {
  return (
    getRecognitionCtor() != null &&
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia
  )
}

/** Явно запрашивает микрофон — индикатор в трее Windows. */
export async function requestMicrophoneAccess(): Promise<{
  ok: boolean
  error?: string
}> {
  if (!navigator.mediaDevices?.getUserMedia) {
    return { ok: false, error: 'Браузер не поддерживает доступ к микрофону.' }
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
      },
      video: false,
    })
    stream.getTracks().forEach((t) => t.stop())
    return { ok: true }
  } catch (e) {
    const err = e as DOMException
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      return {
        ok: false,
        error:
          'Доступ к микрофону запрещён. В Chrome: замок в адресной строке → Микрофон → Разрешить.',
      }
    }
    if (err.name === 'NotFoundError') {
      return { ok: false, error: 'Микрофон не найден. Подключите гарнитуру или проверьте Windows.' }
    }
    return { ok: false, error: err.message || 'Не удалось открыть микрофон.' }
  }
}

function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/\s+/g, ' ')
    .trim()
}

export function extractCommandAfterWake(transcript: string): string | null {
  const raw = transcript.trim()
  if (!raw) return null
  const norm = normalize(raw)
  if (!WAKE_RE.test(norm)) return null

  const patterns = [
    /джарвис[,:]?\s*/gi,
    /jarvis[,:]?\s*/gi,
    /жарвис[,:]?\s*/gi,
    /дарвис[,:]?\s*/gi,
    /ярвис[,:]?\s*/gi,
    /джавис[,:]?\s*/gi,
    /джаврис[,:]?\s*/gi,
    /джа[,:]?\s*/gi,
  ]

  let idx = -1
  for (const re of patterns) {
    re.lastIndex = 0
    let m: RegExpExecArray | null
    while ((m = re.exec(raw)) !== null) {
      const end = m.index + m[0].length
      if (end > idx) idx = end
    }
  }
  if (idx < 0) return null

  const command = raw.slice(idx).trim().replace(/^[,.\s!?]+/, '')
  return command || null
}

function stripWakeFromChunk(text: string): string {
  const cmd = extractCommandAfterWake(text)
  if (cmd) return cmd
  const norm = normalize(text)
  if (WAKE_RE.test(norm)) return ''
  return text.trim()
}

export function createJarvisSpeechListener(handlers: {
  onWakeCommand: (command: string, rawTranscript: string) => void
  onStatus?: (status: JarvisListenStatus, detail?: string) => void
  onError?: (message: string) => void
  onInterim?: (text: string) => void
}): JarvisSpeechListener {
  const Ctor = getRecognitionCtor()
  let recognition: SpeechRecognitionLike | null = null
  let micStream: MediaStream | null = null
  let active = false
  let status: JarvisListenStatus = 'off'
  let restartTimer: ReturnType<typeof setTimeout> | null = null
  let silenceTimer: ReturnType<typeof setTimeout> | null = null
  let maxRecordTimer: ReturnType<typeof setTimeout> | null = null
  let lastSentAt = 0
  let lastSentCommand = ''
  let recording = false
  let commandParts: string[] = []
  let recordingStartedAt = 0
  let lastSpeechAt = 0
  let networkErrors = 0
  let fatalError = false

  const setStatus = (s: JarvisListenStatus, detail?: string) => {
    status = s
    handlers.onStatus?.(s, detail)
  }

  const clearRestart = () => {
    if (restartTimer != null) {
      clearTimeout(restartTimer)
      restartTimer = null
    }
  }

  const clearRecordTimers = () => {
    if (silenceTimer != null) {
      clearTimeout(silenceTimer)
      silenceTimer = null
    }
    if (maxRecordTimer != null) {
      clearTimeout(maxRecordTimer)
      maxRecordTimer = null
    }
  }

  const releaseMic = () => {
    if (micStream) {
      micStream.getTracks().forEach((t) => t.stop())
      micStream = null
    }
  }

  const mergedCommand = (): string =>
    commandParts
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim()

  const finishRecording = (reason: 'silence' | 'max_time' | 'final') => {
    if (!recording) return
    clearRecordTimers()
    recording = false

    const merged = mergedCommand()
    commandParts = []
    setStatus('waiting_wake')

    if (merged.length < MIN_COMMAND_LEN) {
      return
    }

    const now = Date.now()
    if (merged === lastSentCommand && now - lastSentAt < 4000) return
    lastSentCommand = merged
    lastSentAt = now
    handlers.onWakeCommand(merged, merged)
    void reason
  }

  const scheduleSilenceCheck = () => {
    clearRecordTimers()
    if (!recording || !active) return

    silenceTimer = setTimeout(() => {
      silenceTimer = null
      if (!recording || !active) return
      const silentFor = Date.now() - lastSpeechAt
      const merged = mergedCommand()
      if (merged.length >= MIN_COMMAND_LEN && silentFor >= SILENCE_MS) {
        finishRecording('silence')
        return
      }
      if (Date.now() - recordingStartedAt >= RECORD_MAX_MS) {
        finishRecording('max_time')
        return
      }
      scheduleSilenceCheck()
    }, SILENCE_MS)
  }

  const beginRecording = (initialChunk?: string) => {
    recording = true
    recordingStartedAt = Date.now()
    lastSpeechAt = Date.now()
    commandParts = []
    if (initialChunk && initialChunk.length >= MIN_COMMAND_LEN) {
      commandParts.push(initialChunk)
    }
    setStatus('recording')
    scheduleSilenceCheck()
    maxRecordTimer = setTimeout(() => {
      maxRecordTimer = null
      if (recording) finishRecording('max_time')
    }, RECORD_MAX_MS)
  }

  const handleResult = (ev: SpeechRecognitionEventLike) => {
    let interim = ''
    let finalChunk = ''

    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const res = ev.results[i]
      const text = res[0]?.transcript ?? ''
      if (res.isFinal) finalChunk += text
      else interim += text
    }

    const combined = (finalChunk || interim).trim()
    if (!combined) return

    const norm = normalize(combined)
    const hasWake = WAKE_RE.test(norm)

    if (recording) {
      lastSpeechAt = Date.now()
      if (interim) handlers.onInterim?.(mergedCommand() || interim)
      if (finalChunk) {
        const piece = stripWakeFromChunk(finalChunk)
        if (piece.length >= 1) commandParts.push(piece)
      }
      scheduleSilenceCheck()
      return
    }

    if (!hasWake) return

    if (interim) handlers.onInterim?.(combined)

    const cmdFromWake = extractCommandAfterWake(combined)
    if (finalChunk) {
      const piece = stripWakeFromChunk(finalChunk)
      beginRecording(piece || cmdFromWake || undefined)
      if ((piece || cmdFromWake || '').length >= MIN_COMMAND_LEN) {
        scheduleSilenceCheck()
      }
      return
    }

    beginRecording(cmdFromWake || undefined)
  }

  const attachHandlers = (r: SpeechRecognitionLike) => {
    r.onstart = () => {
      if (!active) return
      networkErrors = 0
      if (!recording) setStatus('waiting_wake')
    }

    r.onresult = (ev) => handleResult(ev)

    r.onerror = (ev) => {
      const code = ev.error
      if (code === 'aborted') return
      if (code === 'no-speech') {
        if (recording) {
          scheduleSilenceCheck()
        } else {
          scheduleListenRestart(500)
        }
        return
      }
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        fatalError = true
        active = false
        recording = false
        clearRecordTimers()
        setStatus('error')
        handlers.onError?.(
          'Нет доступа к распознаванию речи. Разрешите микрофон для сайта.',
        )
        return
      }
      if (code === 'network') {
        networkErrors += 1
        if (networkErrors >= 6) {
          fatalError = true
          active = false
          recording = false
          clearRecordTimers()
          setStatus('error')
          handlers.onError?.(
            'Нет связи с сервером распознавания Google. Проверьте интернет и прокси.',
          )
          return
        }
        scheduleListenRestart(1000)
        return
      }
      scheduleListenRestart(700)
    }

    r.onend = () => {
      if (!active || fatalError) {
        if (!active) setStatus('off')
        return
      }
      if (recording) {
        const merged = mergedCommand()
        if (merged.length >= MIN_COMMAND_LEN) {
          finishRecording('final')
        } else {
          recording = false
          clearRecordTimers()
          setStatus('waiting_wake')
        }
      }
      recognition = null
      scheduleListenRestart(400)
    }
  }

  const createRecognition = () => {
    if (!Ctor) return null
    const r = new Ctor()
    r.lang = 'ru-RU'
    r.continuous = true
    r.interimResults = true
    r.maxAlternatives = 1
    attachHandlers(r)
    return r
  }

  const startRecognition = (): boolean => {
    if (!active || fatalError) return false
    recognition = createRecognition()
    if (!recognition) return false
    try {
      recognition.start()
      return true
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      if (/already started/i.test(msg)) return true
      recognition = null
      return false
    }
  }

  const scheduleListenRestart = (delayMs: number) => {
    if (!active || fatalError) return
    clearRestart()
    restartTimer = setTimeout(() => {
      restartTimer = null
      if (!active || fatalError) return
      startRecognition()
    }, delayMs)
  }

  const openMicrophone = async (): Promise<boolean> => {
    if (!navigator.mediaDevices?.getUserMedia) return false
    try {
      releaseMic()
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
        },
        video: false,
      })
      return micStream.getAudioTracks().some((t) => t.readyState === 'live')
    } catch (e) {
      releaseMic()
      const err = e as DOMException
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        handlers.onError?.(
          'Микрофон заблокирован. Разрешите доступ для 127.0.0.1:8000 в настройках Chrome.',
        )
      } else if (err.name === 'NotFoundError') {
        handlers.onError?.('Микрофон не найден на компьютере.')
      } else {
        handlers.onError?.(err.message || 'Ошибка микрофона.')
      }
      return false
    }
  }

  return {
    async start() {
      if (!Ctor) {
        handlers.onError?.('Нужен Chrome или Edge с поддержкой голосового ввода.')
        return false
      }
      if (active) return true

      fatalError = false
      networkErrors = 0
      active = true
      recording = false
      commandParts = []
      clearRecordTimers()
      setStatus('starting')

      const micOk = await openMicrophone()
      if (!micOk) {
        active = false
        setStatus('error')
        return false
      }

      const started = startRecognition()
      if (!started) {
        scheduleListenRestart(300)
      }
      return true
    },

    stop() {
      active = false
      fatalError = false
      recording = false
      commandParts = []
      clearRestart()
      clearRecordTimers()
      if (recognition) {
        try {
          recognition.abort()
        } catch {
          try {
            recognition.stop()
          } catch {
            /* ignore */
          }
        }
        recognition = null
      }
      releaseMic()
      setStatus('off')
    },

    isActive: () => active,
    getStatus: () => status,
    hasMicrophoneStream: () =>
      !!micStream?.getAudioTracks().some((t) => t.readyState === 'live'),
  }
}
