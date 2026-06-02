import { Bot, Info, User } from 'lucide-react'
import { ChatMarkdown } from '@/components/chat/ChatMarkdown'
import {
  extractAvitoReportHtml,
  isJarvisAvitoReport,
  JarvisAvitoReport,
} from '@/components/chat/JarvisAvitoReport'
import {
  extractHealthReportHtml,
  isJarvisHealthReport,
  JarvisHealthReport,
} from '@/components/chat/JarvisHealthReport'
import { cn } from '@/lib/utils'
import type { Message } from '@/types'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === 'system') {
    return (
      <div className="px-4 py-1.5">
        <div className="mx-auto flex max-w-2xl items-start gap-2 rounded-lg border border-amber-500/25 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600/80 dark:text-amber-400/80" />
          <div className="markdown-body min-w-0 flex-1 leading-relaxed">
            <ChatMarkdown content={message.content} />
          </div>
        </div>
      </div>
    )
  }

  const isUser = message.role === 'user'

  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-3',
        isUser ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-muted-foreground',
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div
        className={cn(
          'max-w-[min(720px,85%)] rounded-2xl px-4 py-2.5 text-sm shadow-sm',
          (isJarvisHealthReport(message.content) ||
            isJarvisAvitoReport(message.content)) &&
            'min-w-[min(100%,560px)]',
          isUser
            ? 'bg-primary text-primary-foreground rounded-tr-sm'
            : 'bg-card border border-border text-card-foreground rounded-tl-sm',
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        ) : isJarvisHealthReport(message.content) ? (
          <JarvisHealthReport html={extractHealthReportHtml(message.content)} />
        ) : isJarvisAvitoReport(message.content) ? (
          <JarvisAvitoReport html={extractAvitoReportHtml(message.content)} />
        ) : (
          <div className="markdown-body">
            <ChatMarkdown content={message.content} />
          </div>
        )}
      </div>
    </div>
  )
}
