import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import Plot from 'react-plotly.js'
import type { OptimizationOut, SimDesOut, SimMcOut } from '../../api/types'
import { RADAR_THETA } from '../../lib/radar'

const MARGIN = { l: 40, r: 40, t: 50, b: 40 }
const LINE_WIDTH = 2

function ChartFrame({ testId, children }: { testId: string; children: React.ReactNode }) {
  return (
    <div className="plotly-wrap" data-testid={testId}>
      {children}
    </div>
  )
}

export function UtilizationHeatmap({ rows }: { rows: SimDesOut[] }) {
  const { t } = useTranslation()
  const pivot = useMemo(() => {
    const data: Record<string, Record<string, number[]>> = {}
    for (const row of rows) {
      if (row.rho_sim === null || row.rho_sim === undefined) continue
      ;(data[String(row.c)] ??= {})[String(row.lambda)] ??= []
      data[String(row.c)][String(row.lambda)].push(row.rho_sim * 100)
    }
    const cs = Object.keys(data).sort((a, b) => Number(a) - Number(b))
    const lambdas = new Set<string>()
    for (const c of cs) {
      for (const l of Object.keys(data[c])) lambdas.add(l)
    }
    const xs = [...lambdas].sort((a, b) => Number(a) - Number(b))
    const z = cs.map((c) => xs.map((l) => {
      const vals = data[c][l]
      if (!vals) return null
      return vals.reduce((a, b) => a + b, 0) / vals.length
    }))
    return { z, xs, cs }
  }, [rows])
  return (
    <ChartFrame testId="chart-utilization-heatmap">
      <Plot
        data={[
          {
            type: 'heatmap',
            z: pivot.z,
            x: pivot.xs,
            y: pivot.cs,
            colorscale: 'RdYlGn_r',
            zmin: 0,
            zmax: 100,
            hovertemplate: 'λ=%{x}<br>c=%{y}<br>ρ=%{z:.1f}%<extra></extra>',
          },
        ]}
        layout={{
          autosize: true,
          title: t('simulation.heatmap.title'),
          xaxis: { title: t('simulation.heatmap.x'), automargin: true, tickangle: -45 },
          yaxis: { title: 'Servers c', automargin: true },
          height: 300,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function RhoLqLines({ rows }: { rows: SimDesOut[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-rho-lq-lines">
      <Plot
        data={[
          {
            type: 'scatter',
            mode: 'lines+markers',
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.rho_sim),
            name: 'ρ sim',
            line: { color: '#E8A838', width: LINE_WIDTH },
          },
          {
            type: 'scatter',
            mode: 'lines+markers',
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.Lq_sim),
            name: 'Lq sim',
            line: { color: '#2E86AB', width: LINE_WIDTH },
            yaxis: 'y2',
          },
        ]}
        layout={{
          autosize: true,
          title: t('simulation.rho_lq'),
          xaxis: { title: t('page1.caption'), automargin: true },
          yaxis: { title: 'ρ sim', color: '#E8A838', automargin: true },
          yaxis2: { title: 'Lq sim', color: '#2E86AB', overlaying: 'y', side: 'right', automargin: true },
          legend: { orientation: 'h', y: 1.12 },
          height: 350,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function MaxQueueBars({ rows }: { rows: SimDesOut[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-max-queue-bars">
      <Plot
        data={[
          {
            type: 'bar',
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.max_queue),
            marker_color: '#C0392B',
            name: 'Max Queue',
          },
        ]}
        layout={{
          autosize: true,
          title: t('simulation.max_queue'),
          xaxis: { title: t('page1.caption'), automargin: true },
          yaxis: { title: 'Max Queue', automargin: true },
          height: 350,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function LqHistogram({ rows }: { rows: SimDesOut[] }) {
  const { t } = useTranslation()
  const values = rows.map((r) => r.Lq_sim).filter((v): v is number => v !== null && v !== undefined)
  return (
    <ChartFrame testId="chart-lq-histogram">
      <Plot
        data={[
          {
            type: 'histogram',
            x: values,
            nbinsx: 20,
            marker_color: '#5DADE2',
            name: 'Lq sim',
          },
        ]}
        layout={{
          autosize: true,
          title: t('simulation.lq_hist'),
          xaxis: { title: 'Queue Length', automargin: true },
          yaxis: { title: 'Frequency', automargin: true },
          height: 300,
          margin: { l: 40, r: 40, t: 40, b: 40 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function RhoMeanP95Lines({ rows }: { rows: SimMcOut[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-rho-mean-p95-lines">
      <Plot
        data={[
          {
            type: 'scatter',
            mode: 'lines+markers',
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.rho_mean),
            name: 'ρ mean',
            line: { color: '#E8A838', width: LINE_WIDTH },
          },
          {
            type: 'scatter',
            mode: 'lines+markers',
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.rho_p95),
            name: 'ρ p95',
            line: { color: '#C0392B', width: LINE_WIDTH, dash: 'dash' },
          },
        ]}
        layout={{
          autosize: true,
          title: t('simulation.rho_p95'),
          xaxis: { title: t('page1.caption'), automargin: true },
          yaxis: { title: 'Utilization (ρ)', automargin: true },
          legend: { orientation: 'h', y: 1.12 },
          height: 350,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function FailureRateBars({ rows }: { rows: SimMcOut[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-failure-rate-bars">
      <Plot
        data={[
          {
            type: 'bar',
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.failure_rate),
            marker_color: '#C0392B',
            name: 'Failure Rate',
          },
        ]}
        layout={{
          autosize: true,
          title: t('simulation.failure_rate'),
          xaxis: { title: t('page1.caption'), automargin: true },
          yaxis: { title: 'Failure Rate', automargin: true },
          height: 350,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

function total(rows: OptimizationOut[], pick: (row: OptimizationOut) => number | null): number {
  return rows.reduce((acc, row) => acc + (pick(row) ?? 0), 0)
}

export function RadarChart({ current, optimized }: { current: number[]; optimized: number[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-radar">
      <Plot
        data={[
          {
            type: 'scatterpolar',
            r: current,
            theta: RADAR_THETA,
            fill: 'toself',
            name: t('compare.current'),
            line: { color: '#E74C3C' },
            fillcolor: 'rgba(231, 76, 60, 0.15)',
          },
          {
            type: 'scatterpolar',
            r: optimized,
            theta: RADAR_THETA,
            fill: 'toself',
            name: t('compare.optimized'),
            line: { color: '#27AE60' },
            fillcolor: 'rgba(39, 174, 96, 0.15)',
          },
        ]}
        layout={{
          autosize: true,
          polar: {
            radialaxis: { visible: true, range: [0, 100], tickfont: { size: 10 } },
          },
          title: t('compare.radar'),
          height: 400,
          legend: { orientation: 'h', yanchor: 'bottom', y: 1.08, xanchor: 'center', x: 0.5 },
          margin: { t: 60, b: 20 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function UtilizationCompareBars({ rows }: { rows: OptimizationOut[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-utilization-compare">
      <Plot
        data={[
          {
            type: 'bar',
            name: t('compare.current'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => (r.rho_current ?? 0) * 100),
            marker_color: '#E74C3C',
          },
          {
            type: 'bar',
            name: t('compare.optimized'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => (r.rho_optimal ?? 0) * 100),
            marker_color: '#27AE60',
          },
        ]}
        layout={{
          autosize: true,
          barmode: 'group',
          title: t('compare.utilization'),
          xaxis: { title: t('page1.caption'), automargin: true },
          yaxis: { title: 'Utilization (%)', automargin: true },
          height: 350,
          legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1 },
          margin: { t: 40, b: 20 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function ServerCompareBars({ rows }: { rows: OptimizationOut[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-server-compare">
      <Plot
        data={[
          {
            type: 'bar',
            name: t('compare.current'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.c_current),
            marker_color: '#E74C3C',
          },
          {
            type: 'bar',
            name: t('compare.optimized'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.c_optimal),
            marker_color: '#27AE60',
          },
        ]}
        layout={{
          autosize: true,
          barmode: 'group',
          title: t('compare.servers'),
          xaxis: { title: t('page1.caption'), automargin: true },
          yaxis: { title: 'Servers', automargin: true },
          height: 350,
          legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1 },
          margin: { t: 40, b: 20 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function WaitTimeLines({ rows }: { rows: OptimizationOut[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-wait-time-lines">
      <Plot
        data={[
          {
            type: 'scatter',
            name: t('compare.current'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => (r.Wq_current ?? 0) * 60),
            mode: 'lines+markers',
            line: { color: '#E74C3C', width: LINE_WIDTH },
            marker: { size: 4 },
          },
          {
            type: 'scatter',
            name: t('compare.optimized'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => (r.Wq_optimal ?? 0) * 60),
            mode: 'lines+markers',
            line: { color: '#27AE60', width: LINE_WIDTH },
            marker: { size: 4 },
          },
        ]}
        layout={{
          autosize: true,
          title: t('compare.waiting'),
          xaxis: { title: t('page1.caption'), automargin: true },
          yaxis: { title: 'Avg Wait (min)', automargin: true },
          height: 380,
          legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1 },
          margin: { t: 40, b: 20 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function CostWaterfall({ rows }: { rows: OptimizationOut[] }) {
  const { t } = useTranslation()
  const curServer = total(rows, (r) => (r.cost_per_server ?? 0) * r.c_current)
  const optServer = total(rows, (r) => (r.cost_per_server ?? 0) * r.c_optimal)
  const curWait = total(rows, (r) => r.waiting_cost_current)
  const optWait = total(rows, (r) => r.waiting_cost_optimal)
  const curAbandon = total(rows, (r) => r.abandonment_cost_current)
  const optAbandon = total(rows, (r) => r.abandonment_cost_optimal)
  const curTotal = total(rows, (r) => r.cost_current)
  const optTotal = total(rows, (r) => r.cost_optimal)
  return (
    <ChartFrame testId="chart-cost-waterfall">
      <Plot
        data={[
          {
            type: 'waterfall',
            name: 'Cost',
            orientation: 'v',
            measure: ['relative', 'relative', 'relative', 'relative', 'total'],
            x: ['Current Total', 'Server Delta', 'Wait Delta', 'Abandonment Delta', 'Optimized Total'],
            y: [curTotal, optServer - curServer, optWait - curWait, optAbandon - curAbandon, optTotal],
            connector: { line: { color: '#94A3B8', width: 1 } },
            decreasing: { marker: { color: '#27AE60' } },
            increasing: { marker: { color: '#E74C3C' } },
            totals: { marker: { color: '#2E86AB' } },
          },
        ]}
        layout={{
          autosize: true,
          title: t('compare.waterfall'),
          height: 400,
          margin: { t: 40, b: 20 },
          font: { size: 11 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function ScenarioCompareBars({
  scenarios,
}: {
  scenarios: Array<{ name: string; rows: OptimizationOut[] }>
}) {
  const { t } = useTranslation()
  const colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B']
  return (
    <ChartFrame testId="chart-scenario-compare">
      <Plot
        data={scenarios.map((sc, idx) => ({
          type: 'bar',
          name: sc.name,
          x: sc.rows.map((r) => r.time),
          y: sc.rows.map((r) => (r.Wq_optimal ?? 0) * 60),
          marker_color: colors[idx % colors.length],
        }))}
        layout={{
          autosize: true,
          barmode: 'group',
          title: t('compare.scenario'),
          xaxis: { title: t('page1.caption'), automargin: true },
          yaxis: { title: 'Avg Wait (min)', automargin: true },
          height: 400,
          legend_title: 'Scenario',
          margin: { t: 40, b: 20 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}
