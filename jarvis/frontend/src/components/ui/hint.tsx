import type { ReactNode } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface HintProps {
  text: string
  children: ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
}

/** Подсказка при наведении — для кнопок и обёрток индикаторов. */
export function Hint({ text, children, side = 'top' }: HintProps) {
  if (!text.trim()) return <>{children}</>
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side={side}>{text}</TooltipContent>
    </Tooltip>
  )
}
