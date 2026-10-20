import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { PeriodArrivals } from '../../api/types'
import { fmtDecimal } from '../../lib/format'
import { finiteNumber, minutes, periodsNeedingAttention, type ResultRow } from '../../lib/results'
import { InfoTip } from '../ui/InfoTip'

function KeyResult({ id, label, source, how, compact = false, children }: { id: string; label: string; source: string; how: string; compact?: boolean; children: ReactNode }) {
  return (
    <section className={`card key-result${compact ? ' key-result-compact' : ''}`} aria-labelledby={`${id}-label`}>
      <div className="results-metric-heading"><h3 id={`${id}-label`} className="kpi-label">{label}</h3><InfoTip stableInteraction name={label} text={how} /></div>
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

export function KeyResults({ rows, kpis, separate, recorded, busiest }: {
  rows: ResultRow[]
  kpis: Record<string, number | string | null>
  separate: boolean
  recorded: RecordedWait
  busiest: PeriodArrivals | null | undefined
}) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const unit = t('results.min')
  const attention = periodsNeedingAttention(rows)
  const unstableCount = finiteNumber(kpis.unstable_count) ?? 0
  const place = (time: string, line: string | null) => (line ? `${time} · ${line}` : time)
  const busiestRate = busiest ? finiteNumber(busiest.arrivals_per_hour) : null

  return (
    <div className="key-results" role="group" aria-label={t('results.key_results')}>
      <KeyResult id="kr-recorded" label={t('results.recorded_wait')} source={t('results.source_data')} how={t('results.how_recorded')}>
        {!recorded.hasRecords
          ? <p className="key-result-note">{t('results.recorded_unavailable')}</p>
          : recorded.loading ? <p className="key-result-note">{t('common.loading')}</p>
          : <strong>{minutesText(recorded.dayWaitHours, unavailable, unit)}</strong>}
      </KeyResult>
      <KeyResult id="kr-estimated" label={t('results.estimated_wait')} source={t('results.source_estimate')}
        how={separate ? t('results.how_estimated_separate') : t('results.how_estimated_shared')}>
        <strong>{minutesText(finiteNumber(kpis.avg_waiting_time), unavailable, unit)}</strong>
        {!separate && unstableCount > 0 && <p className="key-result-note">{t('results.estimated_excludes', { count: unstableCount })}</p>}
      </KeyResult>
      <KeyResult compact id="kr-attention" label={t('results.attention')} source={t('results.source_estimate')} how={t('results.how_attention')}>
        {attention.cantKeepUp.length === 0 && attention.highestWait === null && <strong>{unavailable}</strong>}
        {attention.cantKeepUp.length > 0 && (
          <p><span className="status-badge status-critical">{t('results.cant_keep_up')}</span>{' '}
            {attention.cantKeepUp.map((item) => place(item.time, item.line)).join(', ')}</p>
        )}
        {attention.highestWait !== null && (
          <p>
            {attention.cantKeepUp.length > 0 ? t('results.then_highest_wait') : t('results.highest_wait')}{' '}
            <strong>{place(attention.highestWait.time, attention.highestWait.line)}</strong>
            {' · '}{minutesText(attention.highestWait.waitHours, unavailable, unit)}
          </p>
        )}
        <p className="key-result-note">{t('results.not_longest_wait')}</p>
      </KeyResult>
      <KeyResult compact id="kr-busiest" label={t('results.busiest')} source={t('results.source_data')}
        how={separate ? t('results.how_busiest_separate') : t('results.how_busiest_shared')}>
        {busiest && busiestRate !== null
          ? <><strong>{busiest.time}</strong><p>{t('results.customers_per_hour', { count: busiestRate, value: fmtDecimal(busiestRate) })}</p></>
          : <strong>{unavailable}</strong>}
      </KeyResult>
    </div>
  )
}
