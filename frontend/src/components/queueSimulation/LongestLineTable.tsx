import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import { headingText } from '../../lib/headingText'
import { fmtPctDecimal } from '../../lib/format'
import type { LongestMatrix } from '../../lib/longestLine'

const NARROW_PX = 520

/** ≤520 px (the card or the window): cashier headers read 1…n with a key line (spec 2026-10-29 §7.4). */
function useNarrow(ref: RefObject<HTMLElement | null>): boolean {
  const [narrow, setNarrow] = useState(false)
  useEffect(() => {
    const measure = () => {
      const width = ref.current?.clientWidth ?? 0
      setNarrow((width > 0 && width <= NARROW_PX) || window.innerWidth <= NARROW_PX)
    }
    measure()
    window.addEventListener('resize', measure)
    const observer = typeof ResizeObserver === 'undefined' || !ref.current ? null : new ResizeObserver(measure)
    if (observer && ref.current) observer.observe(ref.current)
    return () => {
      window.removeEventListener('resize', measure)
      observer?.disconnect()
    }
  }, [ref])
  return narrow
}

/** Decorative tint scaled to the run's largest value; the number in the cell is the value. */
function tint(value: number, max: number | null): string {
  const share = max !== null && max > 0 ? value / max : 0
  return `color-mix(in srgb, var(--color-data-current) ${Math.round(8 + share * 37)}%, var(--color-bg-surface))`
}

const CLOSED_SWATCH = 'repeating-linear-gradient(135deg, var(--color-bg-subtle) 0 3px, var(--color-bg-surface) 3px 6px)'

/**
 * Longest Single Line per hour and cashier (owner decision B6). Cells are the run's stored max_queue;
 * a hatched cell is not staffed (text alternative "Closed / not staffed"), never zero. Arrow keys,
 * Home and End move between cells; the focused cell is read out below the table and to a live region.
 */
export function LongestLineTable({ matrix, kind, chips }: { matrix: LongestMatrix; kind: 'current' | 'plan'; chips: string[] }) {
  const { t } = useTranslation()
  const wrap = useRef<HTMLDivElement>(null)
  const table = useRef<HTMLTableElement>(null)
  const narrow = useNarrow(wrap)
  const [active, setActive] = useState<{ row: number; col: number } | null>(null)
  const columns = matrix.lanes.length + 1
  const unavailable = t('results.unavailable')
  const closed = t('simulation.state_closed')
  const focusCell = (row: number, col: number) => {
    const next = { row: Math.min(Math.max(row, 0), matrix.rows.length - 1), col: Math.min(Math.max(col, 0), columns - 1) }
    setActive(next)
    table.current?.querySelector<HTMLElement>(`td[data-row="${next.row}"][data-col="${next.col}"]`)?.focus()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTableCellElement>, row: number, col: number) => {
    const target = event.key === 'ArrowDown' ? [row + 1, col] : event.key === 'ArrowUp' ? [row - 1, col]
      : event.key === 'ArrowRight' ? [row, col + 1] : event.key === 'ArrowLeft' ? [row, col - 1]
        : event.key === 'Home' ? [row, 0] : event.key === 'End' ? [row, columns - 1] : null
    if (!target) return
    event.preventDefault()
    focusCell(target[0], target[1])
  }
  const tabStop = active ?? { row: 0, col: 0 }
  const complete = (period: LongestMatrix['rows'][number]) => period.cells.length === matrix.lanes.length
    && period.cells.every((cell) => cell.staffed === false || (cell.staffed === true && cell.value !== null && Number.isFinite(cell.value)))

  const lines = (row: number, col: number): string[] => {
    const period = matrix.rows[row]
    if (!period) return []
    if (col === matrix.lanes.length) return [period.time, `${t('simulation.longest_line')}: ${(complete(period) ? period.max : null) ?? unavailable}`]
    const cell = period.cells[col]
    if (cell.staffed === false) return [`${period.time} · ${cell.lane}`, closed]
    return [`${period.time} · ${cell.lane}`, `${t('charts.longest_tip_max')}: ${cell.value ?? unavailable}`,
      `${t('results.col_workload')}: ${cell.rho === null ? unavailable : fmtPctDecimal(cell.rho)}`]
  }
  const readout = active ? lines(active.row, active.col) : []

  const where = matrix.peaks.map((peak) => `${peak.lane} ${t('charts.conn_during')} ${peak.time}`).join('; ')
  // The hatching key only where "not staffed" is known (a Current run whose Setup staffing is unknown has none).
  const showClosedKey = matrix.staffingKnown || matrix.rows.some((period) => period.cells.some((cell) => cell.staffed === false))
  const takeaway = matrix.dayMax === null || !matrix.rows.every((period) => complete(period) && period.max !== null) ? null
    : t(kind === 'current' ? 'charts.longest_take_current' : 'charts.longest_take_plan', { count: matrix.dayMax, where })

  return (
    // Not a named region: the Key Results card already is the "Longest Single Line" region.
    <section className="card" data-testid="longest-line-table">
      <h2 lang="en" className="section-title">{headingText(t, 'simulation.longest_line')}</h2>
      {takeaway && <p className="cv-takeaway" data-testid="longest-take">{takeaway}</p>}
      <ul className="cv-legend">
        <li className="cv-legend-item"><span className="cv-swatch" aria-hidden="true" style={{ background: tint(1, 1), borderRadius: 3 }} />{t('charts.longest_legend_number')}</li>
        {showClosedKey && <li className="cv-legend-item"><span className="cv-swatch" aria-hidden="true" style={{ background: CLOSED_SWATCH, borderRadius: 3 }} />{closed}</li>}
        <li className="cv-legend-item">{t('charts.longest_legend_max')}</li>
      </ul>
      <div ref={wrap} className="table-scroll">
        <table ref={table} className="cv-matrix">
          <caption className="sr-only">{t('simulation.longest_line')}</caption>
          <thead>
            <tr>
              <th scope="col" className="cv-c-time">{t('common.time')}</th>
              {matrix.lanes.map((lane, index) => (
                <th key={lane} scope="col" title={lane} aria-label={narrow ? lane : undefined}>{narrow ? index + 1 : lane}</th>
              ))}
              <th scope="col" aria-label={narrow ? t('simulation.longest_line') : undefined}>{narrow ? '↑' : t('simulation.longest_line')}</th>
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((period, row) => (
              <tr key={period.time}>
                <th scope="row">{period.time}</th>
                {period.cells.map((cell, col) => {
                  const focus = { 'data-row': row, 'data-col': col, tabIndex: tabStop.row === row && tabStop.col === col ? 0 : -1,
                    onKeyDown: (event: KeyboardEvent<HTMLTableCellElement>) => onKeyDown(event, row, col),
                    onFocus: () => setActive({ row, col }), onMouseEnter: () => setActive({ row, col }), onClick: () => focusCell(row, col) }
                  const isActive = active?.row === row && active.col === col ? ' active' : ''
                  if (cell.staffed === false) {
                    return <td key={cell.lane} className={`cv-closed${isActive}`} {...focus}><span aria-hidden="true">—</span><span className="sr-only">{closed}</span></td>
                  }
                  if (cell.staffed === null) {
                    // Staffing unknown: no value and no hatching.
                    return <td key={cell.lane} className={isActive.trim() || undefined} {...focus}><span aria-hidden="true">—</span><span className="sr-only">{unavailable}</span></td>
                  }
                  return (
                    <td key={cell.lane} className={isActive.trim() || undefined} style={cell.value === null ? undefined : { background: tint(cell.value, matrix.dayMax) }} {...focus}>
                      {cell.value ?? unavailable}
                    </td>
                  )
                })}
                <td className={`cv-maxcol${active?.row === row && active.col === matrix.lanes.length ? ' active' : ''}`} data-row={row} data-col={matrix.lanes.length}
                  tabIndex={tabStop.row === row && tabStop.col === matrix.lanes.length ? 0 : -1}
                  onKeyDown={(event) => onKeyDown(event, row, matrix.lanes.length)} onFocus={() => setActive({ row, col: matrix.lanes.length })}
                  onMouseEnter={() => setActive({ row, col: matrix.lanes.length })} onClick={() => focusCell(row, matrix.lanes.length)}>
                  {(complete(period) ? period.max : null) ?? unavailable}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {narrow && matrix.lanes.length > 0 && (
        <p className="form-hint" data-testid="longest-columns">
          {t('charts.longest_legend_columns', { count: matrix.lanes.length, first: matrix.lanes[0], last: matrix.lanes[matrix.lanes.length - 1] })}
        </p>
      )}
      <div className="cv-readout" aria-hidden="true" data-testid="longest-readout">
        {readout.map((line, index) => <p key={index} className={index === 0 ? 'cv-readout-title' : undefined}>{line}</p>)}
      </div>
      <p className="sr-only" aria-live="polite">{readout.join(', ')}</p>
      <details className="cv-details">
        <summary>{t('simulation.check_details')}</summary>
        <div className="cv-chips">{chips.map((chip, index) => <span key={index} className={`cv-chip${index === 0 ? (kind === 'current' ? ' cv-chip-cur' : ' cv-chip-opt') : ''}`}>{chip}</span>)}</div>
        <p className="form-hint">{t('charts.longest_note')}</p>
      </details>
    </section>
  )
}
