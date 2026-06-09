import { useEffect, useMemo, useState } from 'react'
import { searchMenu, type MenuSearchItem } from '@/api/client'
import {
  blockVisibleInSearch,
  filterSettingsMenu,
  flattenSettingsMenuItems,
  type SettingsBlockId,
  type SettingsMenuItem,
} from '@/lib/settingsMenu'
import { textMatchesSearchQuery } from '@/lib/keyboardLayout'

function collectBlockIds(
  items: MenuSearchItem[],
  blocksMatched: string[],
): SettingsBlockId[] {
  const ids = new Set<SettingsBlockId>()
  for (const b of blocksMatched) {
    if (b) ids.add(b as SettingsBlockId)
  }
  for (const it of items) {
    if (it.block_id && !it.is_block) ids.add(it.block_id as SettingsBlockId)
  }
  return [...ids]
}

function toMenuItems(items: MenuSearchItem[]): SettingsMenuItem[] {
  return items.map((it) => ({
    id: it.id,
    blockId: (it.block_id as SettingsBlockId | null) ?? null,
    sectionDomId: it.section_dom_id,
    label: it.label,
    path: it.path,
    isBlock: !!it.is_block,
    keywords: [],
  }))
}

/** Поиск по меню через jarvis.db; при ошибке API — локальный fallback. */
export function useMenuSearch(query: string) {
  const [dbItems, setDbItems] = useState<MenuSearchItem[] | null>(null)
  const [dbBlockIds, setDbBlockIds] = useState<SettingsBlockId[] | null>(null)
  const [useLocalFallback, setUseLocalFallback] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    const ac = new AbortController()

    const run = async () => {
      setLoading(true)
      try {
        const res = await searchMenu(query, 32, { signal: ac.signal })
        if (cancelled) return
        setDbItems(res.items)
        setDbBlockIds(
          query.trim() ? collectBlockIds(res.items, res.blocks_matched) : null,
        )
        setUseLocalFallback(false)
      } catch (e) {
        if (cancelled || (e instanceof DOMException && e.name === 'AbortError')) return
        setDbItems(null)
        setDbBlockIds(null)
        setUseLocalFallback(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    const t = window.setTimeout(() => void run(), query.trim() ? 160 : 0)
    return () => {
      cancelled = true
      ac.abort()
      window.clearTimeout(t)
    }
  }, [query])

  const menuItems: SettingsMenuItem[] = useMemo(() => {
    if (useLocalFallback || dbItems === null) {
      if (!query.trim()) {
        return flattenSettingsMenuItems()
          .filter((i) => i.id !== 'settings-root' && !i.isBlock)
          .slice(0, 12)
      }
      return filterSettingsMenu(query).slice(0, 24)
    }
    if (!query.trim()) {
      return toMenuItems(dbItems).filter((i) => !i.isBlock).slice(0, 12)
    }
    return toMenuItems(dbItems).slice(0, 24)
  }, [query, dbItems, useLocalFallback])

  const isBlockVisible = useMemo(() => {
    return (blockId: SettingsBlockId) =>
      blockVisibleInSearch(blockId, query, useLocalFallback ? null : dbBlockIds)
  }, [query, dbBlockIds, useLocalFallback])

  const isSectionVisible = useMemo(() => {
    return (sectionDomId: string, childKeywords: string[], childLabel: string) => {
      if (!query.trim()) return true
      if (!useLocalFallback && dbItems) {
        return dbItems.some((it) => it.section_dom_id === sectionDomId)
      }
      if (textMatchesSearchQuery(childLabel, query)) return true
      return childKeywords.some((k) => textMatchesSearchQuery(k, query))
    }
  }, [query, dbItems, useLocalFallback])

  return {
    menuItems,
    isBlockVisible,
    isSectionVisible,
    loading,
    useLocalFallback,
    cellsFromDb: !useLocalFallback && dbItems !== null,
  }
}
