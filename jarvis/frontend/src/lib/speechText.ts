/**
 * Озвучка: блоки --- не читаются; ссылки убираются; числа — словами (на клиенте — упрощённо).
 */

const DETAIL_SPLIT = /(?:^|\n)\s*---+\s*(?:\n|$)/gm
const URL_RE =
  /(?:https?:\/\/|ftp:\/\/|www\.)[^\s\]\)<>"']+|(?<![@\w])[\w-]+\.(?:ru|com|org|net|io|dev|app|me|ua|by|kz)(?:\/[^\s\]\)<>"']*)?/gi

export function stripDetailBlocksForSpeech(text: string): string {
  const raw = text.trim()
  if (!raw) return ''
  const parts = raw.split(DETAIL_SPLIT).map((p) => p.trim())
  if (parts.length === 1) return prepareForSpeech(parts[0])
  const spoken = parts.filter((_, i) => i % 2 === 0).filter(Boolean)
  return prepareForSpeech(spoken.join('\n'))
}

function stripUrls(text: string): string {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(URL_RE, '')
    .replace(/\(\s*\)/g, '')
}

/** Упрощённая озвучка цифр на клиенте (полная — на backend через num2words). */
function numbersToWordsSimple(text: string): string {
  return text.replace(/\b\d+\b/g, (n) => {
    const x = Number(n)
    if (!Number.isFinite(x)) return n
    try {
      return new Intl.NumberFormat('ru-RU', { style: 'decimal' }).format(x)
    } catch {
      return n
    }
  })
}

function cleanForSpeech(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/#{1,6}\s*/g, '')
    .replace(/[🔊🔑⚠️❌✅📎🎙️📁📊🖼️⚙️💬🗑️✏️📥📱🟠]/gu, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function prepareForSpeech(text: string): string {
  return cleanForSpeech(numbersToWordsSimple(stripUrls(text)))
}

/** Короткая строка для озвучки + подробности между --- для экрана. */
export function formatChatMessage(spoken: string, detail?: string): string {
  const s = spoken.trim()
  const d = detail?.trim()
  if (!d) return s
  return `${s}\n\n---\n${d}\n---`
}
