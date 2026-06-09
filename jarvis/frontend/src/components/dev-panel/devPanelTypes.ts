import type { AgentState, VoiceSlot, XttsStatus } from '@/types'

export interface DevPanelShellProps {
  agent: AgentState
  voiceSlots: VoiceSlot[]
  xtts: XttsStatus
  onBaseVoiceUploaded?: () => void
  onMemoryChange?: () => void
  onVoiceSlotUpdate?: (slot: VoiceSlot) => void
  onVoiceRefresh?: () => void
  onXttsRefresh?: () => void
  onSystemLog?: (text: string) => void
}
