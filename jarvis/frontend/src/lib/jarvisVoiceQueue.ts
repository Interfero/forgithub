export interface QueuedVoiceCommand {
  id: number
  text: string
  at: number
}

const MAX_QUEUE = 5

export function createVoiceCommandQueue() {
  let seq = 0
  const items: QueuedVoiceCommand[] = []

  return {
    push(text: string): QueuedVoiceCommand {
      const cmd: QueuedVoiceCommand = {
        id: ++seq,
        text: text.trim(),
        at: Date.now(),
      }
      items.push(cmd)
      while (items.length > MAX_QUEUE) items.shift()
      return cmd
    },
    peek(): QueuedVoiceCommand | null {
      return items[0] ?? null
    },
    shift(): QueuedVoiceCommand | null {
      return items.shift() ?? null
    },
    size(): number {
      return items.length
    },
    clear() {
      items.length = 0
    },
    formatBatch(): string {
      if (items.length === 0) return ''
      if (items.length === 1) return items[0].text
      const lines = items.map((c, i) => `${i + 1}. ${c.text}`)
      return (
        `[Голос — ${items.length} фразы подряд]\n` +
        lines.join('\n') +
        '\n\nОтветь кратко на все пункты; если связь неясна — один уточняющий вопрос.'
      )
    },
    drainBatch(): string {
      const payload = this.formatBatch()
      items.length = 0
      return payload
    },
  }
}
