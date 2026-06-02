import { Lock, Plus, Trash2 } from 'lucide-react'
import { useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Hint } from '@/components/ui/hint'
import { cn } from '@/lib/utils'
import { deleteMemoryFile, fetchMemoryFile, uploadMemoryFile } from '@/api/client'
import type { MemoryFile, MemoryFileContent, MemoryStoreId } from '@/types'

const STORE_HINTS: Record<string, string> = {
  conscious:
    'Сознательное — ваши личные настройки и справочники. Учитываются при каждом ответе ИИ в стандартном чате.',
  'mode-accountant':
    'Предобучение режима «Бухгалтер + Юрист»: шаблоны, нормы, ваши заметки по учёту и праву.',
  'mode-marketer':
    'Предобучение «Маркетолог+Дизайнер»: брендбук, тональность, УТП, примеры креативов.',
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  return `${Math.round(bytes / 1024)} KB`
}

export interface MemoryStoreBlockProps {
  title: string
  description: string
  store: MemoryStoreId
  files: MemoryFile[]
  onRefresh: () => void
  onLog?: (text: string) => void
  onOpenFile: (file: MemoryFileContent, sectionTitle: string) => void
  compact?: boolean
  /** Ещё компактнее — внутри поля ввода чата. */
  composerEmbed?: boolean
}

export function MemoryStoreBlock({
  title,
  description,
  store,
  files,
  onRefresh,
  onLog,
  onOpenFile,
  compact,
  composerEmbed,
}: MemoryStoreBlockProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const hint = STORE_HINTS[store] ?? description

  return (
    <Hint text={hint}>
      <div
        className={
          composerEmbed
            ? 'rounded-md bg-muted/25 px-1.5 py-1'
            : compact
              ? 'rounded-md border border-border/60 bg-background/50 p-2'
              : 'rounded-lg border border-border/80 bg-muted/15 p-3'
        }
      >
        <p
          className={
            composerEmbed
              ? 'text-[10px] font-semibold text-foreground'
              : compact
                ? 'text-[11px] font-semibold text-foreground'
                : 'text-sm font-medium text-foreground'
          }
        >
          {title}
        </p>
        <p
          className={cn(
            'text-muted-foreground',
            composerEmbed ? 'text-[9px]' : 'mt-0.5 text-[10px]',
          )}
        >
          {description}
        </p>
        <div
          className={
            composerEmbed
              ? 'mb-1 mt-1 max-h-[52px] space-y-0.5 overflow-y-auto'
              : compact
                ? 'mb-1.5 mt-1.5 max-h-[88px] space-y-0.5 overflow-y-auto'
                : 'mb-2 mt-2 max-h-[100px] space-y-0.5 overflow-y-auto'
          }
        >
          {files.length === 0 ? (
            <p className="text-[10px] italic text-muted-foreground">
              Нет файлов (.txt, .md, .json)
            </p>
          ) : (
            files.map((f) => (
              <div
                key={f.id}
                className="flex items-center justify-between gap-1 rounded bg-muted/40 px-1.5 py-0.5 text-[10px]"
              >
                <button
                  type="button"
                  className="min-w-0 truncate text-left text-primary hover:underline"
                  onClick={() => {
                    void fetchMemoryFile(store, f.id)
                      .then((c) => onOpenFile(c, title))
                      .catch(() => onLog?.(`⚠️ Не удалось открыть \`${f.name}\``))
                  }}
                >
                  {f.name}
                  <span className="ml-1 text-muted-foreground">{formatSize(f.sizeBytes)}</span>
                </button>
                {f.protected ? (
                  <Lock className="h-3 w-3 shrink-0 text-muted-foreground" />
                ) : (
                  <button
                    type="button"
                    className="text-destructive"
                    onClick={() => {
                      void deleteMemoryFile(store, f.id).then(() => {
                        onLog?.(`📁 **${title}**: удалён \`${f.name}\``)
                        onRefresh()
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
              void uploadMemoryFile(store, file).then(() => {
                onLog?.(`📁 **${title}**: добавлен \`${file.name}\``)
                onRefresh()
              })
            }
            e.target.value = ''
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={
            composerEmbed
              ? 'h-5 w-full gap-1 text-[9px]'
              : compact
                ? 'h-6 w-full gap-1 text-[10px]'
                : 'h-7 w-full gap-1 text-[10px]'
          }
          onClick={() => inputRef.current?.click()}
        >
          <Plus className="h-3 w-3" />
          Добавить файл
        </Button>
      </div>
    </Hint>
  )
}
