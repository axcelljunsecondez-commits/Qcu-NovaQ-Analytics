import { headingText } from '../lib/headingText'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type { SeparateSchedule } from '../api/types'
import { fmt, fmtPctDecimal } from '../lib/format'

function formatLaneCount(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : String(value)
}

function formatAdjustment(value: number | null | undefined, t: TFunction): string {
  if (value === null || value === undefined) return '—'
  if (value === 0) return t('optimize.sep_keep')
  return value > 0 ? `+${value}` : String(value)
}

export function SeparateScheduleCard({ schedule }: { schedule: SeparateSchedule }) {
  const { t } = useTranslation()
  return (
    <div className="card result-card" style={{
      background: 'var(--color-bg-surface)',
      border: '1px solid var(--color-border-subtle)',
      borderRadius: '13px',
      padding: '18px',
    }}>
      <h3 lang="en" className="section-title">{headingText(t, 'optimize.sep_estimated_plan')}</h3>
      <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>
        <span>{t('optimize.sep_target')}: {fmtPctDecimal(schedule.target_utilization)}</span>
        {' · '}<span>{t('optimize.sep_method')}</span>
        {' · '}<span>{t('optimize.sep_replications')}: {schedule.des.replications}</span>
      </div>
      {schedule.overall !== 'COMPLETE' && (
        <div role="alert" className="alert alert-warn" style={{ marginTop: '12px' }}>
          <strong>
            {schedule.overall === 'INFEASIBLE'
              ? t('optimize.sep_infeasible')
              : t('optimize.sep_unavailable_title')}
          </strong>
          {schedule.reason && <p style={{ margin: '4px 0 0' }}>{schedule.reason}</p>}
          {schedule.overall !== 'INFEASIBLE' && (
            <p style={{ margin: '4px 0 0' }}>{t('optimize.sep_unavailable_body')}</p>
          )}
        </div>
      )}
      <div className="table-scroll" role="region" aria-label={t('optimize.sep_estimated_plan')} tabIndex={0} style={{ marginTop: '12px' }}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t('optimize.sep_col_time')}</th>
              <th scope="col">{t('optimize.sep_col_current')}</th>
              <th scope="col">{t('optimize.sep_col_optimal')}</th>
              <th scope="col">{t('optimize.sep_col_adjustment')}</th>
              <th scope="col">{t('optimize.sep_col_peak')}</th>
              <th scope="col">{t('optimize.sep_col_cost')}</th>
            </tr>
          </thead>
          <tbody>
            {schedule.periods.map((period) => {
              const uncertainty = period.optimum?.cost_uncertainty
              return (
                <tr key={period.time}>
                  <th scope="row">{period.time}</th>
                  <td>{period.current_active_lanes === null ? '—' : period.current_active_lanes.length}</td>
                  <td>{formatLaneCount(period.optimal_active_lanes)}</td>
                  <td>{formatAdjustment(period.adjustment, t)}</td>
                  <td>
                    {fmtPctDecimal(period.optimum?.candidate_utilization ?? null)}
                    {period.optimum?.near_target_noise === true && (
                      <small role="note" style={{ display: 'block', color: 'var(--warning)' }}>
                        {t('optimize.sep_near_target_noise')}
                      </small>
                    )}
                  </td>
                  <td>
                    {fmt(period.optimum?.total_cost ?? null)}
                    {uncertainty && uncertainty.ci_lower !== null && uncertainty.ci_upper !== null && (
                      <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                        {t('optimize.sep_cost_ci')}: {fmt(uncertainty.ci_lower)}–{fmt(uncertainty.ci_upper)}
                      </small>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {schedule.periods.map((period) => (
        <details key={period.time} style={{ marginTop: '8px' }}>
          <summary style={{ fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}>
            {t('optimize.sep_candidate_evidence')} · {period.time}
          </summary>
          <div className="table-scroll" role="region" tabIndex={0} aria-label={period.time}>
          <table style={{ marginTop: '6px' }}>
            <thead>
              <tr>
                <th scope="col">{t('optimize.sep_col_lanes')}</th>
                <th scope="col">{t('optimize.sep_col_status')}</th>
                <th scope="col">{t('optimize.sep_col_peak')}</th>
                <th scope="col">{t('optimize.sep_col_mean_cost')}</th>
              </tr>
            </thead>
            <tbody>
              {period.candidates.map((candidate) => (
                <tr key={candidate.active_lane_count}>
                  <td>{candidate.active_lane_count}</td>
                  <td>{candidate.status}</td>
                  <td>{fmtPctDecimal(candidate.candidate_utilization)}</td>
                  <td>{fmt(candidate.mean_total_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </details>
      ))}
    </div>
  )
}
