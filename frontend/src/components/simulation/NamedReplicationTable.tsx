import { useTranslation } from 'react-i18next'
import type { NamedReplicationRow, NamedRunSummary, OutcomeCount } from '../../api/sharedNamed'
import { fmtDecimal } from '../../lib/format'

interface Props {
  rows: NamedReplicationRow[]
  summary: NamedRunSummary
  selectedIndex: number | null
  onSelect: (index: number) => void
}

const minutes = (hours: number | null | undefined) => (hours === null || hours === undefined ? null : hours * 60)
const OUTCOMES = ['with_unserved_customers', 'with_service_after_closing', 'with_shift_overrun', 'with_unfulfilled_breaks']

/** One row per replication and the descriptive aggregate. Waits show in minutes; null shows as "—". No verdict. */
export function NamedReplicationTable({ rows, summary, selectedIndex, onSelect }: Props) {
  const { t } = useTranslation()
  const means = summary.waiting_time.mean_of_replication_means_hours
  const weighted = summary.waiting_time.customer_weighted_mean_hours
  const totals = summary.customers.totals
  return (
    <div data-testid="named-replication-table">
      <div className="card table-scroll" role="region" aria-label={t('simulation.named_replications_caption')} tabIndex={0}>
        <table>
          <caption className="sr-only">{t('simulation.named_replications_caption')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('simulation.named_col_index')}</th>
              <th scope="col">{t('simulation.named_col_arrivals')}</th>
              <th scope="col">{t('simulation.named_col_served')}</th>
              <th scope="col">{t('simulation.named_col_unserved')}</th>
              <th scope="col">{t('simulation.named_col_served_after_closing')}</th>
              <th scope="col">{t('simulation.named_col_mean_wait_min')}</th>
              <th scope="col">{t('simulation.named_col_max_queue')}</th>
              <th scope="col">{t('simulation.named_col_waiting_customer_hours')}</th>
              <th scope="col">{t('simulation.named_col_waiting_at_close')}</th>
              <th scope="col">{t('simulation.named_col_drain_crew')}</th>
              <th scope="col">{t('simulation.named_col_run_after_closing_min')}</th>
              <th scope="col">{t('simulation.named_col_shifts_overrun')}</th>
              <th scope="col">{t('simulation.named_col_breaks_unfulfilled')}</th>
              <th scope="col">{t('simulation.named_col_conservation')}</th>
              <th scope="col"><span className="sr-only">{t('simulation.named_open_replication')}</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.replication_index} data-testid="named-replication-row"
                aria-selected={selectedIndex === row.replication_index}>
                <th scope="row">{row.replication_index}</th>
                <td>{row.customers.arrivals}</td>
                <td>{row.customers.served}</td>
                <td>
                  {row.customers.unserved}{' '}
                  <span className="form-hint">
                    {t('simulation.named_unserved_split', {
                      hard: row.customers.unserved_hard_cutoff,
                      none: row.customers.unserved_no_eligible_employee,
                    })}
                  </span>
                </td>
                <td>{row.customers.served_after_closing}</td>
                <td>{fmtDecimal(minutes(row.waiting.mean_wait_hours))}</td>
                <td>{row.waiting.max_queue_in_horizon ?? '—'}</td>
                <td>{fmtDecimal(row.waiting.customer_hours_total)}</td>
                <td>{row.closing.waiting_at_close}</td>
                <td>{row.closing.drain_crew_size}</td>
                <td>{fmtDecimal(minutes(row.closing.run_after_closing_hours))}</td>
                <td>{row.employees.shifts_with_overrun}</td>
                <td>{row.employees.breaks_unfulfilled}</td>
                <td>{t(row.customer_conservation ? 'simulation.named_conserved_yes' : 'simulation.named_conserved_no')}</td>
                <td>
                  <button type="button" className="btn-ghost" onClick={() => onSelect(row.replication_index)}>
                    {t('simulation.named_open_replication')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="card" data-testid="named-aggregate" aria-label={t('simulation.named_aggregate_title')}>
        <h3 className="section-title">{t('simulation.named_aggregate_title')}</h3>
        <p className="form-hint">{t('simulation.named_aggregate_help')}</p>
        <dl>
          <dt>{t('simulation.named_agg_replications')}</dt>
          <dd>{summary.replications}</dd>
          <dt>{t('simulation.named_agg_customers')}</dt>
          <dd>
            {t('simulation.named_agg_customers_value', {
              arrivals: totals.arrivals, served: totals.served, unserved: totals.unserved,
              after: totals.served_after_closing,
            })}
          </dd>
          <dt>{t('simulation.named_agg_mean_of_means')}</dt>
          <dd data-testid="named-agg-mean-of-means">
            {t('simulation.named_agg_mean_of_means_value', {
              mean: fmtDecimal(minutes(means.mean)),
              lower: fmtDecimal(minutes(means.ci_lower)),
              upper: fmtDecimal(minutes(means.ci_upper)),
              n: means.n,
              undefined: means.n_undefined,
            })}
            <span className="form-hint"> {means.definition}</span>
          </dd>
          <dt>{t('simulation.named_agg_weighted_mean')}</dt>
          <dd>
            {t('simulation.named_agg_weighted_mean_value', {
              value: fmtDecimal(minutes(weighted.value)),
              numerator: fmtDecimal(weighted.numerator_wait_hours),
              denominator: weighted.denominator_served_customers,
            })}
            <span className="form-hint"> {weighted.interval}</span>
          </dd>
          <dt>{t('simulation.named_agg_outcomes')}</dt>
          <dd>
            <p className="form-hint">{t('simulation.named_agg_outcomes_note')}</p>
            <ul>
              {OUTCOMES.map((key) => {
                const item = summary.outcome_counts[key] as OutcomeCount | undefined
                return item ? (
                  <li key={key}>
                    {t(`simulation.named_outcome_${key}`)}: {item.replications} / {item.denominator_replications}
                  </li>
                ) : null
              })}
            </ul>
          </dd>
          <dt>{t('simulation.named_agg_verdict')}</dt>
          <dd>{t('simulation.named_no_verdict')} <span className="form-hint">{summary.verdict_reason}</span></dd>
        </dl>
      </section>
    </div>
  )
}
