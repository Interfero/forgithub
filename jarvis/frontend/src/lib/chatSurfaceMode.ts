export type ChatSurfaceMode = 'text' | 'voice' | 'multimedia'

const MODE_KEY = 'jarvis-chat-surface-mode'
const UI_PERM_KEY = 'jarvis-voice-ui-permission-v1'
const OS_PERM_KEY = 'jarvis-voice-os-permission-v1'

export function readChatSurfaceMode(): ChatSurfaceMode {
  try {
    const v = localStorage.getItem(MODE_KEY)
    if (v === 'voice') return 'voice'
    if (v === 'multimedia') return 'text'
  } catch {
    /* ignore */
  }
  return 'text'
}

export function writeChatSurfaceMode(mode: ChatSurfaceMode): void {
  try {
    localStorage.setItem(MODE_KEY, mode)
  } catch {
    /* ignore */
  }
}

export interface VoiceAccessPermissions {
  uiControl: boolean
  osControl: boolean
}

export function readVoiceAccessPermissions(): VoiceAccessPermissions {
  try {
    return {
      uiControl: localStorage.getItem(UI_PERM_KEY) === '1',
      osControl: localStorage.getItem(OS_PERM_KEY) === '1',
    }
  } catch {
    return { uiControl: false, osControl: false }
  }
}

export function saveVoiceAccessPermissions(perms: VoiceAccessPermissions): void {
  try {
    localStorage.setItem(UI_PERM_KEY, perms.uiControl ? '1' : '0')
    localStorage.setItem(OS_PERM_KEY, perms.osControl ? '1' : '0')
  } catch {
    /* ignore */
  }
}

export function voiceAccessGranted(): boolean {
  const p = readVoiceAccessPermissions()
  return p.uiControl && p.osControl
}
