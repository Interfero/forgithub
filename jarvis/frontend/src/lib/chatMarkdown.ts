/**
 * Подготовка markdown ответа Jarvis для react-markdown (абзацы, списки, медиа).
 */

export function resolveChatMediaUrl(src: string): string {
  const raw = (src || '').trim()
  if (!raw) return ''
  if (/^https?:\/\//i.test(raw) || raw.startsWith('data:')) return raw
  if (raw.startsWith('/api/')) {
    if (typeof window !== 'undefined' && window.location?.origin) {
      return `${window.location.origin}${raw}`
    }
    return raw
  }
  return raw
}

/** GFM: абзацы — через пустую строку; списки — с переносом перед пунктом. */
export function preprocessChatMarkdown(content: string): string {
  let s = (content || '').replace(/\r\n/g, '\n').trim()
  if (
    !s ||
    s.includes('<!-- jarvis-health-report -->') ||
    s.includes('<!-- jarvis-avito-report -->')
  ) {
    return s
  }

  s = s.replace(/\n{3,}/g, '\n\n')

  if (!s.includes('\n\n') && s.length > 180) {
    s = s.replace(/(?<=[.!?…])\s+(?=[А-ЯA-Z«"])/g, '\n\n')
  }

  s = s.replace(/(?<!\n)(\#{2,3}\s)/g, '\n\n$1')
  s = s.replace(/(?<!\n)(\d{1,2}\.\s+)/g, '\n\n$1')
  s = s.replace(/(?<=[.!?])\s+(?=-\s)/g, '\n\n')
  s = s.replace(/(?<=[.!?])\s+(?=•\s)/g, '\n\n')

  return s.replace(/\n{3,}/g, '\n\n').trim()
}
