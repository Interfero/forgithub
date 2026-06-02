import { Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useMenuSearch } from '@/hooks/useMenuSearch'
import { cn } from '@/lib/utils'

export interface MenuSearchNavigatePayload {
  sectionDomId: string
  label: string
}

interface MenuSearchProps {
  onNavigate: (payload: MenuSearchNavigatePayload) => void
  className?: string
}

/** Глобальный поиск по пунктам меню (индекс в jarvis.db). */
export function MenuSearch({ onNavigate, className }: MenuSearchProps) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const { menuItems: results, loading } = useMenuSearch(query)

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <label className="sr-only" htmlFor="jarvis-menu-search">
        Поиск по меню
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          id="jarvis-menu-search"
          type="search"
          value={query}
          placeholder="Поиск по меню…"
          className="h-8 w-full rounded-md border border-input bg-background py-1 pl-8 pr-2 text-xs"
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && results[0]) {
              onNavigate({
                sectionDomId: results[0].sectionDomId,
                label: results[0].label,
              })
              setOpen(false)
              setQuery('')
            }
            if (e.key === 'Escape') setOpen(false)
          }}
        />
      </div>
      {open && (
        <ul
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-56 overflow-y-auto rounded-md border border-border bg-popover py-1 shadow-lg"
          role="listbox"
        >
          {loading && query.trim() && (
            <li className="px-3 py-1.5 text-[10px] text-muted-foreground">Поиск…</li>
          )}
          {!loading && results.length === 0 ? (
            <li className="px-3 py-2 text-[11px] text-muted-foreground">Ничего не найдено</li>
          ) : (
            results.map((item) => (
              <li key={item.sectionDomId + item.label}>
                <button
                  type="button"
                  role="option"
                  className="w-full px-3 py-2 text-left hover:bg-muted/60"
                  onClick={() => {
                    onNavigate({ sectionDomId: item.sectionDomId, label: item.label })
                    setOpen(false)
                    setQuery('')
                  }}
                >
                  <span className="block text-[11px] font-medium text-foreground">{item.label}</span>
                  <span className="block truncate text-[10px] text-muted-foreground">
                    {item.path.join(' → ')}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  )
}
