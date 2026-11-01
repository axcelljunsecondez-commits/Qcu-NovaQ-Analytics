import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  complete, currentGroupDetail, joinLevels, laneDetail, peakCell, planGroupDetail, presentLevels, separatePlanCells,
  separatePlanTakeaway, sharedPlanCells, todayCells, type GroupDetail, type LevelCell,
} from '../../lib/busyLevel'
import { fmtPctDecimal } from '../../lib/format'
import { headingText } from '../../lib/headingText'
import { dayStrip, levelClass, levelKey, periodWarnings, type ResultRow } from '../../lib/results'
import type { UtilizationBand } from '../../lib/utilization'
import { scenarioRows, type SelectedPlan } from './useSelectedPlan'

type LevelView = 'current' | 'plan'

function Level({ level }: { level: UtilizationBand | null }) {
  const { t } = useTranslation()
  return <span className={`status-badge ${levelClass(level)}`}>{t(levelKey(level))}</span>
}

/**
 * Tab 2 "Your day, by Busy Level" (spec 2026-10-29 §5.3, D19): one button per period with the
 * time, level word and workload percentage, so colour is never the only signal. Current comes from
 * today's calculated rows; Suggested plan from the selected plan. Choosing a period keeps the
 * `?period=` sync, and shows that period's cashier lines (separate) or counter group (shared).
 */
export function BusyLevelCard({ rows, separate, plan, planTarget, period, onPeriod }: {
  rows: ResultRow[]
  /** Today's rows are per cashier line. */
  separate: boolean
  plan: SelectedPlan
  /** The selected plan's target utilization; null when no plan is selected. */
  planTarget: number | null
  period: string | null
  onPeriod: (time: string | null) => void
}) {
  const { t } = useTranslation()
  const [chosen, setChosen] = useState<LevelView>('current')
  const separatePlan = plan.kind === 'separate' && plan.usable ? plan : null
  const sharedPlan = plan.kind === 'shared' && plan.usable ? plan : null
  const hasPlan = separatePlan !== null || sharedPlan !== null
  const view: LevelView = hasPlan ? chosen : 'current'
  const planRows = sharedPlan ? scenarioRows(sharedPlan.scenario) : []

  const cells: LevelCell[] = view === 'current' ? todayCells(rows)
    : separatePlan ? separatePlanCells(separatePlan.comparison, separatePlan.plan) : sharedPlanCells(planRows)
  // Today's warnings come from today's rows, so they belong under the Current grid only (review K-UC-4).
  const warnings = view === 'current' ? periodWarnings(dayStrip(rows), planTarget) : []
  if (cells.length === 0) return null

  const unavailable = t('results.unavailable')
  const pct = (value: number | null) => (value === null ? unavailable : fmtPctDecimal(value))
  const present = presentLevels(cells)
  const target = separatePlan?.target ?? sharedPlan?.target ?? null
  const runs = separatePlan?.plan.replications ?? null

  let takeaway: string | null = null
  const peak = peakCell(cells)
  if (complete(cells) && peak !== null) {
    const values = {
      levels: joinLevels(present.levels.map((level) => t(levelKey(level))), t('charts.conn_or')),
      value: pct(cells[peak].rho), time: cells[peak].time, target: target === null ? '' : fmtPctDecimal(target),
    }
    if (view === 'current') takeaway = t(separate ? 'charts.level_take_today' : 'charts.level_take_today_shared', values)
    else if (sharedPlan) takeaway = t('charts.level_take_plan_shared', values)
    else {
      const verdict = separatePlanTakeaway(cells, target)
      if (verdict?.kind === 'below') takeaway = t('charts.level_take_plan_separate', values)
      else if (verdict?.kind === 'above') takeaway = t('charts.level_take_plan_above', { ...values, count: verdict.count, total: cells.length })
    }
  }

  const chips: string[] = []
  if (view === 'current' || sharedPlan) chips.push(t('results.source_estimate'))
  if (view === 'plan' && separatePlan && runs !== null) chips.push(t('charts.level_chip_plan_simulated', { runs }))
  if (view === 'plan' && target !== null) chips.push(`${t('simulation.plan_target')}: ${fmtPctDecimal(target)}`)

  const selected = period !== null && cells.some((cell) => cell.time === period) ? period : null
  const group = (detail: GroupDetail | null) => detail && (
    <div className="table-scroll" role="region" aria-label={selected ?? undefined} tabIndex={0}>
      <table>
        <caption>{selected}</caption>
        <thead><tr><th scope="col">{t('results.col_counters')}</th><th scope="col">{t('results.col_workload')}</th><th scope="col">{t('results.col_level')}</th></tr></thead>
        <tbody><tr><td>{detail.counters ?? unavailable}</td><td>{pct(detail.rho)}</td><td><Level level={detail.level} /></td></tr></tbody>
      </table>
    </div>
  )
  let detail: ReactNode = null
  if (selected !== null) {
    if (!separate && view === 'current') detail = group(currentGroupDetail(rows, selected))
    else if (sharedPlan) detail = group(planGroupDetail(planRows, selected))
    else if (view === 'plan') detail = <p className="form-hint">{selected}: {t('charts.level_plan_no_lanes')}</p>
    else {
      const lanes = laneDetail(rows, selected)
      detail = lanes.length > 0 && (
        <div className="table-scroll" role="region" aria-label={selected} tabIndex={0}>
          <table>
            <caption>{selected}</caption>
            <thead><tr><th scope="col">{t('simulation.sep_lane')}</th><th scope="col">{t('results.col_workload')}</th><th scope="col">{t('results.col_level')}</th></tr></thead>
            <tbody>
              {lanes.map((lane) => <tr key={lane.lane}><th scope="row">{lane.lane}</th><td>{pct(lane.rho)}</td><td><Level level={lane.level} /></td></tr>)}
            </tbody>
          </table>
        </div>
      )
    }
  }

  return (
    <section className="card" aria-labelledby="busy-level-title" data-testid="busy-level">
      <h2 lang="en" id="busy-level-title" className="section-title">{headingText(t, 'results.day_by_level')}</h2>
      {takeaway && <p className="cv-takeaway">{takeaway}</p>}
      {hasPlan && (
        <div className="cv-view-switch" role="group" aria-label={t('charts.view_group')}>
          {(['current', 'plan'] as const).map((item) => (
            <button key={item} type="button" aria-pressed={item === view} onClick={() => setChosen(item)}>
              {t(item === 'current' ? 'simulation.run_current' : 'simulation.run_suggested')}
            </button>
          ))}
        </div>
      )}
      <ul className="cv-legend">
        {present.levels.map((level) => (
          <li key={level} className="cv-legend-item"><Level level={level} />{t(`results.range.${level.toLowerCase()}`)}</li>
        ))}
        {present.unknown && <li className="cv-legend-item"><Level level={null} /></li>}
      </ul>
      <div className="cv-ribbon" role="group" aria-label={t('charts.level_hours')}>
        {cells.map((cell) => (
          <button key={cell.time} type="button" className={`busy-cell ${levelClass(cell.level)}`} aria-pressed={selected === cell.time}
            aria-label={`${cell.time}: ${t(levelKey(cell.level))}, ${pct(cell.rho)}`}
            onClick={() => onPeriod(selected === cell.time ? null : cell.time)}>
            <span className="cv-t">{cell.time}</span>
            <span className="cv-l">{t(levelKey(cell.level))}</span>
            <span className="cv-v">{pct(cell.rho)}</span>
          </button>
        ))}
      </div>
      {warnings.length > 0 && (
        <div className="alert alert-warn" role="status">
          <ul className="busy-warnings">
            {warnings.map((warning) => (
              <li key={warning.time}>
                <strong>{warning.time}</strong>: {t(levelKey(warning.level))}
                {warning.level !== null && ` (${t(`results.range.${warning.level.toLowerCase()}`)})`}
                {warning.aboveTarget && planTarget !== null && ` · ${t('results.above_plan_target', { target: fmtPctDecimal(planTarget) })}`}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="cv-detail" aria-live="polite">{detail}</div>
      <details className="cv-details">
        <summary>{t('simulation.check_details')}</summary>
        <div className="cv-chips">{chips.map((chip) => <span key={chip} className="cv-chip">{chip}</span>)}</div>
        <p className="form-hint">{t('results.levels_note')}{separate ? ` ${t('results.strip_separate_note')}` : ''}</p>
      </details>
    </section>
  )
}
