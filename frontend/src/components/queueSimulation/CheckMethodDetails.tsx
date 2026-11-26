import { useTranslation } from 'react-i18next'
import type { SimMcOut } from '../../api/types'
import { fmtPctDecimal } from '../../lib/format'
import { storedMcParameters, trialsText } from '../../lib/manyVariations'

const SAME = 1e-9

/**
 * "How checks were calculated" (Phase E, owner-authorized 2026-11-25): a closed native disclosure with the
 * method and the parameters every stored Many variations row of the checked run agrees on. A value the rows
 * do not agree on, or rows of another run (the caller passes none), shows Unavailable or is left out.
 * The plan's-target wording is used only when the stored threshold is the plan's target, as in the chart.
 */
export function CheckMethodDetails({ rows, planTarget = null }: { rows: readonly SimMcOut[]; planTarget?: number | null }) {
  const { t } = useTranslation()
  const params = storedMcParameters(rows)
  const ruleKey = planTarget !== null && params.threshold !== null && Math.abs(params.threshold - planTarget) <= SAME
    ? 'charts.mc_chip_fail_plan' : 'charts.mc_chip_fail_current'
  return (
    <details className="decision-details check-method-details" data-testid="check-method-details">
      <summary>{t('simulation.method_disclosure')}</summary>
      <p>{t('simulation.check_variations')}</p>
      <dl className="check-method-list">
        <div>
          <dt>{t('simulation.trials')}</dt>
          <dd className="numeric-value" data-testid="check-method-trials">{params.trials !== null ? trialsText(params.trials) : t('results.unavailable')}</dd>
        </div>
      </dl>
      {params.threshold !== null && <p data-testid="check-method-rule">{t(ruleKey, { threshold: fmtPctDecimal(params.threshold) })}</p>}
    </details>
  )
}
