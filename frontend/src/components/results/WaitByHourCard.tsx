import { useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { ObservedWaitPeriod, PeriodArrivals } from '../../api/types'
import type { StaffingSetup } from '../../lib/longestLine'
import { headingText } from '../../lib/headingText'
import { axisTicks, niceMax } from '../../lib/chartScale'
import { fmtDecimal, fmtPctDecimal } from '../../lib/format'
import type { ResultRow } from '../../lib/results'
import {
  allHourPeriods, anyCut, countersByPeriod, largestShown, separatePlanWaitRows, setupCountersByPeriod, sharedPlanWaitRows, takeawayRow, todayWaitRows, waitGap,
  type WaitRow, type WaitView,
} from '../../lib/waitChart'
import { LineChart, type LineSeries } from '../charts/LineChart'
import { RowChart, type ChartMark, type ChartRow } from '../charts/RowChart'
import { InfoTip } from '../ui/InfoTip'
import { scenarioRows, type SelectedPlan } from './useSelectedPlan'

type Kind = 'est' | 'rec' | 'plan' | 'range' | 'clip' | 'line-rec' | 'line-est'
type Measure = 'wait' | 'arrivals'

function Swatch({ kind }: { kind: Kind }) {
  if (kind === 'line-rec' || kind === 'line-est') {
    const line = kind === 'line-rec' ? 'rec' : 'est'
    return (
      <svg className="cv-swatch cv-swatch-wide cv-swatch-line" viewBox="0 0 24 12" aria-hidden="true" focusable="false">
        <line className={`cv-trace cv-trace-${line}`} x1="1" y1="6" x2="23" y2="6" />
        {line === 'rec' ? <circle className="cv-node cv-node-rec" cx="12" cy="6" r="3.2" /> : <path className="cv-node cv-node-est" d="M12 2 L16 6 L12 10 L8 6Z" />}
      </svg>
    )
  }
  return (
    <svg className="cv-swatch" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
      {kind === 'rec' && <path className="cv-m-rec" d="M7 1 L13 7 L7 13 L1 7Z" />}
      {kind === 'est' && <circle className="cv-m-est" cx="7" cy="7" r="5" />}
      {kind === 'plan' && <circle className="cv-m-plan" cx="7" cy="7" r="4.5" />}
      {kind === 'range' && <line className="cv-l-ci" x1="1" y1="7" x2="13" y2="7" />}
      {kind === 'clip' && <path className="cv-m-clip" d="M1 7 L7 3 L7 11Z" />}
    </svg>
  )
}

function Legend({ items }: { items: { kind: Kind; label: string; extra?: ReactNode }[] }) {
  return (
    <ul className="cv-legend">
      {items.map((item) => <li key={item.kind} className="cv-legend-item"><Swatch kind={item.kind} />{item.label}{item.extra}</li>)}
    </ul>
  )
}

/**
 * Tab 1 "What the plan changes" (spec 2026-10-29 §5.2; HTML5 redesign Phase C, 2026-11-25).
 * Measure Wait: Today view = Recorded (blue line) vs Estimated (gold dashed line) by period, read out with
 * their Gap; Plan view = Estimated vs Suggested plan as one row per period (unchanged). Recorded is never
 * drawn next to the plan. Separate plans show their simulated 95% range, cut at 0 with a marker;
 * shared plans are calculated on both sides, so they have no range and no "simulated" wording.
 * Measure Arrivals: the server's customers per hour for each period (arrivals_by_period), on its own
 * period list. A missing value is a gap, never zero. The card shows when either measure has data (OD-C1).
 */
export function WaitByHourCard({ observed, rows, selectedModel, separate, plan, staffing, footer, arrivals = [], hasRecords = true, fileKey = '' }: {
  /** Recorded/estimated periods of the shown file, or null when it has no recorded waits. */
  observed: ObservedWaitPeriod[] | null
  rows: ResultRow[]
  selectedModel: string | null
  /** The analysis uses separate cashier lines. */
  separate: boolean
  plan: SelectedPlan
  /** Separate lines: the Setup and the file's records, for the Today view's staffed-cashier counts (K-UC-5). */
  staffing?: { setup: StaffingSetup; records: Record<string, unknown>[] | null }
  /** Shown below the chart (the no-plan prompt, D21 / OD-4). */
  footer?: ReactNode
  /** Customers per hour by period of the shown file (GET /current arrivals_by_period). */
  arrivals?: PeriodArrivals[]
  /** The shown file has customer records; without them recorded waits cannot exist. */
  hasRecords?: boolean
  /** The shown file: a new file replays the chart reveal (OD-C6); a refetch of the same file does not. */
  fileKey?: string | number
}) {
  const { t } = useTranslation()
  const separatePlan = plan.kind === 'separate' && plan.usable ? plan : null
  const sharedPlan = plan.kind === 'shared' && plan.usable ? plan : null
  const views: WaitView[] = [...(observed ? ['today' as const] : []), ...(separatePlan || sharedPlan ? ['plan' as const] : [])]
  const [chosen, setChosen] = useState<WaitView>(views[0] ?? 'today')
  const [measureChoice, setMeasureChoice] = useState<Measure | null>(null)
  const [revealToken, setRevealToken] = useState(0)
  const revealMemory = useRef<string | null>(null)
  const arrivalsHasData = arrivals.some((period) => period.arrivals_per_hour !== null && Number.isFinite(period.arrivals_per_hour))
  const waitHasData = views.length > 0
  if (!waitHasData && !arrivalsHasData) return footer ? <>{footer}</> : null
  const view = views.includes(chosen) ? chosen : (views[0] ?? 'today')
  const measure: Measure = measureChoice ?? (waitHasData ? 'wait' : 'arrivals')
  const revealKey = `${fileKey}|${revealToken}`
  const chooseMeasure = (next: Measure) => {
    setMeasureChoice(next)
    // Every measure click replays the reveal, including on the measure already shown (owner decision).
    setRevealToken((token) => token + 1)
  }

  const unavailable = t('results.unavailable')
  const unit = t('results.min')
  const counters = t('results.col_counters')
  const waitText = (value: number | null, unstable = false) => (unstable ? t('results.cant_keep_up_wait') : value === null ? unavailable : `${fmtDecimal(value, 1)} ${unit}`)
  const count = (value: number | null) => (value === null ? unavailable : String(value))
  // Separate Today view: a period whose Setup staffing is not known shows "—", never a count from the rows.
  const countersText = (row: WaitRow) => (view !== 'today' ? `${count(row.countersNow)} → ${count(row.countersPlan)}`
    : separate && row.countersNow === null ? '—' : count(row.countersNow))
  const rangeText = (row: WaitRow) => (row.range ? `${fmtDecimal(row.range.low, 1)} – ${fmtDecimal(row.range.high, 1)} ${unit}` : unavailable)

  const waitRows: WaitRow[] = view === 'today'
    ? todayWaitRows(observed ?? [], separate
      ? (staffing ? setupCountersByPeriod((observed ?? []).map((period) => period.time), staffing.setup, staffing.records) : new Map())
      : countersByPeriod(rows))
    : separatePlan ? separatePlanWaitRows(separatePlan.comparison, separatePlan.plan) : sharedPlanWaitRows(scenarioRows(sharedPlan?.scenario))
  const highlight = takeawayRow(waitRows)
  const cut = view === 'plan' && separatePlan !== null && anyCut(waitRows)
  const planLabel = separatePlan ? t('charts.wait_legend_plan_simulated') : t('simulation.run_suggested')
  const max = niceMax(largestShown(waitRows, view))
  const runs = separatePlan?.plan.replications ?? null
  const seed = separatePlan?.plan.base_seed ?? null
  const target = separatePlan?.target ?? sharedPlan?.target ?? null

  let takeaway: string | null = null
  if (highlight !== null) {
    const row = waitRows[highlight]
    const values = { time: row.time, est: waitText(row.estimated), rec: waitText(row.recorded), plan: waitText(row.plan, row.planUnstable) }
    takeaway = view === 'today' ? t('charts.wait_take_today', values)
      : separatePlan ? t('charts.wait_take_plan_separate', values) : t('charts.wait_take_plan_shared', values)
  }

  const estimateLine = (row: WaitRow) => `${t('results.estimated')} (${t('results.source_estimate')}): ${waitText(row.estimated, row.estimatedUnstable)}`
  const chartRows: ChartRow[] = waitRows.map((row, index) => {
    const marks: ChartMark[] = []
    if (row.estimated !== null) marks.push({ kind: 'est', value: row.estimated })
    if (view === 'today' && row.recorded !== null) marks.push({ kind: 'rec', value: row.recorded })
    if (view === 'plan' && row.plan !== null) marks.push({ kind: 'plan', value: row.plan })
    const readout = [row.time, `${counters}: ${countersText(row)}`]
    let liveText: string
    if (view === 'today') {
      readout.push(`${t('results.recorded')} (${t('results.source_data')}): ${waitText(row.recorded)}`, estimateLine(row))
      const gap = waitGap(row.recorded, row.estimated)
      if (gap !== null) readout.push(`${t('charts.wait_gap')}: ${fmtDecimal(gap, 1)} ${unit}`)
      if (row.flagged) readout.push(t('current.observed_flagged'))
      liveText = `${row.time}: ${t('results.recorded')} ${waitText(row.recorded)}, ${t('results.estimated')} ${waitText(row.estimated)}${row.flagged ? `, ${t('current.observed_flagged')}` : ''}`
    } else {
      readout.push(estimateLine(row), `${planLabel}: ${waitText(row.plan, row.planUnstable)}`)
      if (separatePlan) readout.push(`${t('charts.range_label')}: ${rangeText(row)}`)
      if (row.range?.cut) readout.push(t('charts.clip_legend'))
      liveText = `${row.time}: ${t('results.estimated')} ${waitText(row.estimated, row.estimatedUnstable)}, ${planLabel} ${waitText(row.plan, row.planUnstable)}`
        + (separatePlan ? `, ${t('charts.range_label')} ${rangeText(row)}` : '') + (row.range?.cut ? `, ${t('charts.clip_legend')}` : '')
    }
    return {
      key: row.time,
      label: row.time,
      sublabel: `${counters}: ${countersText(row)}`,
      marks,
      range: view === 'plan' && separatePlan ? row.range : null,
      connect: view === 'today' && row.recorded !== null && row.estimated !== null ? [row.estimated, row.recorded] : null,
      gapLabel: row.estimatedUnstable || row.planUnstable ? t('results.cant_keep_up_wait') : unavailable,
      highlight: index === highlight,
      readout,
      liveText,
    }
  })

  const legend: { kind: Kind; label: string; extra?: ReactNode }[] = []
  if (view === 'today') legend.push({ kind: 'line-rec', label: t('results.recorded'), extra: <span className="cv-chip cv-chip-data">{t('results.source_data')}</span> })
  legend.push({ kind: view === 'today' ? 'line-est' : 'est', label: t('results.estimated'), extra: <span className="cv-chip cv-chip-est">{t('results.source_estimate')}</span> })
  if (view === 'plan') {
    legend.push({ kind: 'plan', label: planLabel, extra: separatePlan ? undefined : <span className="cv-chip cv-chip-opt">{t('results.source_estimate')}</span> })
    if (separatePlan) {
      legend.push({ kind: 'range', label: t('charts.range_label'),
        extra: runs !== null ? <InfoTip name={t('charts.range_label')} ariaLabel={t('charts.info_range_name')} text={t('charts.range_wait', { runs })} /> : undefined })
      if (cut) legend.push({ kind: 'clip', label: t('charts.clip_legend'), extra: <InfoTip name={t('charts.clip_legend')} ariaLabel={t('charts.info_clip_name')} text={t('charts.clip_text')} /> })
    }
  }

  const chips: string[] = []
  if (selectedModel) chips.push(t(separate ? 'charts.wait_chip_estimate_separate' : 'charts.wait_chip_estimate_shared', { model: selectedModel }))
  if (view === 'plan' && separatePlan && runs !== null && seed !== null) chips.push(t('charts.wait_chip_plan_simulated', { runs, seed }))
  if (view === 'plan' && target !== null) chips.push(`${t('simulation.plan_target')}: ${fmtPctDecimal(target)}`)
  const hourly = allHourPeriods(waitRows.map((row) => row.time))
  // Today is a line chart: only the hourly note is approved; non-hour periods show no note (Phase C stop item).
  const axisNote = view === 'today' ? (hourly ? t('charts.line_axis_note') : null) : hourly ? t('charts.wait_axis_note') : t('charts.wait_axis_note_period')
  const todaySeries: LineSeries[] = [
    { kind: 'rec', values: waitRows.map((row) => row.recorded) },
    { kind: 'est', values: waitRows.map((row) => row.estimated) },
  ]
  const todayEmpty = waitRows.every((row) => row.recorded === null && row.estimated === null)

  const arrivalText = (value: number | null) => (value === null ? unavailable : t('results.customers_per_hour', { count: value, value: fmtDecimal(value) }))
  const arrivalValues = arrivals.map((period) => (period.arrivals_per_hour !== null && Number.isFinite(period.arrivals_per_hour) ? period.arrivals_per_hour : null))
  const arrivalMax = niceMax(Math.max(0, ...arrivalValues.map((value) => value ?? 0)))
  const arrivalHourly = allHourPeriods(arrivals.map((period) => period.time))

  const measureSwitch = (
    <div className="cv-view-switch cv-measure-switch" role="group" aria-label={t('charts.measure_group')}>
      {(['wait', 'arrivals'] as const).map((item) => (
        <button key={item} type="button" aria-pressed={item === measure} onClick={() => chooseMeasure(item)}>
          {item === 'wait' ? t('charts.measure_wait') : t('simulation.sep_arrivals')}
        </button>
      ))}
    </div>
  )

  if (measure === 'arrivals') {
    return (
      <section className="card" aria-labelledby="wait-hour-title" data-testid="wait-by-hour">
        <h2 lang="en" id="wait-hour-title" className="section-title">{headingText(t, 'results.arrivals_by_period')}</h2>
        {measureSwitch}
        <p className="form-hint">{t('current.arrivals_title')}</p>
        {arrivalsHasData ? (
          <LineChart name={t('charts.arrivals_chart_name')} periods={arrivals.map((period) => period.time)} series={[{ kind: 'arr', values: arrivalValues }]}
            max={arrivalMax} ticks={axisTicks(arrivalMax, 5)} formatTick={(value) => fmtDecimal(value)}
            readout={(index) => [arrivals[index].time, arrivalText(arrivalValues[index])]}
            liveText={(index) => `${arrivals[index].time} · ${arrivalText(arrivalValues[index])}`}
            revealKey={revealKey} revealMemory={revealMemory} testId="arrivals-chart" />
        ) : <p className="form-hint" data-testid="arrivals-unavailable">{unavailable}</p>}
        <p className="cv-axis-title">{t('results.col_arrivals')}</p>
        <details className="cv-details">
          <summary>{t('simulation.check_details')}</summary>
          {arrivalHourly && <p className="form-hint">{t('charts.line_axis_note')}</p>}
          <details>
            <summary>{t('charts.show_table')}</summary>
            <div className="table-scroll" role="region" aria-label={t('charts.show_table')} tabIndex={0}>
              <table>
                <caption>{t('results.arrivals_table')}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t('common.time')}</th>
                    <th scope="col">{t('results.col_arrivals')}</th>
                  </tr>
                </thead>
                <tbody>
                  {arrivals.map((period, index) => (
                    <tr key={`${index}-${period.time}`}>
                      <th scope="row">{period.time}</th>
                      <td>{arrivalValues[index] === null ? unavailable : fmtDecimal(arrivalValues[index])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </details>
        {footer}
      </section>
    )
  }

  if (!waitHasData) {
    return (
      <section className="card" aria-labelledby="wait-hour-title" data-testid="wait-by-hour">
        <h2 lang="en" id="wait-hour-title" className="section-title">{headingText(t, 'results.wait_comparison')}</h2>
        {measureSwitch}
        <p className="form-hint" data-testid="wait-unavailable">{hasRecords ? unavailable : t('results.recorded_unavailable')}</p>
        {footer}
      </section>
    )
  }

  return (
    <section className="card" aria-labelledby="wait-hour-title" data-testid="wait-by-hour">
      <h2 lang="en" id="wait-hour-title" className="section-title">{headingText(t, 'results.wait_comparison')}</h2>
      {measureSwitch}
      {takeaway && <p className="cv-takeaway">{takeaway}</p>}
      {views.length > 1 && (
        <div className="cv-view-switch" role="group" aria-label={t('charts.view_group')}>
          {views.map((item) => (
            <button key={item} type="button" aria-pressed={item === view} onClick={() => setChosen(item)}>
              {item === 'today' ? t('results.wait_chart') : t('charts.wait_view_plan')}
            </button>
          ))}
        </div>
      )}
      <Legend items={legend} />
      {view === 'today' ? (todayEmpty ? <p className="form-hint" data-testid="wait-unavailable">{unavailable}</p> : (
        <LineChart name={t('charts.wait_chart_name')} periods={waitRows.map((row) => row.time)} series={todaySeries} max={max} ticks={axisTicks(max, 5)}
          formatTick={(value) => fmtDecimal(value, 1)} unit={unit} readout={(index) => chartRows[index].readout} liveText={(index) => chartRows[index].liveText}
          highlight={highlight} initialIndex={highlight ?? 0} revealKey={revealKey} revealMemory={revealMemory} testId="wait-chart" />
      )) : (
        <RowChart key={view} name={t('charts.wait_chart_name')} rows={chartRows} max={max} ticks={axisTicks(max, 5)} formatTick={(value) => fmtDecimal(value, 1)}
          unit={unit} initialRow={highlight ?? 0} testId="wait-chart" />
      )}
      <p className="cv-axis-title">{t('charts.wait_axis')}</p>
      <details className="cv-details">
        <summary>{t('simulation.check_details')}</summary>
        {chips.length > 0 && <div className="cv-chips">{chips.map((chip) => <span key={chip} className="cv-chip">{chip}</span>)}</div>}
        {axisNote && <p className="form-hint">{axisNote}</p>}
        <details>
          <summary>{t('charts.show_table')}</summary>
          <div className="table-scroll" role="region" aria-label={t('charts.show_table')} tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th scope="col">{t('common.time')}</th>
                  <th scope="col">{counters}</th>
                  {view === 'today' && <th scope="col">{t('results.recorded')}</th>}
                  <th scope="col">{t('results.estimated')}</th>
                  {view === 'plan' && <th scope="col">{t('simulation.run_suggested')}</th>}
                  {view === 'plan' && separatePlan && <th scope="col">{t('charts.range_label')}</th>}
                </tr>
              </thead>
              <tbody>
                {waitRows.map((row) => (
                  <tr key={row.time}>
                    <th scope="row">{row.time}{row.flagged && view === 'today' && <small className="plan-target-flag">{t('current.observed_flagged')}</small>}</th>
                    <td>{countersText(row)}</td>
                    {view === 'today' && <td>{waitText(row.recorded)}</td>}
                    <td>{waitText(row.estimated, row.estimatedUnstable)}</td>
                    {view === 'plan' && <td>{waitText(row.plan, row.planUnstable)}</td>}
                    {view === 'plan' && separatePlan && <td>{rangeText(row)}{row.range?.cut ? ` (${t('charts.clip_legend')})` : ''}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </details>
      {footer}
    </section>
  )
}
