import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'

/**
 * One SVG row per period with marks on a shared axis that starts at 0 (spec 2026-10-29 §2.1, §5.2, §8.2).
 * The chart draws exactly what the caller passes: values, ranges (already clamped by the caller),
 * gaps and labels. It computes no statistic. Keyboard: Arrow keys, Home and End move the active row;
 * Enter or a click selects it. The active row's values are read out in a visible panel and a live region.
 */

export type MarkKind = 'est' | 'rec' | 'plan' | 'mc'

export interface ChartMark {
  kind: MarkKind
  value: number
}

export interface ChartRange {
  low: number
  high: number
  /** The shown lower end is 0 (display clamp, OD-1): a small marker is drawn at the axis start. */
  cut: boolean
}

export interface ChartRow {
  key: string
  label: string
  sublabel?: string
  marks: ChartMark[]
  range?: ChartRange | null
  /** Dotted line between two values on the row (for example Recorded and Estimated). */
  connect?: [number, number] | null
  /** Text at the right end of the row (for example the cashier and its value). */
  sideLabel?: string
  /** Shown when nothing is drawn on the row, so a missing value is a labelled gap. */
  gapLabel?: string
  highlight?: boolean
  /** Lines of the visible readout; the caller formats them exactly as the table alternative. */
  readout: string[]
  liveText: string
}

export interface RowChartProps {
  name: string
  rows: ChartRow[]
  /** Axis maximum in value units (greater than 0). */
  max: number
  ticks: number[]
  formatTick: (value: number) => string
  unit?: string
  reference?: { value: number; label: string } | null
  initialRow?: number
  onSelect?: (index: number) => void
  /** Pixels reserved at the right for side labels. */
  sideWidth?: number
  testId?: string
}

const ROW_HEIGHT = 46
const AXIS_HEIGHT = 30
const FALLBACK_WIDTH = 600
const PLOT_PADDING = 8
const MIN_AXIS_WIDTH = 180
const COMPACT_GAP = 12

function useWidth() {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(FALLBACK_WIDTH)
  useEffect(() => {
    const element = ref.current
    if (!element) return undefined
    const measure = () => setWidth(element.clientWidth > 0 ? element.clientWidth : FALLBACK_WIDTH)
    measure()
    if (typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return { ref, width: Math.max(240, width) }
}

function Mark({ mark, x, y }: { mark: ChartMark; x: number; y: number }) {
  if (mark.kind === 'rec') return <path className="cv-m-rec" d={`M${x} ${y - 7} L${x + 7} ${y} L${x} ${y + 7} L${x - 7} ${y}Z`} />
  if (mark.kind === 'est') return <circle className="cv-m-est" cx={x} cy={y} r={5.5} />
  if (mark.kind === 'plan') return <circle className="cv-m-plan" cx={x} cy={y} r={5} />
  return <circle className="cv-m-mc" cx={x} cy={y} r={4.5} />
}

export function RowChart({ name, rows, max, ticks, formatTick, unit, reference = null, initialRow = 0, onSelect, sideWidth, testId }: RowChartProps) {
  const { ref, width } = useWidth()
  const [active, setActive] = useState(-1)
  const narrow = width < 420
  // Measure uncapped text independently of either row layout. Measuring only the
  // currently drawn SVG labels would lose the widths after switching to wrapped HTML.
  const measureRef = useRef<SVGSVGElement>(null)
  const [textWidth, setTextWidth] = useState({ label: 0, side: 0 })
  useLayoutEffect(() => {
    const svg = measureRef.current
    if (!svg) return
    const measure = (value: string, strong = false) => {
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      text.setAttribute('class', strong ? 'cv-lbl-strong' : 'cv-lbl')
      text.textContent = value
      svg.appendChild(text)
      const length = typeof text.getComputedTextLength === 'function' ? text.getComputedTextLength() : 0
      text.remove()
      return length
    }
    let label = 0
    let side = 0
    for (const row of rows) {
      label = Math.max(label, measure(row.label, true), row.sublabel ? measure(row.sublabel) : 0)
      if (row.sideLabel) side = Math.max(side, measure(row.sideLabel))
    }
    setTextWidth((previous) => Math.abs(previous.label - label) < 0.5 && Math.abs(previous.side - side) < 0.5
      ? previous : { label, side })
  }, [rows, width])
  const labelWidth = Math.max(narrow ? 74 : 96, Math.ceil(textWidth.label) + 10)
  const rightWidth = Math.max((sideWidth ?? 18) - PLOT_PADDING, Math.ceil(textWidth.side) + 4)
  const compact = labelWidth + MIN_AXIS_WIDTH + 2 * PLOT_PADDING + rightWidth > width
  const hasSide = rows.some((row) => Boolean(row.sideLabel))
  const plotWidth = compact
    ? hasSide ? Math.max(MIN_AXIS_WIDTH + 2 * PLOT_PADDING, Math.floor((width - COMPACT_GAP) * 0.68)) : width
    : width - labelWidth - rightWidth
  const gridStyle = {
    gridTemplateColumns: compact
      ? hasSide ? `${plotWidth}px minmax(0, 1fr)` : 'minmax(0, 1fr)'
      : `${labelWidth}px ${plotWidth}px ${rightWidth}px`,
    columnGap: compact && hasSide ? COMPACT_GAP : 0,
  }
  const x0 = PLOT_PADDING
  const x1 = plotWidth - PLOT_PADDING
  const scale = max > 0 ? max : 1
  const x = (value: number) => x0 + (Math.min(Math.max(value, 0), scale) / scale) * (x1 - x0)
  const shownTicks = narrow && ticks.length > 5 ? ticks.filter((_, index) => index % 2 === 0 || index === ticks.length - 1) : ticks
  const current = active >= 0 && active < rows.length ? rows[active] : null

  const choose = (index: number, select = false) => {
    if (rows.length === 0) return
    const next = Math.min(Math.max(index, 0), rows.length - 1)
    setActive(next)
    if (select) onSelect?.(next)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const from = active < 0 ? initialRow : active
    const target = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? from + 1
      : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? from - 1
        : event.key === 'Home' ? 0
          : event.key === 'End' ? rows.length - 1
            : null
    if (target !== null) {
      event.preventDefault()
      choose(target)
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault()
      onSelect?.(active)
    }
  }

  return (
    <div className="cv-chart-wrap">
      <div ref={ref} className={`cv-chart${compact ? ' cv-chart-compact' : ''}`} role="group" aria-roledescription="chart" aria-label={name} tabIndex={0} data-testid={testId}
        data-layout={compact ? 'compact' : 'wide'}
        onKeyDown={onKeyDown} onFocus={() => { if (active < 0) choose(initialRow) }}>
        <svg ref={measureRef} className="cv-chart-measure" aria-hidden="true" focusable="false" />
        {reference && <div className="cv-row-axis-grid" style={gridStyle} aria-hidden="true">
          <svg style={{ gridColumn: compact ? 1 : 2 }} viewBox={`0 0 ${plotWidth} ${AXIS_HEIGHT}`} width={plotWidth} height={AXIS_HEIGHT} focusable="false">
            <g data-testid="row-chart-reference">
              <line className="cv-l-cap" x1={x(reference.value)} x2={x(reference.value)} y1={18} y2={AXIS_HEIGHT} />
              <text className="cv-lbl" x={x(reference.value)} y={12} textAnchor="middle">{reference.label}</text>
            </g>
          </svg>
        </div>}
        {rows.map((row, index) => {
          const y = ROW_HEIGHT / 2
          const drawn = row.marks.length > 0 || Boolean(row.range)
          return (
            <div key={row.key} style={gridStyle} className={`cv-row cv-row-grid${row.highlight ? ' hl' : ''}${index === active ? ' active' : ''}`} data-testid="row-chart-row" aria-hidden="true"
              onMouseEnter={() => choose(index)} onClick={() => { ref.current?.focus({ preventScroll: true }); choose(index, true) }}>
              <div className="cv-row-label">
                <strong className="cv-row-title">{row.label}</strong>
                {row.sublabel && <span className="cv-row-sublabel">{row.sublabel}</span>}
              </div>
              <div className="cv-row-svg-cell">
                <svg className="cv-row-plot" viewBox={`0 0 ${plotWidth} ${ROW_HEIGHT}`} width={plotWidth} height={ROW_HEIGHT} focusable="false">
                  <rect className="cv-row-bg" x={0} y={1} width={plotWidth} height={ROW_HEIGHT - 2} rx={4} />
                  {shownTicks.map((tick) => <line key={tick} className={tick === 0 ? 'cv-axis-l' : 'cv-grid-l'} x1={x(tick)} x2={x(tick)} y1={0} y2={ROW_HEIGHT} />)}
                  {reference && <line className="cv-l-cap" x1={x(reference.value)} x2={x(reference.value)} y1={0} y2={ROW_HEIGHT} />}
                  {row.connect && <line className="cv-l-gap" x1={x(row.connect[0])} x2={x(row.connect[1])} y1={y} y2={y} />}
                  {row.range && (
                    <>
                      <line className="cv-l-ci" x1={x(row.range.low)} x2={x(row.range.high)} y1={y + 0.01} y2={y} />
                      {row.range.cut && <path className="cv-m-clip" data-testid="row-chart-cut" d={`M${x0 - 1} ${y} L${x0 + 6} ${y - 5} L${x0 + 6} ${y + 5}Z`} />}
                    </>
                  )}
                  {row.marks.map((mark, markIndex) => <Mark key={`${mark.kind}-${markIndex}`} mark={mark} x={x(mark.value)} y={y} />)}
                </svg>
                {!drawn && row.gapLabel && <span className="cv-row-gap">{row.gapLabel}</span>}
              </div>
              {hasSide && <span className="cv-row-side">{row.sideLabel}</span>}
            </div>
          )
        })}
        <div className="cv-row-axis-grid" style={gridStyle} aria-hidden="true">
          <svg className="cv-ax" style={{ gridColumn: compact ? 1 : 2 }} viewBox={`0 0 ${plotWidth} ${AXIS_HEIGHT}`} width={plotWidth} height={AXIS_HEIGHT} focusable="false">
            {shownTicks.map((tick) => <text key={tick} x={x(tick)} y={16} textAnchor="middle">{formatTick(tick)}</text>)}
            {unit && <text x={x1} y={AXIS_HEIGHT - 2} textAnchor="end">{unit}</text>}
          </svg>
        </div>
      </div>
      <div className="cv-readout" aria-hidden="true" data-testid="row-chart-readout">
        {current && current.readout.map((line, index) => <p key={index} className={index === 0 ? 'cv-readout-title' : undefined}>{line}</p>)}
      </div>
      <p className="sr-only" aria-live="polite">{current?.liveText ?? ''}</p>
    </div>
  )
}
