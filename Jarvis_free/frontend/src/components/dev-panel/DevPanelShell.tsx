import { DevPanel } from '@/components/dev-panel/DevPanel'
import type { DevPanelShellProps } from '@/components/dev-panel/devPanelTypes'

export type { DevPanelShellProps } from '@/components/dev-panel/devPanelTypes'

/** Только локальная разработка (в production-сборке модуль заменяется на stub). */
export function DevPanelShell(props: DevPanelShellProps) {
  return <DevPanel {...props} />
}
