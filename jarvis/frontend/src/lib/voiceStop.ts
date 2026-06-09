/** Команды остановки озвучки / текущего ответа. */
const VOICE_STOP_RE =
  /(?:^|[\s,.!?])(?:джарвис|jarvis|жарвис|джавис)\s*[,]?\s*стоп(?:[\s,.!?]|$)|(?:^|[\s,.!?])стоп\s*[,]?\s*(?:джарвис|jarvis)(?:[\s,.!?]|$)/i

export function isVoiceStopCommand(text: string): boolean {
  return VOICE_STOP_RE.test((text || '').trim())
}
