import { Lock, Plus, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Hint } from '@/components/ui/hint'
import { deleteMemoryFile, fetchMemory, fetchMemoryFile, uploadMemoryFile } from '@/api/client'
import type { MemoryFile, MemoryFileContent, MemoryStores as MemoryStoresType } from '@/types'

interface MemoryStoresProps {
  memory: MemoryStoresType
  onChange: () => void
  onLog?: (text: string) => void
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  return `${Math.round(bytes / 1024)} KB`
}

/** Только бессознательное — базовые правила личности для всего приложения. */
export function MemoryStores({ memory, onChange, onLog }: MemoryStoresProps) {
  const [files, setFiles] = useState(memory.unconscious)
  const inputRef = useRef<HTMLInputElement>(null)
  const [viewer, setViewer] = useState<MemoryFileContent | null>(null)

  useEffect(() => {
    setFiles(memory.unconscious)
  }, [memory.unconscious])

  const refresh = () => {
    void fetchMemory()
      .then((m) => {
        setFiles(m.unconscious)
        onChange()
      })
      .catch(() => onChange())
  }

  useEffect(() => {
    void fetchMemory()
      .then((m) => setFiles(m.unconscious))
      .catch(() => {})
  }, [])

  return (
    <>
      <Hint text="Бессознательное — базовые правила поведения любой ИИ внутри приложения. Применяются во всех режимах чата.">
        <div className="rounded-md border border-border/60 bg-background/50 p-2">
          <p className="text-[11px] font-semibold text-foreground">Бессознательное</p>
          <p className="text-[10px] text-muted-foreground">
            Правила личности Jarvis (файл personality_rules.txt защищён от удаления)
          </p>
          <div className="mb-1.5 mt-1.5 max-h-[88px] space-y-0.5 overflow-y-auto">
            {files.length === 0 ? (
              <p className="text-[10px] italic text-muted-foreground">Нет файлов</p>
            ) : (
              files.map((f) => (
                <div
                  key={f.id}
                  className="flex items-center justify-between gap-1 rounded bg-muted/40 px-1.5 py-0.5 text-[10px]"
                >
                  <button
                    type="button"
                    className="truncate text-left text-primary hover:underline"
                    onClick={() => {
                      void fetchMemoryFile('unconscious', f.id)
                        .then(setViewer)
                        .catch(() => onLog?.(`⚠️ Не удалось открыть \`${f.name}\``))
                    }}
                  >
                    {f.name}
                    <span className="ml-1 text-muted-foreground">{formatSize(f.sizeBytes)}</span>
                  </button>
                  {f.protected ? (
                    <Lock className="h-3 w-3 text-muted-foreground" />
                  ) : (
                    <button
                      type="button"
                      className="text-destructive"
                      onClick={() => {
                        void deleteMemoryFile('unconscious', f.id).then(() => {
                          onLog?.(`📁 Бессознательное: удалён \`${f.name}\``)
                          refresh()
                        })
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".txt,.md,.json"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) {
                void uploadMemoryFile('unconscious', file).then(() => {
                  onLog?.(`📁 Бессознательное: добавлен \`${file.name}\``)
                  refresh()
                })
              }
              e.target.value = ''
            }}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-6 w-full gap-1 text-[10px]"
            onClick={() => inputRef.current?.click()}
          >
            <Plus className="h-3 w-3" />
            Добавить файл
          </Button>
        </div>
      </Hint>

      <Dialog open={viewer != null} onOpenChange={(o) => !o && setViewer(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-sm">{viewer?.name}</DialogTitle>
            <DialogDescription>Бессознательное</DialogDescription>
          </DialogHeader>
          <pre className="max-h-[60vh] overflow-auto rounded-md border bg-muted/30 p-3 font-mono text-xs whitespace-pre-wrap">
            {viewer?.content ?? ''}
          </pre>
        </DialogContent>
      </Dialog>
    </>
  )
}
