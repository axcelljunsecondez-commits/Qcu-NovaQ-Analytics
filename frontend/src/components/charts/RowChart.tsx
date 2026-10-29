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

const ROW_HEIGHT = 34
const AXIS_HEIGHT = 30
const FALLBACK_WIDTH = 600
/** Room between the end of a row label and the axis start (marks at 0 reach 7 px left of it). */
const LABEL_GAP = 14
/** The label column never takes more than this share of the chart, so the plot keeps its room. */
const LABEL_MAX_SHARE = 0.62

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
  // Labels are drawn as given (a per-date label such as "2000-01-03 05:00-06:00 UTC" is about 165 px), so
  // the label column grows to the longest rendered label instead of letting it run under the marks.
  const svgRef = useRef<SVGSVGElement>(null)
  const [labelText, setLabelText] = useState(0)
  useLayoutEffect(() => {
    const labels = svgRef.current?.querySelectorAll<SVGTextContentElement>('[data-row-label]') ?? []
    let longest = 0
    for (const label of labels) {
      if (typeof label.getComputedTextLength === 'function') longest = Math.max(longest, label.getComputedTextLength())
    }
    setLabelText((previous) => (Math.abs(previous - longest) < 0.5 ? previous : longest))
  }, [rows, width])
  const labelWidth = Math.max(narrow ? 82 : 104, Math.min(Math.ceil(labelText) + 4 + LABEL_GAP, Math.floor(width * LABEL_MAX_SHARE)))
  const right = sideWidth ?? 18
  const top = reference ? 22 : 8
  const height = top + rows.length * ROW_HEIGHT + AXIS_HEIGHT
  const x0 = labelWidth
  const x1 = Math.max(x0 + 40, width - right)
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
      <div ref={ref} className="cv-chart" role="group" aria-roledescription="chart" aria-label={name} tabIndex={0} data-testid={testId}
        onKeyDown={onKeyDown} onFocus={() => { if (active < 0) choose(initialRow) }}>
        <svg ref={svgRef} viewBox={`0 0 ${width} ${height}`} width={width} height={height} aria-hidden="true" focusable="false">
          <g className="cv-ax">
            {shownTicks.map((tick) => (
              <g key={tick}>
                <line className={tick === 0 ? 'cv-axis-l' : 'cv-grid-l'} x1={x(tick)} x2={x(tick)} y1={top} y2={height - AXIS_HEIGHT} />
                <text x={x(tick)} y={height - AXIS_HEIGHT + 16} textAnchor="middle">{formatTick(tick)}</text>
              </g>
            ))}
            {unit && <text x={x1} y={height - 2} textAnchor="end">{unit}</text>}
          </g>
          {reference && (
            <g data-testid="row-chart-reference">
              <line className="cv-l-cap" x1={x(reference.value)} x2={x(reference.value)} y1={top - 10} y2={height - AXIS_HEIGHT} />
              <text className="cv-lbl" x={x(reference.value)} y={top - 12} textAnchor="middle">{reference.label}</text>
            </g>
          )}
          {rows.map((row, index) => {
            const y = top + index * ROW_HEIGHT + ROW_HEIGHT / 2
            const drawn = row.marks.length > 0 || Boolean(row.range)
            return (
              <g key={row.key} className={`cv-row${row.highlight ? ' hl' : ''}${index === active ? ' active' : ''}`} data-testid="row-chart-row"
                onMouseEnter={() => choose(index)} onClick={() => { choose(index, true); ref.current?.focus({ preventScroll: true }) }}>
                <rect className="cv-row-bg" x={0} y={y - ROW_HEIGHT / 2 + 1} width={width} height={ROW_HEIGHT - 2} rx={4} />
                <text className="cv-lbl-strong" data-row-label x={4} y={row.sublabel ? y - 2 : y + 4}>{row.label}</text>
                {row.sublabel && <text className="cv-lbl" data-row-label x={4} y={y + 12}>{row.sublabel}</text>}
                {row.connect && <line className="cv-l-gap" x1={x(row.connect[0])} x2={x(row.connect[1])} y1={y} y2={y} />}
                {row.range && (
                  <>
                    <line className="cv-l-ci" x1={x(row.range.low)} x2={x(row.range.high)} y1={y + 0.01} y2={y} />
                    {row.range.cut && <path className="cv-m-clip" data-testid="row-chart-cut" d={`M${x0 - 1} ${y} L${x0 + 6} ${y - 5} L${x0 + 6} ${y + 5}Z`} />}
                  </>
                )}
                {row.marks.map((mark, markIndex) => <Mark key={`${mark.kind}-${markIndex}`} mark={mark} x={x(mark.value)} y={y} />)}
                {!drawn && row.gapLabel && <text className="cv-lbl" x={x0 + 6} y={y + 4}>{row.gapLabel}</text>}
                {row.sideLabel && <text className="cv-lbl" x={x1 + 8} y={y + 4}>{row.sideLabel}</text>}
              </g>
            )
          })}
        </svg>
      </div>
      <div className="cv-readout" aria-hidden="true" data-testid="row-chart-readout">
        {current && current.readout.map((line, index) => <p key={index} className={index === 0 ? 'cv-readout-title' : undefined}>{line}</p>)}
      </div>
      <p className="sr-only" aria-live="polite">{current?.liveText ?? ''}</p>
    </div>
  )
}
