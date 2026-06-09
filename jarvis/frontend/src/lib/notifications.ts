import { formatChatMessage } from '@/lib/speechText'

/** Важные уведомления попадают в чат, контекст LLM и озвучку. Служебные — только в индикаторы. */
export type NotifyImportance = 'important' | 'routine'

/** Короткая фраза для озвучки + подробности между --- (только на экране). */
export { formatChatMessage }

export function inferNotifyImportance(content: string): NotifyImportance {
  const t = content.trim()
  if (!t) return 'routine'
  if (/^❌|^⚠️|ошибк/i.test(t)) return 'important'
  if (/Backend недоступен|Нужен ключ|требует ключ|sk-…/i.test(t)) return 'important'
  if (/^🔑|^📁|^📊|^🎙️.*загружен|^📱.*на связи|^📱.*ошибка|^🟠.*ошибка/i.test(t)) {
    return 'important'
  }
  return 'routine'
}

export function isChatVisibleNotification(
  role: string,
  content: string,
  notifyLevel?: NotifyImportance,
): boolean {
  if (role !== 'system') return true
  const level = notifyLevel ?? inferNotifyImportance(content)
  return level === 'important'
}
