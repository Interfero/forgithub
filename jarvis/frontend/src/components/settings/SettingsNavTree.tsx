import { ChevronDown, ChevronRight } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { SETTINGS_NAV_GROUPS, type SettingsBlockId } from '@/lib/settingsMenu'
import { cn } from '@/lib/utils'

interface SettingsNavTreeProps {
  searchQuery: string
  activeSectionDomId: string | null
  onSelect: (sectionDomId: string, blockId: SettingsBlockId) => void
  isBlockVisible: (blockId: SettingsBlockId) => boolean
  isSectionVisible: (
    sectionDomId: string,
    keywords: string[],
    label: string,
  ) => boolean
}

export function SettingsNavTree({
  searchQuery,
  activeSectionDomId,
  onSelect,
  isBlockVisible,
  isSectionVisible,
}: SettingsNavTreeProps) {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(SETTINGS_NAV_GROUPS.map((g) => [g.blockId, false])),
  )

  useEffect(() => {
    if (!searchQuery.trim()) return
    setExpandedGroups(() =>
      Object.fromEntries(
        SETTINGS_NAV_GROUPS.map((g) => [g.blockId, isBlockVisible(g.blockId)]),
      ),
    )
  }, [searchQuery, isBlockVisible])

  const visibleGroups = useMemo(
    () => SETTINGS_NAV_GROUPS.filter((g) => isBlockVisible(g.blockId)),
    [isBlockVisible],
  )

  const toggleGroup = (blockId: SettingsBlockId) => {
    setExpandedGroups((prev) => ({ ...prev, [blockId]: !prev[blockId] }))
  }

  return (
    <nav className="flex flex-col gap-0.5 p-2" aria-label="Дерево настроек">
      <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Дерево настроек
      </p>
      {visibleGroups.length === 0 ? (
        <p className="px-2 py-3 text-[11px] text-muted-foreground">Ничего не найдено</p>
      ) : (
        visibleGroups.map((g) => {
          const groupOpen = expandedGroups[g.blockId] !== false
          const hasChildren = g.children.length > 0
          const blockActive = activeSectionDomId === g.sectionDomId

          return (
            <div key={g.blockId}>
              <div className="flex items-center gap-0.5">
                {hasChildren ? (
                  <button
                    type="button"
                    className="rounded p-1 text-muted-foreground hover:bg-muted/50"
                    aria-label={groupOpen ? 'Свернуть' : 'Развернуть'}
                    onClick={() => toggleGroup(g.blockId)}
                  >
                    {groupOpen ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                  </button>
                ) : (
                  <span className="w-6" />
                )}
                <button
                  type="button"
                  onClick={() => onSelect(g.sectionDomId, g.blockId)}
                  className={cn(
                    'min-w-0 flex-1 rounded-md px-2 py-1.5 text-left text-[11px] font-medium transition-colors',
                    blockActive
                      ? 'bg-primary/15 text-primary'
                      : 'text-foreground hover:bg-muted/50',
                  )}
                >
                  {g.label}
                </button>
              </div>
              {hasChildren && groupOpen && (
                <ul className="ml-5 border-l border-border/60 pl-2">
                  {g.children
                    .filter((c) =>
                      isSectionVisible(c.sectionDomId, c.keywords, c.label),
                    )
                    .map((c) => (
                      <li key={c.sectionDomId}>
                        <button
                          type="button"
                          onClick={() => onSelect(c.sectionDomId, g.blockId)}
                          className={cn(
                            'w-full rounded-md px-2 py-1 text-left text-[10px] transition-colors',
                            activeSectionDomId === c.sectionDomId
                              ? 'bg-primary/12 font-medium text-primary'
                              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
                          )}
                        >
                          {c.label}
                        </button>
                      </li>
                    ))}
                </ul>
              )}
            </div>
          )
        })
      )}
    </nav>
  )
}
