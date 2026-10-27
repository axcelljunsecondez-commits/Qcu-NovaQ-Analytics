import { useLayoutEffect, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { tooltipPlacement, type TooltipSide } from './tooltipPlacement'
import type { TooltipInteraction } from './useTooltipInteraction'

interface TooltipPopupProps {
  interaction: TooltipInteraction
  placement: TooltipSide
  className: 'tooltip' | 'info-tip-text'
  children: string
  id?: string
  descriptive?: boolean
  avoidInput?: boolean
}

export function TooltipPopup({ interaction, placement, className, children, id, descriptive = false, avoidInput = false }: TooltipPopupProps) {
  const { open, popupRef, portalHost, getTrigger } = interaction
  const [position, setPosition] = useState<(CSSProperties & { side: TooltipSide }) | null>(null)
  useLayoutEffect(() => {
    if (!open || !portalHost) return
    function positionPopup() {
      const trigger = getTrigger()
      const popup = popupRef.current
      if (!trigger || !popup) return
      const visual = window.visualViewport
      const viewport = { left: visual?.offsetLeft ?? 0, top: visual?.offsetTop ?? 0, width: visual?.width ?? window.innerWidth, height: visual?.height ?? window.innerHeight }
      const bounds = trigger.getBoundingClientRect()
      const size = popup.getBoundingClientRect()
      const input = avoidInput ? trigger.closest('.form-field')?.querySelector('input, select, textarea') : null
      const result = tooltipPlacement(bounds, size, viewport, placement, input?.getBoundingClientRect())
      const inherited = getComputedStyle(trigger)
      const tokens: Record<string, string> = {}
      for (const key of ['--bg-card', '--text-primary', '--border', '--shadow-md', '--navy-950']) {
        const value = inherited.getPropertyValue(key).trim()
        if (value) tokens[key] = value
      }
      const maxWidth = Math.min(result.maxWidth, 22 * (Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16))
      setPosition({ ...tokens, fontFamily: inherited.fontFamily, left: result.left, top: result.top, maxWidth, maxHeight: result.maxHeight, side: result.side })
    }
    positionPopup()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(positionPopup)
    if (popupRef.current) observer?.observe(popupRef.current)
    const theme = new MutationObserver(positionPopup)
    theme.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => { observer?.disconnect(); theme.disconnect() }
  }, [avoidInput, children, getTrigger, open, placement, popupRef, portalHost])

  if (!open || !portalHost) return null
  const { side, ...style } = position ?? {}
  return createPortal(<span ref={popupRef} id={id} className={`floating-tooltip ${className}`} data-side={side}
    role={descriptive ? 'tooltip' : undefined} aria-hidden={descriptive ? undefined : true}
    data-testid={descriptive ? undefined : 'tooltip'}
    style={{ ...style, visibility: position ? 'visible' : 'hidden' }} {...interaction.popupHandlers}>{children}</span>, portalHost)
}
