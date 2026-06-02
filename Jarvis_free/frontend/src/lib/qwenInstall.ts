import {
  fetchQwenDownloadProgress,
  startQwenModelDownload,
  type QwenDownloadProgress,
} from '@/api/client'
import type { LocalQwenState } from '@/types'

export type QwenDownloadResult =
  | { kind: 'already_installed' }
  | { kind: 'in_progress' }
  | { kind: 'started' }
  | { kind: 'error'; message: string }

export type { QwenDownloadProgress }

/** Запуск скачивания GGUF Qwen 2.5 14B внутрь Jarvis (~9 ГБ). */
export async function requestQwenModelDownload(
  qwen: LocalQwenState,
  force = false,
): Promise<QwenDownloadResult> {
  if (qwen.filesPresent && !force) {
    return { kind: 'already_installed' }
  }
  if (qwen.downloadPhase === 'downloading') {
    return { kind: 'in_progress' }
  }
  try {
    const res = await startQwenModelDownload(force)
    if (res.skipped && res.already_installed) {
      return { kind: 'already_installed' }
    }
    if (res.skipped && (res.in_progress || res.download_phase === 'downloading')) {
      return { kind: 'in_progress' }
    }
    if (res.ok === false) {
      return {
        kind: 'error',
        message: res.message || res.download_message || 'Сервер не запустил загрузку',
      }
    }
    return { kind: 'started' }
  } catch (e) {
    const raw = e instanceof Error ? e.message : String(e)
    if (/404|Not Found/i.test(raw)) {
      return {
        kind: 'error',
        message:
          'На сервере нет API загрузки. Перезапустите Jarvis (restart.bat) и обновите страницу (Ctrl+F5).',
      }
    }
    if (/HTML|не JSON/i.test(raw)) {
      return { kind: 'error', message: raw }
    }
    if (/Таймаут|abort|fetch|Failed to fetch/i.test(raw)) {
      return {
        kind: 'error',
        message: 'Нет связи с backend — запустите start.bat и откройте http://127.0.0.1:8001/',
      }
    }
    return {
      kind: 'error',
      message: raw || 'Не удалось начать загрузку',
    }
  }
}

export { fetchQwenDownloadProgress }
