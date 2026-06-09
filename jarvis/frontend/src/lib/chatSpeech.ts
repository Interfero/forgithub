const API = import.meta.env.VITE_API_URL ?? ''

let speechQueue: Promise<void> = Promise.resolve()
let currentAudio: HTMLAudioElement | null = null
let playbackListeners: Array<(playing: boolean) => void> = []
let speechEnabled = true

export function onSpeechPlaybackChange(listener: (playing: boolean) => void): () => void {
  playbackListeners.push(listener)
  return () => {
    playbackListeners = playbackListeners.filter((l) => l !== listener)
  }
}

function notifyPlayback(playing: boolean) {
  for (const l of playbackListeners) {
    try {
      l(playing)
    } catch {
      /* ignore */
    }
  }
}

/** Включена ли озвучка (выкл при отключении голосового режима). */
export function setChatSpeechEnabled(enabled: boolean): void {
  speechEnabled = enabled
  if (!enabled) {
    stopChatSpeechPlayback()
  }
}

export function isChatSpeechEnabled(): boolean {
  return speechEnabled
}

export function unlockChatSpeechPlayback(): void {
  try {
    const a = new Audio(
      'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=',
    )
    a.volume = 0.001
    void a.play().catch(() => {})
  } catch {
    /* ignore */
  }
}

function stopCurrent(): void {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.currentTime = 0
    currentAudio = null
  }
}

export function stopChatSpeechPlayback(): void {
  stopCurrent()
  speechQueue = Promise.resolve()
  notifyPlayback(false)
}

import { stripDetailBlocksForSpeech } from '@/lib/speechText'

function plainTextForSpeech(text: string): string {
  return stripDetailBlocksForSpeech(text)
}

function queueSpeech(task: () => Promise<void>): void {
  if (!speechEnabled) return
  speechQueue = speechQueue.then(task).catch(() => {})
}

async function playAudioBlob(blob: Blob): Promise<boolean> {
  if (!speechEnabled || !blob.size) return false
  stopCurrent()
  unlockChatSpeechPlayback()
  const objectUrl = URL.createObjectURL(blob)
  const audio = new Audio(objectUrl)
  currentAudio = audio
  notifyPlayback(true)
  try {
    await audio.play()
  } catch {
    URL.revokeObjectURL(objectUrl)
    currentAudio = null
    notifyPlayback(false)
    return false
  }
  try {
    await new Promise<void>((resolve, reject) => {
      audio.onended = () => {
        URL.revokeObjectURL(objectUrl)
        if (currentAudio === audio) currentAudio = null
        resolve()
      }
      audio.onerror = () => {
        URL.revokeObjectURL(objectUrl)
        if (currentAudio === audio) currentAudio = null
        reject(new Error('playback_error'))
      }
    })
    return true
  } finally {
    notifyPlayback(false)
  }
}

async function playAudioUrl(audioUrl: string): Promise<boolean> {
  if (!speechEnabled) return false
  const url = audioUrl.startsWith('http') ? audioUrl : `${API}${audioUrl}`
  try {
    const res = await fetch(`${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`, {
      cache: 'no-store',
    })
    if (!res.ok) return false
    return playAudioBlob(await res.blob())
  } catch {
    return false
  }
}

async function synthesizeAndPlay(text: string): Promise<boolean> {
  if (!speechEnabled) return false
  const plain = plainTextForSpeech(text)
  if (!plain || plain.length < 2) return false

  try {
    const res = await fetch(`${API}/api/voice/speak`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: plain }),
    })
    if (!res.ok) return false
    const data = (await res.json()) as { audio_url?: string }
    if (!data.audio_url) return false
    return playAudioUrl(data.audio_url)
  } catch {
    return false
  }
}

/** Озвучить произвольный текст из чата (очередь, без зависаний). */
export function speakChatContent(
  text: string,
  preferredAudioUrl?: string | null,
  options?: { synthesizeFallback?: boolean },
): void {
  if (!speechEnabled) return
  const trimmed = text.trim()
  if (!trimmed) return
  const allowSynth = options?.synthesizeFallback !== false

  queueSpeech(async () => {
    if (preferredAudioUrl) {
      const ok = await playAudioUrl(preferredAudioUrl)
      if (ok) return
    }
    if (!allowSynth) return
    await synthesizeAndPlay(trimmed)
  })
}

/** Всё, что попало в чат текстом — user / assistant / system. */
export function speakChatMessage(
  content: string,
  preferredAudioUrl?: string | null,
  speechText?: string | null,
): void {
  const spoken = (speechText || '').trim() || content
  const onlySpeech = !!(speechText || '').trim()
  speakChatContent(spoken, preferredAudioUrl, {
    synthesizeFallback: !onlySpeech,
  })
}

/** @deprecated используйте speakChatContent */
export async function playAssistantReply(
  content: string,
  audioUrl?: string | null,
): Promise<void> {
  speakChatContent(content, audioUrl)
}

export async function speakChatText(text: string): Promise<boolean> {
  return synthesizeAndPlay(text)
}

export async function enqueueChatSpeech(audioUrl: string): Promise<boolean> {
  if (!speechEnabled) return false
  return new Promise((resolve) => {
    queueSpeech(async () => {
      resolve(await playAudioUrl(audioUrl))
    })
  })
}
