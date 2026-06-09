import { ChevronDown, ChevronUp, Pin, Wifi, WifiOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { MemoryStoreBlock } from '@/components/memory/MemoryStoreBlock'
import { fetchMemory, fetchNetworkStatus } from '@/api/client'
import { cn } from '@/lib/utils'
import type { MemoryFileContent, MemoryStores } from '@/types'

const COLLAPSED_KEY = 'jarvis-pin-conscious-collapsed'
const EMBEDDED_COLLAPSED_KEY = 'jarvis-pin-conscious-embedded-collapsed'

interface ChatPinnedConsciousProps {
  memory: MemoryStores
  onMemoryChange?: () => void
  onSystemLog?: (text: string) => void
  /** Внутри поля ввода сообщения (composer). */
  embedded?: boolean
}

export function ChatPinnedConscious({
  memory,
  onMemoryChange,
  onSystemLog,
  embedded = false,
}: ChatPinnedConsciousProps) {
  const [local, setLocal] = useState(memory)
  const collapseKey = embedded ? EMBEDDED_COLLAPSED_KEY : COLLAPSED_KEY

  const [collapsed, setCollapsed] = useState(() => {
    try {
      const v = localStorage.getItem(collapseKey)
      if (v === null) return embedded ? false : true
      return v === '1'
    } catch {
      return embedded ? false : true
    }
  })
  const [viewer, setViewer] = useState<{
    file: MemoryFileContent
    sectionTitle: string
  } | null>(null)
  const [netOk, setNetOk] = useState<boolean | null>(null)

  useEffect(() => {
    setLocal(memory)
  }, [memory])

  useEffect(() => {
    let cancelled = false
    const poll = () => {
      void fetchNetworkStatus()
        .then((n) => {
          if (!cancelled) setNetOk(Boolean(n.internet_ok))
        })
        .catch(() => {
          if (!cancelled) setNetOk(null)
        })
    }
    poll()
    const id = window.setInterval(poll, 25_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  const toggleCollapsed = () => {
    setCollapsed((v) => {
      const next = !v
      try {
        localStorage.setItem(collapseKey, next ? '1' : '0')
      } catch {
        /* ignore */
      }
      return next
    })
  }

  const refresh = () => {
    void fetchMemory()
      .then((m) => {
        setLocal(m)
        onMemoryChange?.()
      })
      .catch(() => onMemoryChange?.())
  }

  const fileCount = local.conscious.length

  const panel = (
    <div
      className={cn(
        embedded
          ? 'w-full min-w-0 border-b border-border/60 pb-1.5'
          : 'overflow-hidden rounded-xl border border-primary/25 bg-card/90 shadow-sm ring-1 ring-primary/10',
      )}
    >
      <button
        type="button"
        onClick={toggleCollapsed}
        className={cn(
          'flex w-full flex-wrap items-center justify-between gap-2 text-left transition-colors',
          embedded
            ? 'rounded-md px-1 py-1 hover:bg-muted/40'
            : 'border-b border-primary/15 bg-primary/8 px-3 py-2 hover:bg-primary/12',
        )}
        aria-expanded={!collapsed}
      >
        <div className="flex min-w-0 items-center gap-1.5">
          <Pin
            className={cn(
              'shrink-0 text-primary',
              embedded ? 'h-3 w-3' : 'h-3.5 w-3.5',
            )}
          />
          <span
            className={cn(
              'font-semibold uppercase tracking-wide text-primary',
              embedded ? 'text-[9px]' : 'text-[10px]',
            )}
          >
            Закреп · Сознательное
          </span>
          {collapsed && fileCount > 0 && (
            <span className="truncate text-[9px] font-normal text-muted-foreground">
              · {fileCount} файл(ов)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'items-center gap-1 text-[9px] text-muted-foreground',
              embedded ? 'hidden sm:flex' : 'hidden sm:flex',
            )}
            title={
              netOk === false
                ? 'Нет выхода в интернет у Windows (прокси/VPN)'
                : 'Интернет Windows (не путать с установкой Chromium)'
            }
          >
            {netOk === false ? (
              <WifiOff className="h-3 w-3 text-amber-500" />
            ) : (
              <Wifi className="h-3 w-3 text-primary/80" />
            )}
            сеть
          </span>
          {collapsed ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </div>
      </button>
      <div
        className={cn(
          'grid transition-[grid-template-rows] duration-200 ease-out',
          collapsed ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]',
        )}
      >
        <div className="min-h-0 overflow-hidden">
          <div
            className={cn(
              embedded ? 'max-h-[120px] overflow-y-auto pt-1' : 'px-2 pb-2 pt-1.5',
            )}
          >
            <MemoryStoreBlock
              title="Сознательное"
              description={
                embedded
                  ? 'В каждом ответе Jarvis'
                  : 'Учитывается в каждом ответе Jarvis'
              }
              store="conscious"
              files={local.conscious}
              onRefresh={refresh}
              onLog={onSystemLog}
              onOpenFile={(f, t) => setViewer({ file: f, sectionTitle: t })}
              compact
              composerEmbed={embedded}
            />
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <>
      {embedded ? (
        panel
      ) : (
        <div className="shrink-0 border-b border-border/80 bg-background/95 backdrop-blur-sm">
          <div className="mx-auto w-full max-w-3xl px-4 py-2">{panel}</div>
        </div>
      )}

      <Dialog open={viewer != null} onOpenChange={(o) => !o && setViewer(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-hidden">
          <DialogHeader>
            <DialogTitle className="truncate text-sm">{viewer?.file.name}</DialogTitle>
            <DialogDescription className="text-xs">{viewer?.sectionTitle}</DialogDescription>
          </DialogHeader>
          <pre className="max-h-[60vh] overflow-auto rounded-md border bg-muted/30 p-3 font-mono text-xs whitespace-pre-wrap">
            {viewer?.file.content ?? ''}
          </pre>
        </DialogContent>
      </Dialog>
    </>
  )
}
