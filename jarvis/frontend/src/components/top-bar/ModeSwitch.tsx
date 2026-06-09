import { Hint } from '@/components/ui/hint'
import { cn } from '@/lib/utils'
import { MODE_LABELS, type AgentMode } from '@/types'

const MODES: AgentMode[] = ['standard', 'accountant', 'marketer', 'developer']

const MODE_HINTS: Record<AgentMode, string> = {
  standard: 'Универсальный ассистент. Файлы «Сознательное» — в Настройках.',
  accountant:
    'Бухгалтерия и право РФ. Только текст через DeepSeek — не генерирует картинки.',
  marketer:
    'Маркетинг, дизайн и генерация изображений (Google Nano Banana). Не путать с DeepSeek.',
  developer:
    'Код и архитектура. Только Perplexity (pplx-…). Картинки — режим «Маркетолог+Дизайнер» и Nano Banana.',
}

interface ModeSwitchProps {
  mode: AgentMode
  onModeChange: (mode: AgentMode) => void
  deepseekConfigured?: boolean
  nanobananaConfigured?: boolean
  perplexityConfigured?: boolean
  perplexityUsable?: boolean
  compact?: boolean
  className?: string
}

function needsKey(
  id: AgentMode,
  deepseekConfigured: boolean,
  nanobananaConfigured: boolean,
  perplexityConfigured: boolean,
  perplexityUsable: boolean,
): boolean {
  if (id === 'accountant') return !deepseekConfigured
  if (id === 'marketer') return !nanobananaConfigured
  if (id === 'developer') return !perplexityUsable && !perplexityConfigured
  return false
}

/** Переключатель режимов чата — в шапке над чатом. */
export function ModeSwitch({
  mode,
  onModeChange,
  deepseekConfigured = false,
  nanobananaConfigured = false,
  perplexityConfigured = false,
  perplexityUsable = false,
  compact,
  className,
}: ModeSwitchProps) {
  return (
    <div
      className={cn('flex min-h-0 min-w-0 items-center gap-1.5', className)}
      role="group"
      aria-label="Режим чата"
    >
      {!compact && (
        <span className="shrink-0 text-[10px] font-semibold uppercase leading-none tracking-wide text-muted-foreground">
          Режим:
        </span>
      )}
      <div
        className={cn(
          'inline-flex min-h-0 flex-wrap items-center rounded-md border border-border bg-muted/50 p-0.5',
          compact && 'w-full',
        )}
        role="tablist"
        aria-label="Режимы Jarvis"
      >
        {MODES.map((id) => {
          const missingKey = needsKey(
            id,
            deepseekConfigured,
            nanobananaConfigured,
            perplexityConfigured,
            perplexityUsable,
          )
          let hint = MODE_HINTS[id]
          if (missingKey) {
            if (id === 'accountant') {
              hint =
                'Нажмите — откроются Настройки, введите ключ DeepSeek (sk-…)'
            } else if (id === 'marketer') {
              hint =
                'Нажмите — откроются Настройки, введите ключ Google Nano Banana'
            } else if (id === 'developer') {
              hint = 'Нажмите — откроются Настройки → Perplexity (pplx-…)'
            }
          }

          return (
            <Hint key={id} text={hint}>
              <button
                type="button"
                role="tab"
                aria-selected={mode === id}
                onClick={() => onModeChange(id)}
                className={cn(
                  'flex h-7 shrink-0 items-center rounded-[5px] px-2 text-[11px] font-medium leading-none transition-all',
                  compact && 'flex-1 text-center text-[10px]',
                  mode === id
                    ? 'bg-background text-foreground shadow-sm ring-1 ring-primary/30'
                    : 'text-muted-foreground hover:bg-background/60 hover:text-foreground',
                  missingKey && mode !== id && 'ring-1 ring-amber-500/25',
                )}
              >
                {MODE_LABELS[id]}
              </button>
            </Hint>
          )
        })}
      </div>
    </div>
  )
}
