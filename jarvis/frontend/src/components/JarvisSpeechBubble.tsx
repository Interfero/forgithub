import { cn } from '@/lib/utils'

export type JarvisSpeechBubbleVariant = 'think' | 'sleep'
export type JarvisSpeechBubblePlacement = 'above' | 'corner'

interface JarvisSpeechBubbleProps {
  variant: JarvisSpeechBubbleVariant
  /** above — по центру над головой; corner — угол (legacy) */
  placement?: JarvisSpeechBubblePlacement
  className?: string
}

/** Облачко мыслей (? — думает, ZzZ — «спит» при долгом простое). */
export function JarvisSpeechBubble({
  variant,
  placement = 'above',
  className,
}: JarvisSpeechBubbleProps) {
  const isSleep = variant === 'sleep'

  const label = isSleep ? (
    <>
      Z<span className="jarvis-speech-bubble__z-small">z</span>
      <span className="jarvis-speech-bubble__z-small">Z</span>
    </>
  ) : (
    '?'
  )

  if (placement === 'above') {
    return (
      <div
        className={cn(
          'jarvis-speech-bubble jarvis-speech-bubble--above pointer-events-none flex select-none flex-col items-center',
          isSleep ? 'jarvis-speech-bubble--sleep' : 'jarvis-speech-bubble--think',
          className,
        )}
        aria-hidden
      >
        <div className="jarvis-speech-bubble__cloud">
          <span className="jarvis-speech-bubble__label">{label}</span>
        </div>
        <span className="jarvis-speech-bubble__trail" aria-hidden>
          <span className="jarvis-speech-bubble__dot jarvis-speech-bubble__dot--sm" />
          <span className="jarvis-speech-bubble__dot jarvis-speech-bubble__dot--xs" />
        </span>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'jarvis-speech-bubble jarvis-speech-bubble--corner pointer-events-none select-none',
        isSleep ? 'jarvis-speech-bubble--sleep' : 'jarvis-speech-bubble--think',
        className,
      )}
      aria-hidden
    >
      <div className="jarvis-speech-bubble__cloud">
        <span className="jarvis-speech-bubble__label">{label}</span>
      </div>
      <span className="jarvis-speech-bubble__dot jarvis-speech-bubble__dot--sm" />
      <span className="jarvis-speech-bubble__dot jarvis-speech-bubble__dot--xs" />
    </div>
  )
}
