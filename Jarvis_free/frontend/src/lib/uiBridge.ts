/** Команды UI от бэкенда / Qwen → React-панели Jarvis */

export const JARVIS_UI_EVENT = 'jarvis-ui-command'
export const JARVIS_INDICATORS_TOGGLE = 'jarvis-indicators-toggle'

export type SettingsFocusSection =
  | 'general'
  | 'qwen'
  | 'deepseek'
  | 'ideogram'
  | 'nanobanana'
  | 'perplexity'
  | 'telegram'
  | 'avito'

export type UiCommand =
  | { action: 'expand_panel'; panel: 'telegram' | 'avito' }
  | { action: 'open_settings'; section?: SettingsFocusSection }
  | { action: 'set_mode'; mode: 'standard' | 'accountant' | 'marketer' | 'developer' }
  | { action: 'set_field'; target: 'telegram' | 'avito'; field: string; value: string }
  | {
      action: 'click'
      target: 'telegram' | 'avito' | 'app'
      control: string
      on?: boolean
    }
  | { action: 'refresh_status' }

export function dispatchUiCommands(commands: UiCommand[]) {
  for (const cmd of commands) {
    window.dispatchEvent(new CustomEvent<UiCommand>(JARVIS_UI_EVENT, { detail: cmd }))
  }
}

export function toggleIndicatorsPanel() {
  window.dispatchEvent(new Event(JARVIS_INDICATORS_TOGGLE))
}
