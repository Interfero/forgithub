import { useCallback, useEffect, useState } from 'react'
import { Download, Loader2, Search, Trash2 } from 'lucide-react'
import {
  deleteHfSkill,
  downloadHfSkill,
  fetchHfInstalled,
  fetchHfStatus,
  searchHfHub,
  setHfSkillEnabled,
} from '@/api/client'
import { Hint } from '@/components/ui/hint'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface HfSkillRow {
  id: string
  repo_id: string
  repo_type: string
  label: string
  integration: string
  size_bytes: number
  enabled: boolean
}

interface HfSearchItem {
  repo_id: string
  downloads?: number | null
  likes?: number | null
  jarvis_download_bytes?: number
  jarvis_download_files?: number
  repo_total_bytes?: number
  main_file_bytes?: number
  main_file_name?: string | null
}

function formatBytes(bytes?: number | null): string {
  if (bytes == null || bytes <= 0) return '—'
  if (bytes >= 1024 ** 3) return `~${(bytes / 1024 ** 3).toFixed(1)} ГБ`
  if (bytes >= 1024 ** 2) return `~${Math.round(bytes / 1024 ** 2)} МБ`
  if (bytes >= 1024) return `~${Math.round(bytes / 1024)} КБ`
  return `~${bytes} Б`
}

function sizeHintText(item: HfSearchItem): string {
  const parts: string[] = []
  if (item.main_file_name && item.main_file_bytes) {
    parts.push(`Главный файл: ${item.main_file_name} (${formatBytes(item.main_file_bytes)})`)
  }
  if (item.repo_total_bytes) {
    parts.push(`Весь репозиторий: ${formatBytes(item.repo_total_bytes)}`)
  }
  if (item.jarvis_download_bytes != null && item.jarvis_download_files) {
    parts.push(
      `Jarvis скачает ${item.jarvis_download_files} файлов: ${formatBytes(item.jarvis_download_bytes)}`,
    )
  }
  return parts.join('. ') || 'Размер репозитория на Hugging Face Hub'
}

function primarySizeLabel(item: HfSearchItem): string {
  if (item.main_file_bytes) return formatBytes(item.main_file_bytes)
  if (item.repo_total_bytes) return formatBytes(item.repo_total_bytes)
  return '—'
}

interface HfSkillsPanelProps {
  onSystemLog?: (text: string) => void
}

const REPO_TYPE_HINTS: Record<'model' | 'dataset' | 'space', string> = {
  model: 'Модели (GGUF, LoRA, transformers)',
  dataset: 'Датасеты для RAG и обучения',
  space: 'Spaces — демо-приложения на Hub',
}

export function HfSkillsPanel({ onSystemLog }: HfSkillsPanelProps) {
  const [query, setQuery] = useState('')
  const [repoType, setRepoType] = useState<'model' | 'dataset' | 'space'>('model')
  const [tokenOk, setTokenOk] = useState(false)
  const [searching, setSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searchMode, setSearchMode] = useState<'exact' | 'multi_term' | 'empty' | null>(null)
  const [searchTerms, setSearchTerms] = useState<string[]>([])
  const [downloading, setDownloading] = useState<string | null>(null)
  const [downloadPct, setDownloadPct] = useState(0)
  const [results, setResults] = useState<HfSearchItem[]>([])
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null)
  const [installed, setInstalled] = useState<HfSkillRow[]>([])

  const refreshInstalled = useCallback(async () => {
    try {
      const d = await fetchHfInstalled()
      setInstalled(d.skills as HfSkillRow[])
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    fetchHfStatus()
      .then((s) => setTokenOk(s.tokenConfigured))
      .catch(() => setTokenOk(false))
    void refreshInstalled()
  }, [refreshInstalled])

  const handleSearch = async () => {
    const q = query.trim()
    if (q.length < 2) {
      setSearchError('Введите минимум 2 символа для поиска.')
      setHasSearched(true)
      return
    }
    if (!tokenOk) {
      setSearchError('Сначала добавьте Read-токен в backend/config/huggingface.key')
      setHasSearched(true)
      return
    }

    setSearching(true)
    setSearchError(null)
    setSearchMode(null)
    setSearchTerms([])
    setHasSearched(true)
    setSelectedRepoId(null)
    try {
      const d = await searchHfHub(q, repoType)
      setResults(d.items)
      setSearchMode(d.searchMode ?? (d.items.length ? 'exact' : 'empty'))
      setSearchTerms(d.terms ?? [])
      if (d.items.length > 0) {
        setSelectedRepoId(d.items[0].repo_id)
      }
      const modeNote =
        d.searchMode === 'multi_term'
          ? ` (по словам: ${(d.terms ?? []).join(', ')})`
          : ''
      onSystemLog?.(`🔎 HF: найдено ${d.items.length} репозиториев (${repoType})${modeNote}`)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'ошибка поиска'
      setSearchError(msg)
      setResults([])
      onSystemLog?.(`❌ HF поиск: ${msg}`)
    } finally {
      setSearching(false)
    }
  }

  const handleDownload = async (repoId: string) => {
    setDownloading(repoId)
    setDownloadPct(8)
    const tick = window.setInterval(() => {
      setDownloadPct((p) => (p >= 92 ? p : p + 4))
    }, 400)
    try {
      const m = await downloadHfSkill({ repoId, repoType })
      setDownloadPct(100)
      onSystemLog?.(
        `✅ Навык установлен: ${m.label ?? m.repo_id} (${Math.round((m.size_bytes ?? 0) / (1024 * 1024))} МБ)`,
      )
      await refreshInstalled()
    } catch (e) {
      onSystemLog?.(`❌ HF скачивание: ${e instanceof Error ? e.message : 'ошибка'}`)
    } finally {
      window.clearInterval(tick)
      setDownloading(null)
      setDownloadPct(0)
    }
  }

  const selectedResult = results.find((r) => r.repo_id === selectedRepoId) ?? null

  return (
    <div className="space-y-4 text-xs">
      {!tokenOk && (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-amber-800 dark:text-amber-200">
          Положите Read-токен в <code className="rounded bg-muted px-1">backend/config/huggingface.key</code>
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {(['model', 'dataset', 'space'] as const).map((t) => (
          <Hint key={t} text={REPO_TYPE_HINTS[t]}>
            <Button
              type="button"
              size="sm"
              variant={repoType === t ? 'default' : 'outline'}
              className="h-7 text-[11px] transition-transform hover:scale-[1.02]"
              onClick={() => setRepoType(t)}
            >
              {t}
            </Button>
          </Hint>
        ))}
      </div>

      <div className="flex gap-2">
        <Hint text="Поиск на huggingface.co — нужен токен Read">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='Например: sentence-transformers russian, qwen gguf'
            className="h-8 text-xs"
            onKeyDown={(e) => e.key === 'Enter' && void handleSearch()}
          />
        </Hint>
        <Hint text="Искать репозитории на Hub">
          <Button
            type="button"
            size="sm"
            className="h-8 gap-1 transition-all hover:scale-[1.03]"
            disabled={searching}
            onClick={() => void handleSearch()}
          >
            {searching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            Найти
          </Button>
        </Hint>
      </div>

      <section
        aria-label="Результаты поиска Hugging Face"
        className="rounded-lg border-2 border-primary/25 bg-muted/20 p-3 ring-1 ring-border/80"
      >
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-foreground">
            Результаты поиска
          </p>
          {searching ? (
            <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Ищем на Hub и считаем размеры…
            </span>
          ) : hasSearched ? (
            <span className="text-[10px] text-muted-foreground">
              {results.length > 0
                ? `Найдено: ${results.length} · тип: ${repoType}${
                    searchMode === 'multi_term'
                      ? ` · по словам: ${searchTerms.join(', ')}`
                      : ''
                  }`
                : 'Совпадений нет'}
            </span>
          ) : null}
        </div>

        <div className="min-h-[140px] rounded-md border border-border/70 bg-background/60">
          {!hasSearched && !searching && (
            <p className="px-3 py-6 text-center text-[11px] text-muted-foreground">
              Введите запрос и нажмите «Найти». Hub не понимает длинные фразы целиком — Jarvis
              автоматически ищет по каждому слову и сортирует по релевантности.
            </p>
          )}

          {searchMode === 'multi_term' && results.length > 0 && (
            <p className="border-b border-primary/20 bg-primary/5 px-3 py-2 text-[10px] text-muted-foreground">
              Точной фразы «{query.trim()}» на Hub нет. Показаны результаты по словам:{' '}
              <strong className="text-foreground">{searchTerms.join(', ')}</strong>.
            </p>
          )}

          {searchError && (
            <p className="border-b border-destructive/30 bg-destructive/10 px-3 py-2 text-[11px] text-destructive">
              {searchError}
            </p>
          )}

          {hasSearched && !searching && !searchError && results.length === 0 && (
            <p className="px-3 py-6 text-center text-[11px] text-muted-foreground">
              По запросу «{query.trim()}» в категории <strong className="text-foreground">{repoType}</strong>{' '}
              ничего не найдено. Попробуйте одно слово, например{' '}
              <strong className="text-foreground">sentence-transformers</strong> или{' '}
              <strong className="text-foreground">russian</strong>.
            </p>
          )}

          {results.length > 0 && (
            <ul className="max-h-48 divide-y divide-border/60 overflow-y-auto">
              {results.map((r) => {
                const selected = selectedRepoId === r.repo_id
                return (
                  <li key={r.repo_id}>
                    <button
                      type="button"
                      className={cn(
                        'flex w-full items-center justify-between gap-2 px-3 py-2 text-left transition-colors',
                        selected ? 'bg-primary/12' : 'hover:bg-muted/40',
                      )}
                      onClick={() => setSelectedRepoId(r.repo_id)}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-mono text-[10px] text-foreground">
                          {r.repo_id}
                        </span>
                        {(r.downloads != null ||
                          r.likes != null ||
                          r.repo_total_bytes ||
                          r.main_file_bytes) && (
                          <span className="text-[10px] text-muted-foreground">
                            {r.downloads != null ? `↓ ${r.downloads.toLocaleString('ru-RU')}` : ''}
                            {r.downloads != null && r.likes != null ? ' · ' : ''}
                            {r.likes != null ? `♥ ${r.likes.toLocaleString('ru-RU')}` : ''}
                            {(r.downloads != null || r.likes != null) &&
                            (r.repo_total_bytes || r.main_file_bytes)
                              ? ' · '
                              : ''}
                            <Hint text={sizeHintText(r)}>
                              <span className="font-medium text-cyan-700 dark:text-cyan-300">
                                {primarySizeLabel(r)}
                                {r.repo_total_bytes &&
                                r.main_file_bytes &&
                                r.repo_total_bytes > r.main_file_bytes * 1.2
                                  ? ` · репо ${formatBytes(r.repo_total_bytes)}`
                                  : ''}
                              </span>
                            </Hint>
                          </span>
                        )}
                      </span>
                      <Hint text={`${sizeHintText(r)}. Скачать в data/hf_skills/`}>
                        <Button
                          type="button"
                          size="sm"
                          variant={selected ? 'default' : 'secondary'}
                          className="relative h-7 shrink-0 overflow-hidden text-[10px] transition-transform hover:scale-[1.04]"
                          disabled={!!downloading || !tokenOk}
                          onClick={(e) => {
                            e.stopPropagation()
                            void handleDownload(r.repo_id)
                          }}
                        >
                          {downloading === r.repo_id && (
                            <span
                              className="absolute inset-y-0 left-0 bg-primary/30 transition-all duration-300"
                              style={{ width: `${downloadPct}%` }}
                            />
                          )}
                          <span className="relative flex items-center gap-1">
                            {downloading === r.repo_id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Download className="h-3 w-3" />
                            )}
                            Скачать
                          </span>
                        </Button>
                      </Hint>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {selectedResult && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
            <div className="min-w-0">
              <p className="truncate font-mono text-[10px]">{selectedResult.repo_id}</p>
              <Hint text={sizeHintText(selectedResult)}>
                <p className="text-[10px] text-cyan-700 dark:text-cyan-300">
                  {primarySizeLabel(selectedResult)}
                  {selectedResult.repo_total_bytes &&
                  selectedResult.main_file_bytes &&
                  selectedResult.repo_total_bytes > selectedResult.main_file_bytes * 1.2
                    ? ` · репо ${formatBytes(selectedResult.repo_total_bytes)}`
                    : ''}
                  {selectedResult.jarvis_download_bytes != null && selectedResult.jarvis_download_files
                    ? ` · Jarvis: ${formatBytes(selectedResult.jarvis_download_bytes)}`
                    : ''}
                </p>
              </Hint>
            </div>
            <Hint text={`${sizeHintText(selectedResult)}. Скачать в Jarvis`}>
              <Button
                type="button"
                size="sm"
                className="relative h-8 min-w-[120px] overflow-hidden transition-transform hover:scale-[1.03]"
                disabled={!!downloading || !tokenOk}
                onClick={() => void handleDownload(selectedResult.repo_id)}
              >
                {downloading === selectedResult.repo_id && (
                  <span
                    className="absolute inset-y-0 left-0 bg-primary/35 transition-all duration-300"
                    style={{ width: `${downloadPct}%` }}
                  />
                )}
                <span className="relative flex items-center gap-1.5">
                  {downloading === selectedResult.repo_id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Download className="h-3.5 w-3.5" />
                  )}
                  Скачать
                </span>
              </Button>
            </Hint>
          </div>
        )}
      </section>

      <div>
        <p className="mb-2 font-medium text-foreground">Установлено в Jarvis</p>
        {installed.length === 0 ? (
          <p className="text-muted-foreground">Пока пусто — найдите навык и нажмите «Скачать».</p>
        ) : (
          <ul className="space-y-2">
            {installed.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/60 px-2 py-1.5"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{s.label || s.repo_id}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {s.integration} · {Math.round((s.size_bytes || 0) / (1024 * 1024))} МБ
                  </p>
                </div>
                <div className="flex gap-1">
                  <Hint text={s.enabled ? 'Выключить навык' : 'Включить навык'}>
                    <Button
                      type="button"
                      size="sm"
                      variant={s.enabled ? 'default' : 'outline'}
                      className="h-7 text-[10px]"
                      onClick={() =>
                        void setHfSkillEnabled(s.id, !s.enabled).then(refreshInstalled)
                      }
                    >
                      {s.enabled ? 'Вкл' : 'Выкл'}
                    </Button>
                  </Hint>
                  <Hint text="Удалить с диска">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 text-destructive"
                      onClick={() =>
                        void deleteHfSkill(s.id).then(() => {
                          onSystemLog?.(`🗑 Удалён навык ${s.repo_id}`)
                          return refreshInstalled()
                        })
                      }
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </Hint>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
