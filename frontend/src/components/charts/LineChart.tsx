import { useEffect, useRef, useState, type KeyboardEvent, type MutableRefObject } from 'react'

/**
 * Hand-built SVG line chart, one point per period (HTML5 redesign Phase C, owner decisions OD-C1..C6).
 * Like RowChart it draws exactly what the caller passes and computes no statistic: the y axis starts
 * at 0 at the caller's `max`, periods are evenly spaced, and a null value breaks the line (no zero-fill,
 * no interpolation, no node). Keyboard: Arrow keys, Home and End move the active period; the readout
 * lines and the live text come from the caller, formatted as in the table alternative.
 *
 * Reveal (MASTER §7, 2026-11-25): only the data layer (traces and nodes) is revealed left to right with a
 * clip-path over 1.8 s, and only when `revealKey` changes to a key that was not revealed yet. Hover,
 * focus and the arrow keys never change the key. Under reduced motion the marks are shown at once.
 */

export type LineKind = 'rec' | 'est' | 'arr'

export interface LineSeries {
  kind: LineKind
  /** One value per period, in the caller's display unit; null is a gap. */
  values: (number | null)[]
}

export interface LineChartProps {
  name: string
  periods: string[]
  series: LineSeries[]
  /** Axis maximum in value units (greater than 0). */
  max: number
  ticks: number[]
  formatTick: (value: number) => string
  unit?: string
  /** Lines of the visible readout for period `index`. */
  readout: (index: number) => string[]
  liveText: (index: number) => string
  /** Takeaway period: drawn with a larger node and a ring. */
  highlight?: number | null
  initialIndex?: number
  /** A new key replays the reveal; see `revealMemory`. */
  revealKey: string
  /** Last revealed key, owned by the caller so a remount with the same key does not replay the reveal. */
  revealMemory?: MutableRefObject<string | null>
  testId?: string
}

const HEIGHT = 220
const TOP = 26
const BOTTOM = 30
const LEFT = 46
const RIGHT = 14
const FALLBACK_WIDTH = 600
const LABEL_CHAR_PX = 6.2
export const REVEAL_MS = 1800
export const REVEAL_DELAY_MS = 120

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

/** Runs of consecutive non-null points; each run becomes one path, so a null is a visible break. */
function runs(values: (number | null)[]): number[][] {
  const out: number[][] = []
  let current: number[] = []
  values.forEach((value, index) => {
    if (value === null || !Number.isFinite(value)) {
      if (current.length > 0) out.push(current)
      current = []
    } else current.push(index)
  })
  if (current.length > 0) out.push(current)
  return out
}

function Node({ kind, x, y, big, active }: { kind: LineKind; x: number; y: number; big: boolean; active: boolean }) {
  const className = `cv-node cv-node-${kind}${big ? ' is-highlight' : ''}${active ? ' is-active' : ''}`
  if (kind === 'est') {
    const r = big ? 6 : 4.5
    return <path className={className} d={`M${x} ${y - r} L${x + r} ${y} L${x} ${y + r} L${x - r} ${y}Z`} />
  }
  return <circle className={className} cx={x} cy={y} r={big ? 5.5 : 3.8} />
}

export function LineChart({
  name, periods, series, max, ticks, formatTick, unit, readout, liveText, highlight = null, initialIndex = 0, revealKey, revealMemory, testId,
}: LineChartProps) {
  const { ref, width } = useWidth()
  const layerRef = useRef<SVGGElement>(null)
  const ownMemory = useRef<string | null>(null)
  const memory = revealMemory ?? ownMemory
  const [active, setActive] = useState(-1)
  const count = periods.length
  const plotWidth = width - LEFT - RIGHT
  const plotHeight = HEIGHT - TOP - BOTTOM
  const scale = max > 0 ? max : 1
  const x = (index: number) => LEFT + (count <= 1 ? plotWidth / 2 : (index * plotWidth) / (count - 1))
  const y = (value: number) => TOP + plotHeight - (Math.min(Math.max(value, 0), scale) / scale) * plotHeight
  const slot = count <= 1 ? plotWidth : plotWidth / (count - 1)
  const longest = periods.reduce((longestLabel, label) => Math.max(longestLabel, label.length), 1)
  // The first and last labels are anchored inward, so neighbours need 1.5 label widths between them.
  const labelEvery = Math.max(1, Math.ceil((1.5 * (longest * LABEL_CHAR_PX + 8)) / slot))

  useEffect(() => {
    if (memory.current === revealKey) return undefined
    const prior = memory.current
    memory.current = revealKey
    const layer = layerRef.current
    if (!layer || typeof layer.animate !== 'function') return undefined
    const motion = typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-reduced-motion: reduce)') : null
    if (motion?.matches) return undefined
    const animation = layer.animate(
      [{ clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0)' }],
      { duration: REVEAL_MS, delay: REVEAL_DELAY_MS, easing: 'ease-in-out', fill: 'backwards' },
    )
    const onMotionChange = (event: MediaQueryListEvent) => { if (event.matches) animation.cancel() }
    motion?.addEventListener?.('change', onMotionChange)
    return () => {
      motion?.removeEventListener?.('change', onMotionChange)
      // An interrupted reveal (unmount before it finished) may replay; a finished one never does.
      if (animation.playState !== 'finished' && memory.current === revealKey) memory.current = prior
      animation.cancel()
    }
  }, [revealKey, memory])

  const choose = (index: number) => {
    if (count === 0) return
    setActive(Math.min(Math.max(index, 0), count - 1))
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const from = active < 0 ? initialIndex : active
    const target = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? from + 1
      : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? from - 1
        : event.key === 'Home' ? 0
          : event.key === 'End' ? count - 1
            : null
    if (target !== null) {
      event.preventDefault()
      choose(target)
    }
  }
  const current = active >= 0 && active < count ? active : null

  return (
    <div className="cv-chart-wrap">
      <div ref={ref} className="cv-chart cv-line-chart" role="group" aria-roledescription="chart" aria-label={name} tabIndex={0} data-testid={testId}
        onKeyDown={onKeyDown} onFocus={() => { if (active < 0) choose(initialIndex) }}>
        <svg viewBox={`0 0 ${width} ${HEIGHT}`} width={width} height={HEIGHT} aria-hidden="true" focusable="false">
          <g className="cv-ax">
            {ticks.map((tick) => (
              <g key={tick}>
                <line className={tick === 0 ? 'cv-axis-l' : 'cv-line-grid'} x1={LEFT} x2={LEFT + plotWidth} y1={y(tick)} y2={y(tick)} />
                <text className="numeric-value" x={LEFT - 6} y={y(tick) + 4} textAnchor="end">{formatTick(tick)}</text>
              </g>
            ))}
            {unit && <text x={LEFT - 6} y={TOP - 14} textAnchor="end">{unit}</text>}
            {/* Thinned period labels only (the readout names the active period), so labels never overlap;
                the first and last are anchored inside the plot. */}
            {periods.map((label, index) => (index % labelEvery === 0
              ? <text key={`${index}-${label}`} className={index === current ? 'cv-lbl-strong' : undefined} x={x(index)} y={HEIGHT - 10}
                textAnchor={count > 1 && index === 0 ? 'start' : count > 1 && index === count - 1 ? 'end' : 'middle'}>{label}</text>
              : null))}
          </g>
          {current !== null && <line className="cv-line-guide" data-testid="line-chart-guide" x1={x(current)} x2={x(current)} y1={TOP} y2={TOP + plotHeight} />}
          <g ref={layerRef} className="cv-curve-layer" data-testid="line-chart-curves">
            {series.map((line) => runs(line.values).map((run) => (
              <path key={`${line.kind}-${run[0]}`} className={`cv-trace cv-trace-${line.kind}`} data-testid={`line-trace-${line.kind}`}
                d={run.map((index, position) => `${position === 0 ? 'M' : 'L'}${x(index)} ${y(line.values[index] as number)}`).join(' ')} />
            )))}
            {series.map((line) => line.values.map((value, index) => (value === null || !Number.isFinite(value) ? null
              : <Node key={`${line.kind}-${index}`} kind={line.kind} x={x(index)} y={y(value)} big={index === highlight} active={index === current} />)))}
          </g>
          {periods.map((label, index) => (
            <rect key={`${index}-${label}`} className="cv-line-hit" data-testid="line-chart-hit" x={x(index) - slot / 2} y={TOP} width={slot} height={plotHeight}
              onMouseEnter={() => choose(index)} onClick={() => { ref.current?.focus({ preventScroll: true }); choose(index) }} />
          ))}
        </svg>
      </div>
      <div className="cv-readout" aria-hidden="true" data-testid="line-chart-readout">
        {current !== null && readout(current).map((line, index) => <p key={index} className={index === 0 ? 'cv-readout-title' : undefined}>{line}</p>)}
      </div>
      <p className="sr-only" aria-live="polite">{current !== null ? liveText(current) : ''}</p>
    </div>
  )
}
