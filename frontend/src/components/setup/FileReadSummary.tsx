import { useTranslation } from 'react-i18next'
import type { SharedAggregateFileFacts, QueueSetup } from '../../api/types'
import { fmtDecimal } from '../../lib/format'
import { headingText } from '../../lib/headingText'

/** File contents returned by the server; this component never parses or recalculates the upload. */
export function FileReadSummary({ facts, derived, analysisName }: { facts: SharedAggregateFileFacts; derived: QueueSetup; analysisName: string }) {
  const { t } = useTranslation()
  const range = (low: number, high: number) => low === high ? fmtDecimal(low) : `${fmtDecimal(low)}–${fmtDecimal(high)}`
  return (
    <section className="card file-read-summary" aria-labelledby="file-read-title">
      <h3 id="file-read-title" lang="en" className="card-title">{headingText(t, 'analyses.upload_read_title')}</h3>
      <dl className="file-read-facts">
        <div><dt>{t('analyses.active')}</dt><dd>{analysisName} · {t('analyses.shared')}</dd></div>
        <div><dt>{t('datasets.file')}</dt><dd>{facts.filename} · {facts.row_count} {t('datasets.rows')}</dd></div>
        <div><dt>{t('analyses.segments')}</dt><dd>{t('simulation.operating_hours', { hours: `${facts.start_time}–${facts.end_time}` })} · {t('analyses.upload_read_segments', { count: facts.row_count })}</dd></div>
        <div><dt>{t('setup.manual_counters')}</dt><dd>{range(facts.counter_min, facts.counter_max)}</dd></div>
        <div><dt>{t('analyses.staffing_varies')}</dt><dd>{t(derived.staffing_varies_by_period ? 'guided.yes' : 'guided.no')}</dd></div>
        <div><dt>{t('setup.manual_arrivals')}</dt><dd>{range(facts.lambda_min, facts.lambda_max)}</dd></div>
        <div><dt>{t('setup.manual_served')}</dt><dd>{range(facts.mu_min, facts.mu_max)}</dd></div>
      </dl>
      <figure className="file-read-counters">
        <figcaption>{t('setup.manual_counters')}</figcaption>
        <svg viewBox={`0 0 ${facts.rows.length * 28} 80`} role="img" aria-label={t('setup.manual_counters')} preserveAspectRatio="none">
          {facts.rows.map((row, index) => {
            const height = row.c / Math.max(1, facts.counter_max) * 70
            return <rect key={row.time} x={index * 28 + 2} y={76 - height} width={24} height={height}><title>{row.time}: {row.c}</title></rect>
          })}
        </svg>
      </figure>
      <details>
        <summary>{t('filters.show_per_period', { count: facts.row_count })}</summary>
        <div className="table-scroll" role="region" aria-label={t('setup.manual_table')} tabIndex={0}>
          <table>
            <caption className="sr-only">{t('setup.manual_table')}</caption>
            <thead><tr><th scope="col">{t('setup.manual_period')}</th><th scope="col">{t('setup.manual_arrivals')}</th><th scope="col">{t('setup.manual_served')}</th><th scope="col">{t('setup.manual_counters')}</th></tr></thead>
            <tbody>{facts.rows.map((row) => <tr key={row.time}><th scope="row">{row.time}</th><td>{fmtDecimal(row.lambda)}</td><td>{fmtDecimal(row.mu)}</td><td>{row.c}</td></tr>)}</tbody>
          </table>
        </div>
      </details>
    </section>
  )
}
