import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { TooltipPopup } from './TooltipPopup'
import { useTooltipInteraction } from './useTooltipInteraction'

/**
 * Accessible explanation; the same pointer, keyboard and touch rules apply to every page.
 * `ariaLabel` replaces the "About: {name}" button name with a full name (spec 2026-10-29 §7.6).
 * `label` shows that text as a dotted trigger instead of the ⓘ glyph; its accessible name is the label itself.
 */
export function InfoTip({ name, text, ariaLabel, label }: { name: string; text: string; ariaLabel?: string; label?: string }) {
  const { t } = useTranslation()
  const id = useId()
  const tip = useTooltipInteraction({ toggleOnClick: true })
  return <span ref={tip.anchorRef} className="info-tip" {...tip.triggerHandlers}>
    {label === undefined
      ? <button type="button" className="info-tip-button" aria-label={ariaLabel ?? t('calculator.about', { name })}
        aria-expanded={tip.open} aria-describedby={tip.open ? id : undefined}>ⓘ</button>
      : <button type="button" className="tip-trigger" aria-expanded={tip.open} aria-describedby={tip.open ? id : undefined}>{label}</button>}
    <TooltipPopup interaction={tip} placement="top" className="info-tip-text" id={id} descriptive avoidInput>{text}</TooltipPopup>
  </span>
}
