import type { ReactNode } from 'react'
import { TooltipPopup } from './TooltipPopup'
import { useTooltipInteraction } from './useTooltipInteraction'
import type { TooltipSide } from './tooltipPlacement'

interface TooltipProps {
  label: string
  enabled?: boolean
  placement?: TooltipSide
  children: ReactNode
}

/** Visual name for one already-labelled control; duplicate text is hidden from assistive technology. */
export function Tooltip({ label, enabled = true, placement = 'right', children }: TooltipProps) {
  const tip = useTooltipInteraction({ enabled })
  return <span ref={tip.anchorRef} className="tooltip-anchor" {...tip.triggerHandlers}>
    {children}
    <TooltipPopup interaction={tip} placement={placement} className="tooltip">{label}</TooltipPopup>
  </span>
}
