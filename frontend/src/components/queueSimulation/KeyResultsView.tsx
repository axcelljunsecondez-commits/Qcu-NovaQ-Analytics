import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import type { RunSummary, SelectedDesPeriod, SimDesOut, SimulationTrace } from '../../api/types'
import { fmt, fmtDecimal, downloadCsv } from '../../lib/format'
import { SAMPLE_MINUTES, dayOrigin, dayPeriods, mergeDayTrace, scheduledBreaks, waitingThroughTheDay, wallClock, type ScheduledBreak } from '../../lib/replay'
import { DatePicker } from './DatePicker'
import { LqHistogram, MaxQueueBars, RhoLqLines, UtilizationHeatmap } from '../charts/Charts'
import { currentRun, suggestedRun, type RunChoice, type SimulationContext } from './simulationContext'

function Card({ label, now, plan, note }: { label: string; now: string; plan: string; note?: string }) {
  const { t } = useTranslation()
  return (
    <section className="card key-result" aria-label={label}>
      <h3 className="kpi-label">{label}</h3>
      <p className="headline-pair"><span>{t('simulation.run_current')}: <strong>{now}</strong></span><span aria-hidden="true">→</span><span>{t('simulation.run_suggested')}: <strong>{plan}</strong></span></p>
      {note && <p className="key-result-note">{note}</p>}
    </section>
  )
}

function WaitingChart({ trace, origin, breaks }: { trace: SimulationTrace; origin: number | null; breaks: ScheduledBreak[] }) {
  const { t } = useTranslation()
  const points = waitingThroughTheDay(trace)
  const max = Math.max(1, ...points.map((point) => point.waiting))
  const end = points.at(-1)?.hours ?? 0
  const label = (hours: number) => (origin === null ? `${fmtDecimal(hours, 2)} h` : wallClock(origin, hours))
  return (
    <section className="card" aria-labelledby="waiting-chart-title">
      <h2 id="waiting-chart-title" className="section-title">{t('simulation.chart_waiting')}</h2>
      <svg className="waiting-chart" viewBox="0 0 600 160" role="img" aria-label={t('simulation.chart_waiting_summary', { max })} preserveAspectRatio="none">
        {breaks.map((item, index) => (
          <rect key={index} className="waiting-chart-break" x={end > 0 ? (item.startHours / end) * 600 : 0} width={end > 0 ? Math.max(2, ((item.endHours - item.startHours) / end) * 600) : 0} y={0} height={160} />
        ))}
        <polyline className="waiting-chart-line" fill="none" points={points.map((point) => `${end > 0 ? (point.hours / end) * 600 : 0},${160 - (point.waiting / max) * 150}`).join(' ')} />
      </svg>
      <p className="form-hint">{t('simulation.chart_waiting_axis', { start: label(0), end: label(end), max, minutes: SAMPLE_MINUTES })}{breaks.length > 0 ? ` ${t('simulation.chart_breaks_marked')}` : ''}</p>
      {trace.truncated && <p className="form-hint">{t('simulation.chart_waiting_truncated')}</p>}
    </section>
  )
}

function WaitByPeriod({ summary }: { summary: RunSummary }) {
  const { t } = useTranslation()
  const values = summary.periods.map((period) => ({ time: period.time, minutes: period.average_wait_hours === null ? null : period.average_wait_hours * 60 }))
  const max = Math.max(0, ...values.map((item) => item.minutes ?? 0))
  return (
    <section className="card" aria-labelledby="wait-period-title">
      <h2 id="wait-period-title" className="section-title">{t('simulation.chart_wait_by_period')}</h2>
      <div className="hbar-chart" role="img" aria-labelledby="wait-period-title">
        {values.map((item) => (
          <div className="hbar-row" key={item.time}>
            <div className="hbar-head"><span className="hbar-label">{item.time}</span><span className="hbar-value">{item.minutes === null ? t('results.unavailable') : `${fmtDecimal(item.minutes, 1)} ${t('results.min')}`}</span></div>
            <span className="hbar-track"><span className="hbar-fill" style={{ width: item.minutes !== null && max > 0 ? `${(item.minutes / max) * 100}%` : '0%' }} /></span>
          </div>
        ))}
      </div>
    </section>
  )
}

function PeriodTable({ summary }: { summary: RunSummary }) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  return (
    <div className="table-scroll" role="region" aria-label={t('simulation.period_table')} tabIndex={0}>
      <table>
        <caption className="sr-only">{t('simulation.period_table')}</caption>
        <thead><tr><th scope="col">{t('common.time')}</th><th scope="col">{t('simulation.average_wait')}</th><th scope="col">{t('simulation.longest_line')}</th><th scope="col">{t('simulation.arrived')}</th><th scope="col">{t('simulation.served_customers')}</th></tr></thead>
        <tbody>
          {summary.periods.map((period) => (
            <tr key={period.time}>
              <th scope="row">{period.time}</th>
              <td>{period.average_wait_hours === null ? unavailable : `${fmtDecimal(period.average_wait_hours * 60, 1)} ${t('results.min')}`}</td>
              <td>{period.longest_line ?? unavailable}</td>
              <td>{period.arrivals ?? unavailable}</td>
              <td>{period.served ?? unavailable}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function LaneTable({ period }: { period: SelectedDesPeriod }) {
  const { t } = useTranslation()
  return (
    <div className="table-scroll" role="region" aria-label={period.time} tabIndex={0}>
      <table>
        <caption>{period.time}</caption>
        <thead><tr><th scope="col">{t('simulation.sep_lane')}</th><th scope="col">{t('simulation.sep_active')}</th><th scope="col">{t('simulation.sep_arrivals')}</th><th scope="col">{t('simulation.sep_served')}</th><th scope="col">Wq (min)</th><th scope="col">ρ</th></tr></thead>
        <tbody>
          {period.results.map((row) => (
            <tr key={String(row.queue_id)}>
              <th scope="row">{row.queue_id ?? '—'}</th><td>{row.active ? '✓' : '—'}</td><td>{row.arrivals ?? '—'}</td><td>{row.served ?? '—'}</td>
              <td>{fmt(row.Wq_sim === null || row.Wq_sim === undefined ? null : row.Wq_sim * 60)}</td><td>{fmtDecimal(row.rho_sim)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function LegacyMore({ rows }: { rows: SimDesOut[] }) {
  const { t } = useTranslation()
  const showLine = rows.some((row) => typeof row.queue_id === 'string' && row.queue_id.trim() !== '')
  return (
    <>
      <div className="table-scroll" role="region" aria-label={t('simulation.des_table_caption')} tabIndex={0}>
        <table>
          <caption className="sr-only">{t('simulation.des_table_caption')}</caption>
          <thead><tr><th scope="col">{t('common.time')}</th>{showLine && <th scope="col">{t('analyses.service_line')}</th>}<th scope="col">{t('simulation.status')}</th><th scope="col">ρ</th><th scope="col">Lq</th><th scope="col">{t('system.sim_wait_minutes')}</th><th scope="col">{t('simulation.max_queue')}</th><th scope="col">{t('simulation.served')}</th><th scope="col">{t('simulation.dropped')}</th></tr></thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.time}-${typeof row.queue_id === 'string' ? row.queue_id : ''}-${index}`}>
                <th scope="row">{row.time}</th>{showLine && <td>{typeof row.queue_id === 'string' && row.queue_id.trim() !== '' ? row.queue_id : '—'}</td>}
                <td>{row.error ?? row.status}</td><td>{fmtDecimal(row.rho_sim)}</td><td>{fmt(row.Lq_sim, 3)}</td><td>{fmt(row.Wq_sim == null ? null : row.Wq_sim * 60, 2)}</td><td>{row.max_queue}</td><td>{row.served}</td><td>{row.dropped}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card-grid">
        <div className="card"><UtilizationHeatmap rows={rows} /></div>
        <div className="card"><RhoLqLines rows={rows} /></div>
        <div className="card"><MaxQueueBars rows={rows} /></div>
        <div className="card"><LqHistogram rows={rows} /></div>
      </div>
      <button type="button" className="btn-ghost" onClick={() => downloadCsv('novaq_unified_des.csv', rows as unknown as Record<string, unknown>[])}>{t('simulation.download_csv')}</button>
    </>
  )
}

/** Key results (D27, D30): four headline cards Current → Suggested and two charts; the rest under More results. */
export function KeyResultsView({ context, run }: { context: SimulationContext; run: RunChoice }) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const suggested = suggestedRun(context)
  const current = currentRun(context)
  const nowSummary = current?.summary ?? null
  const planSummary = suggested?.result.summary ?? null
  const shown = run === 'suggested' ? suggested : current ? { kind: 'legacy' as const, result: current } : null
  const shownSummary = run === 'suggested' ? planSummary : nowSummary
  const origin = dayOrigin(context.analysis.queue_setup)
  const breaks = context.separate ? scheduledBreaks(context.analysis.queue_setup) : []
  const [params] = useSearchParams()
  const chosenDay = shown?.kind === 'separate' ? dayPeriods(shown.result.periods, context.perDateDays, params.get('date')) : null
  const dayTrace = chosenDay && shownSummary?.basis === 'continuous_day' ? mergeDayTrace(chosenDay.periods) : null
  const dayCount = shown?.kind === 'separate' ? shown.result.days?.length ?? 0 : 0

  const value = (summary: RunSummary | null, exists: boolean, pick: (summary: RunSummary) => string | null) => {
    if (!exists) return t('simulation.status_not_run')
    if (!summary) return t('simulation.summary_rerun')
    return pick(summary) ?? unavailable
  }
  const minutesOf = (summary: RunSummary) => (summary.average_wait_hours === null ? null : `${fmtDecimal(summary.average_wait_hours * 60, 1)} ${t('results.min')}`)
  const count = (field: 'served' | 'in_system_at_close' | 'longest_line') => (summary: RunSummary) => (summary[field] === null ? null : String(summary[field]))
  const perPeriodNote = [nowSummary, planSummary].some((summary) => summary?.basis === 'per_period') ? t('simulation.per_period_totals_note') : undefined

  return (
    <div className="page-stack">
      <div className="key-results" role="group" aria-label={t('results.key_results')}>
        <Card label={t('simulation.average_wait')} now={value(nowSummary, current !== null, minutesOf)} plan={value(planSummary, suggested !== null, minutesOf)} />
        <Card label={t('simulation.longest_line')} now={value(nowSummary, current !== null, count('longest_line'))} plan={value(planSummary, suggested !== null, count('longest_line'))} />
        <Card label={t('simulation.served_customers')} now={value(nowSummary, current !== null, count('served'))} plan={value(planSummary, suggested !== null, count('served'))} note={perPeriodNote} />
        <Card label={t('simulation.not_served_at_close')} now={value(nowSummary, current !== null, count('in_system_at_close'))} plan={value(planSummary, suggested !== null, count('in_system_at_close'))} note={perPeriodNote} />
      </div>
      {!shown && <p className="empty-state">{t(context.separate ? 'simulation.run_first' : 'simulation.run_first_period')}</p>}
      {shown?.kind === 'separate' && (
        <div role="status" className={`alert ${shown.result.overall_conservation ? 'alert-ok' : 'alert-error'}`}>
          {shown.result.overall_conservation ? t('simulation.sep_conservation_ok') : t('simulation.sep_conservation_bad')}
        </div>
      )}
      {dayCount > 1 && <p className="form-hint" data-testid="dates-note">{t('simulation.totals_all_dates', { dates: dayCount })}</p>}
      {chosenDay && chosenDay.dates.length > 1 && <DatePicker dates={chosenDay.dates} date={chosenDay.date} />}
      {shown && (
        <div className="grid g2">
          {dayTrace
            ? <WaitingChart trace={dayTrace} origin={origin} breaks={breaks} />
            : <section className="card"><h2 className="section-title">{t('simulation.chart_waiting')}</h2><p className="form-hint">{t('simulation.chart_waiting_needs_day')}</p></section>}
          {shownSummary ? <WaitByPeriod summary={shownSummary} /> : <section className="card"><h2 className="section-title">{t('simulation.chart_wait_by_period')}</h2><p className="form-hint">{t('simulation.summary_rerun')}</p></section>}
        </div>
      )}
      {shown && (
        <details className="card collapsible-card">
          <summary><h2 className="section-title">{t('simulation.more_results')}</h2></summary>
          {shownSummary && <PeriodTable summary={shownSummary} />}
          {shown.kind === 'separate'
            ? shown.result.periods.map((period) => <LaneTable key={period.time} period={period} />)
            : <LegacyMore rows={shown.result.results ?? []} />}
        </details>
      )}
    </div>
  )
}
