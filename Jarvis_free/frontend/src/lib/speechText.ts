/**
 * Озвучка: между --- … --- только текст для экрана (не читается вслух).
 */

const DETAIL_SPLIT = /(?:^|\n)\s*---+\s*(?:\n|$)/gm

export function stripDetailBlocksForSpeech(text: string): string {
  const raw = text.trim()
  if (!raw) return ''
  const parts = raw.split(DETAIL_SPLIT).map((p) => p.trim())
  if (parts.length === 1) return cleanForSpeech(parts[0])
  const spoken = parts.filter((_, i) => i % 2 === 0).filter(Boolean)
  return cleanForSpeech(spoken.join('\n'))
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

/** Короткая строка для озвучки + подробности между --- для экрана. */
export function formatChatMessage(spoken: string, detail?: string): string {
  const s = spoken.trim()
  const d = detail?.trim()
  if (!d) return s
  return `${s}\n\n---\n${d}\n---`
}
