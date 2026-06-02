import { Children, isValidElement, type ReactElement, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChartBlock } from '@/components/chat/ChartBlock'
import { MermaidBlock } from '@/components/chat/MermaidBlock'
import {
  preprocessChatMarkdown,
  resolveChatMediaUrl,
} from '@/lib/chatMarkdown'

interface ChatMarkdownProps {
  content: string
}

function codeTextFromPre(children: ReactNode): { className: string; text: string } {
  const child = Children.only(children)
  if (!isValidElement(child)) {
    return { className: '', text: '' }
  }
  const el = child as ReactElement<{ className?: string; children?: ReactNode }>
  return {
    className: el.props.className ?? '',
    text: String(el.props.children ?? '').replace(/\n$/, ''),
  }
}

const markdownComponents: Components = {
  table: ({ children }) => (
    <div className="jarvis-md-table-wrap my-3 overflow-x-auto">
      <table>{children}</table>
    </div>
  ),
  p: ({ children }) => <p className="jarvis-md-p">{children}</p>,
  img: ({ src, alt, title }) => {
    const resolved = resolveChatMediaUrl(src ?? '')
    if (!resolved) return null
    const caption = (title || alt || '').trim()
    const isIcq = resolved.includes('/api/icq-smileys/')
    if (isIcq) {
      return (
        <img
          src={resolved}
          alt={caption || 'ICQ'}
          title={caption || undefined}
          className="jarvis-icq-smiley"
          loading="lazy"
        />
      )
    }
    return (
      <figure className="jarvis-chat-figure my-3 max-w-full">
        <img
          src={resolved}
          alt={caption || 'Сгенерировано Jarvis'}
          title={caption || undefined}
          className="jarvis-chat-image max-h-[min(70vh,520px)] w-auto max-w-full rounded-lg border border-border object-contain shadow-sm"
          loading="lazy"
        />
        {caption && caption !== 'Сгенерировано' ? (
          <figcaption className="mt-1.5 text-xs text-muted-foreground">{caption}</figcaption>
        ) : null}
      </figure>
    )
  },
  a: ({ href, children }) => {
    const url = resolveChatMediaUrl(href ?? '')
    if (url.includes('/api/videos/')) {
      return (
        <figure className="jarvis-chat-figure my-3 max-w-full">
          <video
            src={url}
            controls
            className="jarvis-chat-video max-h-[min(70vh,520px)] w-full max-w-full rounded-lg border border-border"
            preload="metadata"
          />
          <figcaption className="mt-1.5 text-xs text-muted-foreground">
            {typeof children === 'string' ? children : 'Сгенерировано видео'}
          </figcaption>
        </figure>
      )
    }
    return (
      <a href={url} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    )
  },
  pre: ({ children }) => {
    const { className, text } = codeTextFromPre(children)
    const lang = /language-([\w-]+)/.exec(className)?.[1]?.toLowerCase()

    if (lang === 'mermaid') {
      return <MermaidBlock chart={text} />
    }
    if (lang === 'chart' || lang === 'json-chart') {
      return <ChartBlock source={text} />
    }

    return (
      <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
        <code className={className}>{text}</code>
      </pre>
    )
  },
  code: ({ className, children }) => (
    <code className={className}>{children}</code>
  ),
}

export function ChatMarkdown({ content }: ChatMarkdownProps) {
  const prepared = preprocessChatMarkdown(content)
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {prepared}
    </ReactMarkdown>
  )
}
