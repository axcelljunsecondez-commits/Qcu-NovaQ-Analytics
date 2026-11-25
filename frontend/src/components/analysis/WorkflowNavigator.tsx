import { useEffect, useId, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { analysisWorkflow, workflowStepHref } from '../../lib/workflow'
import { Tooltip } from '../ui/Tooltip'

/** Width (content box) at which global.css shows the one-row numbered step bar; keep in sync with
 *  `@container workflow-footer (min-width: 920px)` in global.css (K-HB-4: widest case 878 px). */
const WIDE_STEP_ROW_PX = 920

/** True while the footer is wide enough for the numbered step bar, where step labels become tooltips. */
function useWideStepRow(element: HTMLElement | null) {
  const [wide, setWide] = useState(false)
  useEffect(() => {
    if (!element || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentBoxSize?.[0]
      const width = box ? box.inlineSize : entries[0]?.contentRect.width ?? 0
      setWide(width >= WIDE_STEP_ROW_PX)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [element])
  return wide
}

export function WorkflowNavigator() {
  const { t } = useTranslation()
  const { analysisId } = useParams()
  const location = useLocation()
  const listId = useId()
  const [expanded, setExpanded] = useState(false)
  const [navElement, setNavElement] = useState<HTMLElement | null>(null)
  const wide = useWideStepRow(navElement)
  // A new step page starts with the step list closed (narrow layout only; wide layouts always show it).
  useEffect(() => setExpanded(false), [location.pathname])
  const current = location.pathname.split('/').pop()
  const index = analysisWorkflow.findIndex(([path]) => path === current)
  if (!analysisId || index < 0) return null
  const previous = analysisWorkflow[index - 1]
  const next = analysisWorkflow[index + 1]

  return (
    <nav ref={setNavElement} className="workflow-footer" aria-label={t('workflow.navigation')}>
      <button
        type="button"
        className="workflow-summary"
        aria-expanded={expanded}
        aria-controls={listId}
        onClick={() => setExpanded((value) => !value)}
      >
        <span className="workflow-position">
          {t('workflow.step', { current: index + 1, total: analysisWorkflow.length })}
        </span>
        <strong>{t(analysisWorkflow[index][1])}</strong>
      </button>
      <ol id={listId} className={`workflow-stepper${expanded ? ' is-expanded' : ''}`}>
        {analysisWorkflow.map(([path, label], stepIndex) => {
          const isCurrent = stepIndex === index
          // Owner 2026-11-24: in the wide row other steps show only their number; the label stays the
          // accessible name (visually hidden by CSS) and appears as a tooltip on hover and focus.
          return (
            <li key={path} className={isCurrent ? 'active' : undefined}>
              <Tooltip label={t(label)} enabled={wide && !isCurrent} placement="top">
                <Link to={workflowStepHref(path, analysisId)} aria-current={isCurrent ? 'step' : undefined}>
                  <span className="workflow-step-number" aria-hidden="true">{stepIndex + 1}</span>
                  <span className="workflow-step-label">{t(label)}</span>
                </Link>
              </Tooltip>
            </li>
          )
        })}
      </ol>
      <div className="workflow-footer-actions">
        {previous && (
          <Link className="btn-ghost" to={workflowStepHref(previous[0], analysisId)}>
            {t('workflow.back', { step: t(previous[1]) })}
          </Link>
        )}
        {next ? (
          <Link className="btn-primary" to={workflowStepHref(next[0], analysisId)}>
            {t('workflow.next', { step: t(next[1]) })}
          </Link>
        ) : (
          <Link className="btn-primary" to="/analyses">{t('workflow.finish')}</Link>
        )}
      </div>
    </nav>
  )
}
