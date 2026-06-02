import type { DevPanelShellProps } from '@/components/dev-panel/devPanelTypes'

/** Заглушка для production: панель разработчика не попадает в UI и не тянет DevPanel в бандл. */
export function DevPanelShell(_props: DevPanelShellProps) {
  return null
}
