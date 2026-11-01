import { headingText } from '../../lib/headingText'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import type { RunSummary, SelectedDesPeriod, SimDesOut, SimulationTrace } from '../../api/types'
import { fmt, fmtDecimal, downloadCsv } from '../../lib/format'
import { currentMatrix, planMatrix } from '../../lib/longestLine'
import { SAMPLE_MINUTES, dayOrigin, dayPeriods, mergeDayTrace, scheduledBreaks, waitingThroughTheDay, wallClock, type ScheduledBreak } from '../../lib/replay'
import { InfoTip } from '../ui/InfoTip'
import { DatePicker } from './DatePicker'
import { LongestLineTable } from './LongestLineTable'
import { currentRun, runBasisKey, suggestedRun, type RunChoice, type SimulationContext } from './simulationContext'

/** Current and Suggested plan side by side, no arrow (owner decision B5): the two runs may be set up differently. */
function Pair({ now, plan, nowInfo, planInfo, mid }: { now: string; plan: string; nowInfo?: ReactNode; planInfo?: ReactNode; mid?: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="cv-pair">
      <p className="headline-pair"><span>{t('simulation.run_current')}: <strong>{now}</strong></span>{nowInfo}</p>
      <div className="cv-pair-mid">{mid}</div>
      <p className="headline-pair"><span>{t('simulation.run_suggested')}: <strong>{plan}</strong></span>{planInfo}</p>
    </div>
  )
}

function Card({ label, now, plan, mid }: { label: string; now: string; plan: string; mid?: ReactNode }) {
  return (
    <section className="card key-result" aria-label={label}>
      <h3 className="kpi-label">{label}</h3>
      <Pair now={now} plan={plan} mid={mid} />
    </section>
  )
}

/**
 * The basis ⓘ text, only where it is true (spec §7.3, App. B W12): the plan's continuous day includes the
 * Setup's breaks and staff finish serving the customers in line at closing. Separate lines (review K-UC-3):
 * the Current run is ONE continuous simulation over the Setup's periods, without breaks, that stops at
 * closing (simulation.py _simulate_parallel_segments_core, one env.run(until=horizon)); its summary says
 * "per_period" only because it reports no whole-day customer counts. The shared Current run does simulate
 * one period at a time (_simulate_segments_core), so shared keeps the per-period texts.
 */
function basisTextKey(context: SimulationContext, now: RunSummary | null, plan: RunSummary | null): string | null {
  if (!now || !plan || now.basis === plan.basis) return null
  if (now.basis !== 'per_period' || plan.basis !== 'continuous_day') return null
  const breaks = (context.analysis.queue_setup.breaks ?? []).length > 0
  if (context.separate) {
    if (context.perDateDays) return 'charts.key_basis_per_date_separate'
    return breaks ? 'charts.key_basis_separate' : 'charts.key_basis_no_breaks_separate'
  }
  if (context.perDateDays) return 'charts.key_basis_per_date'
  return breaks ? 'charts.key_basis' : 'charts.key_basis_no_breaks'
}

/** The "Unavailable" ⓘ text for a side without whole-day customer counts; true for that side's run only. */
function unavailableTextKey(context: SimulationContext, side: RunChoice): string {
  if (!context.separate) return 'charts.key_unavailable_explain'
  // Separate Current: one continuous run without customer totals. A separate plan with basis per_period
  // (per-date data without operating segments) does simulate each period alone.
  return side === 'current' ? 'charts.key_unavailable_explain_separate' : 'charts.key_unavailable_explain'
}

function WaitingChart({ trace, origin, breaks }: { trace: SimulationTrace; origin: number | null; breaks: ScheduledBreak[] }) {
  const { t } = useTranslation()
  const points = waitingThroughTheDay(trace)
  const max = Math.max(1, ...points.map((point) => point.waiting))
  const end = points.at(-1)?.hours ?? 0
  const label = (hours: number) => (origin === null ? `${fmtDecimal(hours, 2)} h` : wallClock(origin, hours))
  return (
    <section className="card" aria-labelledby="waiting-chart-title">
      <h2 lang="en" id="waiting-chart-title" className="section-title">{headingText(t, 'simulation.chart_waiting')}</h2>
      <ul className="cv-legend" data-testid="waiting-legend">
        <li className="cv-legend-item">
          <svg className="cv-swatch cv-swatch-wide" viewBox="0 0 24 12" aria-hidden="true" focusable="false"><line className="waiting-chart-line" x1={0} y1={6} x2={24} y2={6} /></svg>
          {t('simulation.chart_waiting')}
        </li>
        {breaks.length > 0 && (
          <li className="cv-legend-item">
            <svg className="cv-swatch cv-swatch-wide" viewBox="0 0 24 12" aria-hidden="true" focusable="false"><rect className="waiting-chart-break" x={0} y={0} width={24} height={12} /></svg>
            {t('help.guide.simulation.breaks.title')}
          </li>
        )}
      </ul>
      <svg className="waiting-chart" viewBox="0 0 600 160" role="img" aria-label={t('simulation.chart_waiting_summary', { max })} preserveAspectRatio="none">
        {breaks.map((item, index) => (
          <rect key={index} className="waiting-chart-break" x={end > 0 ? (item.startHours / end) * 600 : 0} width={end > 0 ? Math.max(2, ((item.endHours - item.startHours) / end) * 600) : 0} y={0} height={160} />
        ))}
        <polyline className="waiting-chart-line" fill="none" points={points.map((point) => `${end > 0 ? (point.hours / end) * 600 : 0},${160 - (point.waiting / max) * 150}`).join(' ')} />
      </svg>
      <p className="form-hint">{t('simulation.chart_waiting_axis', { start: label(0), end: label(end), max, minutes: SAMPLE_MINUTES })}</p>
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
      <h2 lang="en" id="wait-period-title" className="section-title">{headingText(t, 'simulation.chart_wait_by_period')}</h2>
      <div className="hbar-chart" role="img" aria-labelledby="wait-period-title">
        {/* Keyed by position too: a per-date run can list the same period label twice. */}
        {values.map((item, index) => (
          <div className="hbar-row" key={`${index}-${item.time}`}>
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
          {summary.periods.map((period, index) => (
            <tr key={`${index}-${period.time}`}>
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
        <thead><tr><th scope="col">{t('simulation.sep_lane')}</th><th scope="col">{t('simulation.sep_active')}</th><th scope="col">{t('simulation.sep_arrivals')}</th><th scope="col">{t('simulation.sep_served')}</th><th scope="col"><InfoTip name="Wq (min)" label="Wq (min)" text={t('simulation.tip_wq')} /></th><th scope="col"><InfoTip name="ρ" label="ρ" text={t('simulation.tip_rho')} /></th></tr></thead>
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
          <thead><tr><th scope="col">{t('common.time')}</th>{showLine && <th scope="col">{t('analyses.service_line')}</th>}<th scope="col">{t('simulation.status')}</th><th scope="col"><InfoTip name="ρ" label="ρ" text={t('simulation.tip_rho')} /></th><th scope="col">Lq</th><th scope="col">{t('system.sim_wait_minutes')}</th><th scope="col">{t('simulation.max_queue')}</th><th scope="col">{t('simulation.served')}</th><th scope="col">{t('simulation.dropped')}</th></tr></thead>
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
      <button type="button" className="btn-ghost" onClick={() => downloadCsv('novaq_unified_des.csv', rows as unknown as Record<string, unknown>[])}>{t('simulation.download_csv')}</button>
    </>
  )
}

/**
 * Key results (D27, D30; owner decision B5): two headline cards Current and Suggested plan, the closing
 * alert, the Longest Single Line table (separate lines) and two charts; Customer Served and the rest
 * under More results.
 */
export function KeyResultsView({ context, run }: { context: SimulationContext; run: RunChoice }) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const suggested = suggestedRun(context)
  const current = currentRun(context)
  const nowSummary = current?.summary ?? null
  const planSummary = suggested?.result.summary ?? null
  const shown = run === 'suggested' ? suggested : current ? { kind: 'legacy' as const, result: current } : null
  const shownSummary = run === 'suggested' ? planSummary : nowSummary
  const setup = context.analysis.queue_setup
  const origin = dayOrigin(setup)
  const breaks = context.separate ? scheduledBreaks(setup) : []
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
  const count = (field: 'served' | 'longest_line' | 'in_system_at_close') => (summary: RunSummary) => (summary[field] === null ? null : String(summary[field]))

  const basisKey = basisTextKey(context, nowSummary, planSummary)
  const basisInfo = basisKey ? <InfoTip name={t('charts.info_basis_name')} ariaLabel={t('charts.info_basis_name')} text={t(basisKey)} /> : undefined
  const nowWait = nowSummary ? minutesOf(nowSummary) : null
  const planWait = planSummary ? minutesOf(planSummary) : null
  const takeaway = nowSummary && planSummary && nowWait && planWait
    ? t(nowSummary.basis === planSummary.basis ? 'charts.key_take_same_basis' : 'charts.key_take', { current: nowWait, plan: planWait })
    : null
  const atClose = planSummary?.in_system_at_close
  // The alert says "in the plan's simulated day". A per-date plan's value is the server's total over all
  // dates (workflow.py at_close_total), so the alert is true only for one simulated day; with more dates the
  // value stays in More Results under its own label, beside the "totals add up all dates" note.
  const planDays = suggested?.kind === 'separate' ? suggested.result.days?.length ?? 0 : 0
  const oneSimulatedDay = context.perDateDays ? planDays === 1 : planDays <= 1
  // The "Unavailable" explanation is shown only for a side whose run reports no whole-day customer counts.
  const unavailableInfo = (summary: RunSummary | null, side: RunChoice) => (summary?.basis === 'per_period' && summary.served === null
    ? <InfoTip name={t('charts.info_unavailable_name')} ariaLabel={t('charts.info_unavailable_name')} text={t(unavailableTextKey(context, side))} />
    : undefined)

  const seedChip = (seed: unknown) => (typeof seed === 'number' ? `${t('simulation.seed')}: ${seed}` : t('charts.chip_seed_not_saved'))
  // Only the selected separate-lines plan models the Setup's breaks; Current and the legacy shared run have none.
  const planBreaksKey = context.selectedSeparate && (setup.breaks ?? []).length > 0 ? 'charts.chip_breaks_included' : 'charts.chip_no_breaks'
  // Separate Current's basis chip already says "no breaks" (simulation.run_basis_continuous_no_breaks).
  const currentChips = [t('simulation.run_current'), t(runBasisKey(context, 'current')), ...(context.separate ? [] : [t('charts.chip_no_breaks')]), seedChip(context.workflow.des_current?.params.seed)]
  const planChips = [t('simulation.run_suggested'), t(runBasisKey(context, 'suggested')), t(planBreaksKey), seedChip(context.workflow.des?.params.seed)]

  const matrix = !context.separate || !shown ? null
    : shown.kind === 'separate' ? (chosenDay ? planMatrix(chosenDay.periods, setup.queue_ids ?? []) : null)
      : currentMatrix(shown.result.results ?? [], setup)
  // The table is separate lines only; its Current run is one continuous run without breaks (K-UC-3).
  const longestChips = run === 'current' ? currentChips : planChips

  return (
    <div className="page-stack">
      {takeaway && <p className="cv-takeaway" data-testid="key-take">{takeaway}</p>}
      <div className="key-results" role="group" aria-label={t('results.key_results')}>
        <Card label={t('simulation.average_wait')} now={value(nowSummary, current !== null, minutesOf)} plan={value(planSummary, suggested !== null, minutesOf)} mid={basisInfo} />
        <Card label={t('simulation.longest_line')} now={value(nowSummary, current !== null, count('longest_line'))} plan={value(planSummary, suggested !== null, count('longest_line'))} mid={basisInfo} />
      </div>
      {oneSimulatedDay && typeof atClose === 'number' && atClose > 0 && (
        <p role="status" className="alert alert-warn" data-testid="closing-alert">{t('charts.closing_alert', { count: atClose })}</p>
      )}
      {(current || suggested) && (
        <details className="cv-details" data-testid="key-details">
          <summary>{t('simulation.check_details')}</summary>
          <div className="cv-chips">
            {current && <span className="cv-chip cv-chip-cur">{currentChips.join(' · ')}</span>}
            {suggested && <span className="cv-chip cv-chip-opt">{planChips.join(' · ')}</span>}
          </div>
        </details>
      )}
      {!shown && <p className="empty-state">{t(runBasisKey(context, run) === 'simulation.run_basis_per_period' ? 'simulation.run_first_period' : 'simulation.run_first')}</p>}
      {shown?.kind === 'separate' && (
        <div role="status" className={`alert ${shown.result.overall_conservation ? 'alert-ok' : 'alert-error'}`}>
          {shown.result.overall_conservation ? t('simulation.sep_conservation_ok') : t('simulation.sep_conservation_bad')}
        </div>
      )}
      {dayCount > 1 && <p className="form-hint" data-testid="dates-note">{t('simulation.totals_all_dates', { dates: dayCount })}</p>}
      {chosenDay && chosenDay.dates.length > 1 && <DatePicker dates={chosenDay.dates} date={chosenDay.date} />}
      {matrix && <LongestLineTable key={`${run}-${chosenDay?.date ?? ''}`} matrix={matrix} kind={run === 'current' ? 'current' : 'plan'} chips={longestChips} />}
      {shown && (
        <div className="grid g2">
          {dayTrace
            ? <WaitingChart trace={dayTrace} origin={origin} breaks={breaks} />
            : <section className="card"><h2 lang="en" className="section-title">{headingText(t, 'simulation.chart_waiting')}</h2><p className="form-hint">{t(context.separate && run === 'current' ? 'simulation.chart_waiting_needs_plan_day' : 'simulation.chart_waiting_needs_day')}</p></section>}
          {shownSummary ? <WaitByPeriod summary={shownSummary} /> : <section className="card"><h2 lang="en" className="section-title">{headingText(t, 'simulation.chart_wait_by_period')}</h2><p className="form-hint">{t('simulation.summary_rerun')}</p></section>}
        </div>
      )}
      {shown && (
        <details className="card collapsible-card">
          <summary><h2 lang="en" className="section-title">{headingText(t, 'simulation.more_results')}</h2></summary>
          <section className="key-result" aria-label={t('simulation.served_customers')} data-testid="more-served">
            <h3 className="kpi-label">{t('simulation.served_customers')}</h3>
            <Pair now={value(nowSummary, current !== null, count('served'))} plan={value(planSummary, suggested !== null, count('served'))}
              nowInfo={unavailableInfo(nowSummary, 'current')} planInfo={unavailableInfo(planSummary, 'suggested')} />
          </section>
          {!oneSimulatedDay && typeof atClose === 'number' && (
            <section className="key-result" aria-label={t('simulation.not_served_at_close')} data-testid="more-at-close">
              <h3 className="kpi-label">{t('simulation.not_served_at_close')}</h3>
              <Pair now={value(nowSummary, current !== null, count('in_system_at_close'))} plan={value(planSummary, suggested !== null, count('in_system_at_close'))}
                nowInfo={unavailableInfo(nowSummary, 'current')} />
              {planDays > 1 && <p className="form-hint">{t('simulation.totals_all_dates', { dates: planDays })}</p>}
            </section>
          )}
          {shownSummary && <PeriodTable summary={shownSummary} />}
          {shown.kind === 'separate'
            ? shown.result.periods.map((period) => <LaneTable key={period.time} period={period} />)
            : <LegacyMore rows={shown.result.results ?? []} />}
        </details>
      )}
    </div>
  )
}
