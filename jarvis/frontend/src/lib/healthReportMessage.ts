import type { Message } from '@/types'

export function createHealthReportMessage(content: string): Message {
  return {
    id: `health-${Date.now()}`,
    role: 'assistant',
    content,
    createdAt: new Date().toISOString(),
  }
}
