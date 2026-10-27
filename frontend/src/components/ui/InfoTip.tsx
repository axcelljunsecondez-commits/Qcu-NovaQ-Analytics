import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { TooltipPopup } from './TooltipPopup'
import { useTooltipInteraction } from './useTooltipInteraction'

/** Accessible explanation; the same pointer, keyboard and touch rules apply to every page. */
export function InfoTip({ name, text }: { name: string; text: string }) {
  const { t } = useTranslation()
  const id = useId()
  const tip = useTooltipInteraction({ toggleOnClick: true })
  return <span ref={tip.anchorRef} className="info-tip" {...tip.triggerHandlers}>
    <button type="button" className="info-tip-button" aria-label={t('calculator.about', { name })}
      aria-expanded={tip.open} aria-describedby={tip.open ? id : undefined}>ⓘ</button>
    <TooltipPopup interaction={tip} placement="top" className="info-tip-text" id={id} descriptive avoidInput>{text}</TooltipPopup>
  </span>
}
