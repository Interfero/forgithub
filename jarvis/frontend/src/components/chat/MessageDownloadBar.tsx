import { Download } from 'lucide-react'
import { useMemo } from 'react'
import { Hint } from '@/components/ui/hint'
import { Button } from '@/components/ui/button'
import { resolveChatMediaUrl } from '@/lib/chatMarkdown'

interface MessageDownloadBarProps {
  content: string
  role: 'user' | 'assistant' | 'system'
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function extractImageUrls(content: string): string[] {
  const urls: string[] = []
  const re = /!\[[^\]]*\]\(([^)]+)\)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(content)) !== null) {
    const raw = (m[1] || '').trim()
    if (raw) urls.push(resolveChatMediaUrl(raw))
  }
  return urls
}

export function MessageDownloadBar({ content, role }: MessageDownloadBarProps) {
  const imageUrls = useMemo(() => extractImageUrls(content), [content])
  const text = (content || '').trim()
  if (!text && imageUrls.length === 0) return null

  const baseName = role === 'user' ? 'jarvis-user' : 'jarvis-reply'

  return (
    <div className="mt-2 flex flex-wrap gap-1 border-t border-border/50 pt-2">
      {text ? (
        <Hint text="Скачать текст сообщения как .txt">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 gap-1 text-[10px] transition-transform hover:scale-[1.03]"
            onClick={() => {
              downloadBlob(
                `${baseName}-${Date.now()}.txt`,
                new Blob([text], { type: 'text/plain;charset=utf-8' }),
              )
            }}
          >
            <Download className="h-3 w-3" />
            Текст
          </Button>
        </Hint>
      ) : null}
      {imageUrls.map((url, idx) => (
        <Hint key={`${url}-${idx}`} text="Скачать изображение из ответа">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 gap-1 text-[10px] transition-transform hover:scale-[1.03]"
            onClick={() => {
              const a = document.createElement('a')
              a.href = url
              a.download = `${baseName}-image-${idx + 1}${url.includes('.png') ? '.png' : '.jpg'}`
              a.target = '_blank'
              a.rel = 'noopener'
              a.click()
            }}
          >
            <Download className="h-3 w-3" />
            Картинка {imageUrls.length > 1 ? idx + 1 : ''}
          </Button>
        </Hint>
      ))}
    </div>
  )
}
