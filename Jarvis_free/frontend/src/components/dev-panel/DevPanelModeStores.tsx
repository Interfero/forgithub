import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { MemoryStoreBlock } from '@/components/memory/MemoryStoreBlock'
import { Hint } from '@/components/ui/hint'
import { cn } from '@/lib/utils'
import { fetchMemory } from '@/api/client'
import type { MemoryFileContent, MemoryStores } from '@/types'

const COLLAPSE_KEY = 'jarvis-dev-mode-training-expanded'

interface DevPanelModeStoresProps {
  memory: MemoryStores
  onMemoryChange?: () => void
  onLog?: (text: string) => void
}

/** Предобучение режимов — в панели разработчика; файлы на диске → Qwen при ответах. */
export function DevPanelModeStores({
  memory,
  onMemoryChange,
  onLog,
}: DevPanelModeStoresProps) {
  const [local, setLocal] = useState(memory)
  const [expanded, setExpanded] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) !== 'false'
    } catch {
      return true
    }
  })
  const [viewer, setViewer] = useState<{
    file: MemoryFileContent
    sectionTitle: string
  } | null>(null)

  useEffect(() => {
    setLocal(memory)
  }, [memory])

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, String(expanded))
    } catch {
      /* ignore */
    }
  }, [expanded])

  const refresh = () => {
    void fetchMemory()
      .then((m) => {
        setLocal(m)
        onMemoryChange?.()
      })
      .catch(() => onMemoryChange?.())
  }

  const fileCount = local.modeAccountant.length + local.modeMarketer.length

  return (
    <>
      <div className="rounded-md border border-border/60 bg-background/40">
        <Hint text="Тексты .txt/.md/.json для режимов «Бухгалтер» и «Маркетолог». Сохраняются в backend/data/memory/ и подмешиваются в Qwen 2.5 14B при ответах (в т.ч. в exe без этой панели).">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex w-full items-center gap-2 px-2 py-1.5 text-left transition-colors hover:bg-muted/30"
            aria-expanded={expanded}
          >
            {expanded ? (
              <ChevronUp className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            )}
            <span className="text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
              Предобучение режимов
            </span>
            {!expanded && fileCount > 0 && (
              <span className="text-[9px] text-primary">({fileCount} файлов)</span>
            )}
            <span className="ml-auto text-[9px] text-muted-foreground">
              {expanded ? 'Свернуть' : 'Развернуть'}
            </span>
          </button>
        </Hint>

        <div
          className={cn(
            'grid transition-[grid-template-rows] duration-200 ease-out',
            expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
          )}
        >
          <div className="min-h-0 overflow-hidden">
            <div className="space-y-2 border-t border-border/40 px-2 pb-2 pt-2">
              <p className="text-[10px] text-muted-foreground">
                Файлы → <code className="rounded bg-muted px-0.5">backend/data/memory/modes/</code>
                {' '}
                и jarvis.db. Qwen читает их при каждом локальном ответе в активном режиме.
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                <MemoryStoreBlock
                  title="Бухгалтер + Юрист"
                  description="Файлы режима бухгалтера"
                  store="mode-accountant"
                  files={local.modeAccountant}
                  onRefresh={refresh}
                  onLog={onLog}
                  onOpenFile={(f, t) => setViewer({ file: f, sectionTitle: t })}
                  compact
                />
                <MemoryStoreBlock
                  title="Маркетолог+Дизайнер"
                  description="Маркетинг, копирайт, дизайн-брифы"
                  store="mode-marketer"
                  files={local.modeMarketer}
                  onRefresh={refresh}
                  onLog={onLog}
                  onOpenFile={(f, t) => setViewer({ file: f, sectionTitle: t })}
                  compact
                />
              </div>
            </div>
          </div>
        </div>
      </div>

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
