import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { SimMcOut } from '../../api/types'
import { axisTicks } from '../../lib/chartScale'
import { fmtPctDecimal } from '../../lib/format'
import { failureRate, highestRiskIndex, mcAxisMax, mcPeriods, mcRangeText, storedMcParameters } from '../../lib/manyVariations'
import { RowChart, type ChartRow } from '../charts/RowChart'
import { InfoTip } from '../ui/InfoTip'

const SAME = 1e-9

function trialsText(trials: number): string {
  return trials.toLocaleString('en-US')
}

/**
 * "What is Many variations?" filled from the STORED run (spec 2026-10-29 §8.1, C5): trials, threshold
 * and cap as every stored row records them. Not shown when a value is missing or the rows disagree.
 */
export function ManyVariationsInfo({ rows }: { rows: SimMcOut[] }) {
  const { t } = useTranslation()
  const params = storedMcParameters(rows)
  if (!params.explainable) return null
  return (
    <InfoTip name={t('charts.mc_info_name')} ariaLabel={t('charts.mc_info_name')} text={t('charts.mc_info_text', {
      trials: trialsText(params.trials as number), target: fmtPctDecimal(params.threshold), cap: fmtPctDecimal(params.cap),
    })} />
  )
}

export interface ManyVariationsChartProps {
  rows: SimMcOut[]
  /** Separate lines name the highest-risk cashier of each period; a shared line has one row per period. */
  separate: boolean
  run: 'plan' | 'current'
  planTarget: number | null
  seed: unknown
  /** The full stored table, shown inside "details" as the table alternative. */
  children?: ReactNode
}

/**
 * Highest failure rate per period against the cap (owner decision B7). Point = stored failure_rate,
 * line = its stored 95% range, dashed line = the stored cap. Percentages use the decimal rule (B8).
 */
export function ManyVariationsChart({ rows, separate, run, planTarget, seed, children }: ManyVariationsChartProps) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<number | null>(null)
  const unavailable = t('results.unavailable')
  const params = storedMcParameters(rows)
  const periods = mcPeriods(rows)
  const highest = highestRiskIndex(periods)
  const allRatesKnown = rows.length > 0 && rows.every((row) => failureRate(row) !== null)
  const max = mcAxisMax(periods, params.cap)
  const lane = (row: SimMcOut) => (typeof row.queue_id === 'string' && row.queue_id !== '' ? row.queue_id : '—')
  const pct = (row: SimMcOut) => {
    const value = failureRate(row)
    return value === null ? unavailable : fmtPctDecimal(value)
  }

  const chartRows: ChartRow[] = periods.map((period, index) => {
    const worst = period.worst
    const complete = period.all.every((row) => failureRate(row) !== null)
    const value = complete ? failureRate(worst) : null
    const low = worst.failure_rate_ci_lower
    const high = worst.failure_rate_ci_upper
    const range = complete && typeof low === 'number' && typeof high === 'number' && Number.isFinite(low) && Number.isFinite(high) ? { low, high, cut: false } : null
    const lines = [period.time, ...(separate && complete ? [`${t('simulation.sep_lane')}: ${lane(worst)}`] : []),
      `${t('simulation.sep_mc_failure')}: ${complete ? pct(worst) : unavailable}`, `${t('charts.range_label')}: ${complete ? mcRangeText(worst) ?? unavailable : unavailable}`]
    return {
      key: period.time,
      label: period.time,
      marks: value === null ? [] : [{ kind: 'mc', value }],
      range,
      sideLabel: complete ? (separate ? `${lane(worst)} ${pct(worst)}` : pct(worst)) : unavailable,
      gapLabel: unavailable,
      highlight: allRatesKnown && index === highest,
      readout: lines,
      liveText: lines.join(', '),
    }
  })

  const top = highest >= 0 ? periods[highest] : null
  // "Closest to the cap" is true only at or below the cap (review K-UC-6); a higher stored rate gets the "above" text.
  const topRate = top ? failureRate(top.worst) : null
  const above = topRate !== null && params.cap !== null && topRate > params.cap + SAME
  const takeaway = allRatesKnown && top && params.cap !== null && params.trials !== null
    ? separate
      ? t(above ? 'charts.mc_take_separate_above' : 'charts.mc_take_separate', { cap: fmtPctDecimal(params.cap), time: top.time, lane: lane(top.worst), rate: pct(top.worst), trials: trialsText(params.trials) })
      : t(above ? 'charts.mc_take_shared_above' : 'charts.mc_take_shared', { cap: fmtPctDecimal(params.cap), time: top.time, rate: pct(top.worst), trials: trialsText(params.trials) })
    : null
  // The plan's-target wording is true only when the stored threshold is the plan's target.
  const failKey = !separate ? 'charts.mc_chip_fail_shared'
    : run === 'plan' && planTarget !== null && params.threshold !== null && Math.abs(params.threshold - planTarget) <= SAME
      ? 'charts.mc_chip_fail_plan' : 'charts.mc_chip_fail_current'
  const chips = [
    t(run === 'plan' ? 'simulation.run_suggested' : 'simulation.run_current'),
    ...(params.trials !== null ? [`${t('simulation.trials')}: ${trialsText(params.trials)}`] : []),
    ...(params.cap !== null ? [`${t('simulation.failure_rate_cap')}: ${fmtPctDecimal(params.cap)}`] : []),
    ...(typeof seed === 'number' ? [`${t('simulation.seed')}: ${seed}`] : []),
    ...(params.threshold !== null ? [t(failKey, { threshold: fmtPctDecimal(params.threshold) })] : []),
  ]
  const hasRange = chartRows.some((row) => row.range)
  const detail = separate && selected !== null ? periods[selected] : null

  return (
    <div className="page-stack" data-testid="many-variations-chart">
      {takeaway && <p className="cv-takeaway" data-testid="mc-take">{takeaway}</p>}
      <ul className="cv-legend">
        <li className="cv-legend-item">
          <svg className="cv-swatch" viewBox="0 0 14 14" aria-hidden="true" focusable="false"><circle className="cv-m-mc" cx={7} cy={7} r={4.5} /></svg>
          {t(separate ? 'charts.mc_legend_point_separate' : 'charts.mc_legend_point_shared')}
        </li>
        {hasRange && (
          <li className="cv-legend-item">
            <svg className="cv-swatch" viewBox="0 0 14 14" aria-hidden="true" focusable="false"><line className="cv-l-ci" x1={1} y1={7} x2={13} y2={7} /></svg>
            {t('charts.range_label')}
            {params.trials !== null && <InfoTip name={t('charts.info_range_name')} ariaLabel={t('charts.info_range_name')} text={t('charts.range_mc', { trials: trialsText(params.trials) })} />}
          </li>
        )}
        {params.cap !== null && (
          <li className="cv-legend-item">
            <svg className="cv-swatch" viewBox="0 0 14 14" aria-hidden="true" focusable="false"><line className="cv-l-cap" x1={7} y1={0} x2={7} y2={14} /></svg>
            {`${t('simulation.failure_rate_cap')} ${fmtPctDecimal(params.cap)}`}
          </li>
        )}
      </ul>
      <RowChart name={t('charts.mc_chart_name')} rows={chartRows} max={max} ticks={axisTicks(max, 5)} formatTick={(value) => fmtPctDecimal(value)}
        reference={params.cap !== null ? { value: params.cap, label: fmtPctDecimal(params.cap) } : null}
        initialRow={Math.max(0, highest)} onSelect={separate ? setSelected : undefined} sideWidth={separate ? 128 : 64} testId="mc-chart" />
      {detail && (
        <div className="table-scroll" role="region" aria-label={detail.time} tabIndex={0} data-testid="mc-detail">
          <table>
            <caption>{detail.time}</caption>
            <thead><tr><th scope="col">{t('simulation.sep_lane')}</th><th scope="col">{t('simulation.sep_mc_failure')}</th><th scope="col">{t('charts.range_label')}</th></tr></thead>
            <tbody>{detail.all.map((row, index) => (
              <tr key={`${lane(row)}-${index}`}><th scope="row">{lane(row)}</th><td>{pct(row)}</td><td>{mcRangeText(row) ?? unavailable}</td></tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <details className="cv-details">
        <summary>{t('simulation.check_details')}</summary>
        <div className="cv-chips">{chips.map((chip, index) => <span key={index} className={`cv-chip${index === 0 ? (run === 'plan' ? ' cv-chip-opt' : ' cv-chip-cur') : ''}`}>{chip}</span>)}</div>
        {children}
      </details>
    </div>
  )
}
