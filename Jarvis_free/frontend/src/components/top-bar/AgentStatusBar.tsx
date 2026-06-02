import { useEffect, useState } from 'react'
import { JARVIS_INDICATORS_TOGGLE } from '@/lib/uiBridge'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { AgentStatusIndicators } from '@/components/top-bar/IndicatorPanel'
import { cn } from '@/lib/utils'
import type { AgentMode, AgentState } from '@/types'

const COLLAPSE_KEY = 'jarvis-indicators-collapsed'

/** Ширина chevron в заголовке — под неё выравнивается левая рамка панели с буквой «П». */
const INDICATOR_CHEVRON_SLOT = 'w-3.5 shrink-0'
const INDICATOR_GUTTER = 'flex gap-2 px-4'

interface AgentStatusBarProps {
  agent: AgentState
  mode: AgentMode
}

/** Публичные индикаторы — под переключателем режима (в production и dev). */
export function AgentStatusBar({ agent, mode }: AgentStatusBarProps) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [collapsed])

  useEffect(() => {
    const onToggle = () => setCollapsed((v) => !v)
    window.addEventListener(JARVIS_INDICATORS_TOGGLE, onToggle)
    return () => window.removeEventListener(JARVIS_INDICATORS_TOGGLE, onToggle)
  }, [])

  return (
    <div className="border-t border-border/40 bg-muted/10">
      <div className={cn(INDICATOR_GUTTER, 'py-1.5')}>
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left text-xs font-medium text-foreground/90 transition-colors hover:text-foreground"
          aria-expanded={!collapsed}
        >
          {collapsed ? (
            <ChevronDown className={cn('h-3.5', INDICATOR_CHEVRON_SLOT, 'text-muted-foreground')} />
          ) : (
            <ChevronUp className={cn('h-3.5', INDICATOR_CHEVRON_SLOT, 'text-muted-foreground')} />
          )}
          <span>Панель индикации</span>
          {collapsed && (
            <span className="truncate text-[10px] font-normal text-muted-foreground">
              — свёрнута, состояние в чипах при развороте
            </span>
          )}
        </button>
      </div>
      <div
        className={cn(
          'grid transition-[grid-template-rows] duration-200 ease-out',
          collapsed ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]',
        )}
      >
        <div className="max-h-[50vh] min-h-0 overflow-y-auto overflow-x-hidden overscroll-y-contain">
          <div className={cn(INDICATOR_GUTTER, 'pb-2 pt-0.5')}>
            <span className={INDICATOR_CHEVRON_SLOT} aria-hidden />
            <div className="min-w-0 w-full flex-1">
              <AgentStatusIndicators agent={agent} mode={mode} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
