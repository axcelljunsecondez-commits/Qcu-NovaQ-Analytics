import { useTranslation } from 'react-i18next'

/**
 * Recorded check counts of one separate-lines validation or decision record (Phase E, owner O-E1/OD-E3/OD-E4).
 * Pure display: each value is shown exactly as recorded. Nothing is derived, reconciled or filled in:
 * a recorded 0 shows "0", and a missing, null or non-integer count shows Unavailable.
 */
export function CheckCountStrip({ total, passed, failed, insufficient }: {
  total: number | null | undefined
  passed: number | null | undefined
  failed: number | null | undefined
  insufficient: number | null | undefined
}) {
  const { t } = useTranslation()
  const shown = (value: number | null | undefined) => (typeof value === 'number' && Number.isInteger(value) && value >= 0 ? String(value) : t('results.unavailable'))
  const items: [string, number | null | undefined][] = [
    ['simulation.required_checks', total],
    ['simulation.verdict.pass', passed],
    ['simulation.verdict.fail', failed],
    ['simulation.verdict.insufficient', insufficient],
  ]
  return (
    <dl className="check-stats" aria-label={t('simulation.check_counts_label')} data-testid="check-count-strip">
      {items.map(([key, value]) => (
        <div key={key}>
          <dt>{t(key)}</dt>
          <dd className="numeric-value">{shown(value)}</dd>
        </div>
      ))}
    </dl>
  )
}
