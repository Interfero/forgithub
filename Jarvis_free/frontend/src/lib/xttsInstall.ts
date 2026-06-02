import { downloadJarvisVoice, fetchXttsStatus } from '@/api/client'
import type { XttsStatus } from '@/types'

export type XttsDownloadResult =
  | { kind: 'already_installed'; status: XttsStatus }
  | { kind: 'in_progress'; status: XttsStatus }
  | { kind: 'started'; status: XttsStatus }
  | { kind: 'blocked'; status: XttsStatus; reason: string }
  | { kind: 'error'; message: string }

/** Проверка перед «Докачать библиотеки» — не запускать pip, если TTS уже установлен. */
export async function requestXttsInstall(): Promise<XttsDownloadResult> {
  const current = await fetchXttsStatus()
  if (current.pythonOkForXtts === false) {
    return { kind: 'blocked', status: current, reason: current.message }
  }
  if (current.importable || current.status === 'ready') {
    return { kind: 'already_installed', status: current }
  }
  if (
    current.status === 'installing_deps' ||
    current.status === 'downloading_model'
  ) {
    return { kind: 'in_progress', status: current }
  }
  try {
    await downloadJarvisVoice()
    const st = await fetchXttsStatus()
    return { kind: 'started', status: st }
  } catch (e) {
    return {
      kind: 'error',
      message: e instanceof Error ? e.message : 'Ошибка загрузки',
    }
  }
}
