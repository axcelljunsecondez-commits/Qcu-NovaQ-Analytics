import { NumericValue } from '../ui/NumericValue'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { fmtDecimal } from '../../lib/format'
import { finiteNumber, minutes } from '../../lib/results'
import { InfoTip } from '../ui/InfoTip'

function KeyResult({ id, label, source, how, children }: { id: string; label: string; source: string; how: string; children: ReactNode }) {
  return (
    <section className="card key-result" aria-labelledby={`${id}-label`}>
      <div className="results-metric-heading"><h3 id={`${id}-label`} className="kpi-label">{label}</h3><InfoTip name={label} text={how} /></div>
      <div className="key-result-value">{children}</div>
      <p className="key-result-source">{source}</p>
    </section>
  )
}

function minutesText(hours: number | null | undefined, unavailable: string, unit: string): string {
  const value = minutes(hours)
  return value === null ? unavailable : `${fmtDecimal(value, 1)} ${unit}`
}

export interface RecordedWait {
  /** False for aggregate uploads: the file has no arrival and service-start times. */
  hasRecords: boolean
  loading: boolean
  dayWaitHours: number | null
}

export function KeyResults({ kpis, separate, recorded }: {
  kpis: Record<string, number | string | null>
  separate: boolean
  recorded: RecordedWait
}) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const unit = t('results.min')
  const unstableCount = finiteNumber(kpis.unstable_count) ?? 0

  return (
    <div className="key-results" role="group" aria-label={t('results.key_results')}>
      <KeyResult id="kr-recorded" label={t('results.recorded_wait')} source={t('results.source_data')} how={t('results.how_recorded')}>
        {!recorded.hasRecords
          ? <p className="key-result-note">{t('results.recorded_unavailable')}</p>
          : recorded.loading ? <p className="key-result-note">{t('common.loading')}</p>
          : <strong><NumericValue>{minutesText(recorded.dayWaitHours, unavailable, unit)}</NumericValue></strong>}
      </KeyResult>
      <KeyResult id="kr-estimated" label={t('results.estimated_wait')} source={t('results.source_estimate')}
        how={separate ? t('results.how_estimated_separate') : t('results.how_estimated_shared')}>
        <strong><NumericValue>{minutesText(finiteNumber(kpis.avg_waiting_time), unavailable, unit)}</NumericValue></strong>
        {!separate && unstableCount > 0 && <p className="key-result-note">{t('results.estimated_excludes', { count: unstableCount })}</p>}
      </KeyResult>
    </div>
  )
}
