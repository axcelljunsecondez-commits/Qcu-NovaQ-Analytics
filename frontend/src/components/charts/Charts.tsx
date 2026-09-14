import { useId, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import Plotly from 'plotly.js'
import createPlotlyComponent from 'react-plotly.js/factory'
import type { OptimizationOut, SimDesOut, SimMcOut } from '../../api/types'
import { completeFiniteTotal } from '../../lib/comparison'

const Plot = createPlotlyComponent(Plotly)
const MARGIN = { l: 40, r: 40, t: 25, b: 40 }
const LINE_WIDTH = 2

function ChartFrame({ testId, title, children }: { testId: string; title?: string; children: React.ReactNode }) {
  const titleId = useId()
  return (
    <div className="plotly-wrap" data-testid={testId} role="figure" aria-labelledby={title ? titleId : undefined}>
      {title && <h4 id={titleId}>{title}</h4>}
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
    <ChartFrame testId="chart-utilization-heatmap" title={t('simulation.heatmap.title')}>
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
          title: '',
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
    <ChartFrame testId="chart-rho-lq-lines" title={t('simulation.rho_lq')}>
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
          title: '',
          xaxis: { title: t('common.time'), automargin: true },
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
    <ChartFrame testId="chart-max-queue-bars" title={t('simulation.max_queue')}>
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
          title: '',
          xaxis: { title: t('common.time'), automargin: true },
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
    <ChartFrame testId="chart-lq-histogram" title={t('simulation.lq_hist')}>
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
          title: '',
          xaxis: { title: 'Queue Length', automargin: true },
          yaxis: { title: 'Frequency', automargin: true },
          height: 300,
          margin: { l: 40, r: 40, t: 20, b: 40 },
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
    <ChartFrame testId="chart-rho-mean-p95-lines" title={t('simulation.rho_p95')}>
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
          title: '',
          xaxis: { title: t('common.time'), automargin: true },
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
    <ChartFrame testId="chart-failure-rate-bars" title={t('simulation.failure_rate')}>
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
          title: '',
          xaxis: { title: t('common.time'), automargin: true },
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

export function UtilizationCompareBars({ rows }: { rows: OptimizationOut[] }) {
  const { t } = useTranslation()
  return (
    <ChartFrame testId="chart-utilization-compare" title={t('compare.utilization')}>
      <Plot
        data={[
          {
            type: 'bar',
            name: t('compare.current'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.rho_current === null ? null : r.rho_current * 100),
            marker_color: '#0B66C3',
          },
          {
            type: 'bar',
            name: t('compare.optimized'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.rho_optimal === null ? null : r.rho_optimal * 100),
            marker_color: '#6842B8',
          },
        ]}
        layout={{
          autosize: true,
          barmode: 'group',
          title: '',
          xaxis: { title: t('common.time'), automargin: true },
          yaxis: { title: 'Utilization (%)', automargin: true },
          height: 350,
          legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1 },
          margin: { t: 20, b: 20 },
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
    <ChartFrame testId="chart-server-compare" title={t('compare.servers')}>
      <Plot
        data={[
          {
            type: 'bar',
            name: t('compare.current'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.c_current),
            marker_color: '#0B66C3',
          },
          {
            type: 'bar',
            name: t('compare.optimized'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.c_optimal),
            marker_color: '#6842B8',
          },
        ]}
        layout={{
          autosize: true,
          barmode: 'group',
          title: '',
          xaxis: { title: t('common.time'), automargin: true },
          yaxis: { title: 'Servers', automargin: true },
          height: 350,
          legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1 },
          margin: { t: 20, b: 20 },
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
    <ChartFrame testId="chart-wait-time-lines" title={t('compare.waiting')}>
      <Plot
        data={[
          {
            type: 'scatter',
            name: t('compare.current'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.Wq_current === null ? null : r.Wq_current * 60),
            mode: 'lines+markers',
            line: { color: '#0B66C3', width: LINE_WIDTH },
            marker: { size: 4 },
          },
          {
            type: 'scatter',
            name: t('compare.optimized'),
            x: rows.map((r) => r.time),
            y: rows.map((r) => r.Wq_optimal === null ? null : r.Wq_optimal * 60),
            mode: 'lines+markers',
            line: { color: '#6842B8', width: LINE_WIDTH },
            marker: { size: 4 },
          },
        ]}
        layout={{
          autosize: true,
          title: '',
          xaxis: { title: t('common.time'), automargin: true },
          yaxis: { title: 'Avg Wait (min)', automargin: true },
          height: 380,
          legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1 },
          margin: { t: 20, b: 20 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}

export function CostWaterfall({ rows }: { rows: OptimizationOut[] }) {
  const { t } = useTranslation()
  const curServer = completeFiniteTotal(rows.map((r) => r.cost_per_server == null ? null : r.cost_per_server * r.c_current))
  const optServer = completeFiniteTotal(rows.map((r) => r.cost_per_server == null || r.c_optimal == null ? null : r.cost_per_server * r.c_optimal))
  const curWait = completeFiniteTotal(rows.map((r) => r.waiting_cost_current))
  const optWait = completeFiniteTotal(rows.map((r) => r.waiting_cost_optimal))
  const curAbandon = completeFiniteTotal(rows.map((r) => r.abandonment_cost_current))
  const optAbandon = completeFiniteTotal(rows.map((r) => r.abandonment_cost_optimal))
  const curTotal = completeFiniteTotal(rows.map((r) => r.cost_current))
  const optTotal = completeFiniteTotal(rows.map((r) => r.cost_optimal))
  return (
    <ChartFrame testId="chart-cost-waterfall" title={t('compare.waterfall')}>
      <Plot
        data={[
          {
            type: 'bar',
            name: t('compare.current'),
            x: ['Server', 'Wait', 'Abandonment', 'Total'],
            y: [curServer, curWait, curAbandon, curTotal],
            marker_color: '#0B66C3',
          },
          {
            type: 'bar',
            name: t('compare.optimized'),
            x: ['Server', 'Wait', 'Abandonment', 'Total'],
            y: [optServer, optWait, optAbandon, optTotal],
            marker_color: '#6842B8',
          },
        ]}
        layout={{
          autosize: true,
          barmode: 'group',
          title: '',
          height: 400,
          margin: { t: 20, b: 20 },
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
    <ChartFrame testId="chart-scenario-compare" title={t('compare.scenario')}>
      <Plot
        data={scenarios.map((sc, idx) => ({
          type: 'bar',
          name: sc.name,
          x: sc.rows.map((r) => r.time),
          y: sc.rows.map((r) => r.Wq_optimal === null ? null : r.Wq_optimal * 60),
          marker_color: colors[idx % colors.length],
        }))}
        layout={{
          autosize: true,
          barmode: 'group',
          title: '',
          xaxis: { title: t('common.time'), automargin: true },
          yaxis: { title: 'Avg Wait (min)', automargin: true },
          height: 400,
          legend_title: 'Scenario',
          margin: { t: 20, b: 20 },
        }}
        style={{ width: '100%' }}
        useResizeHandler={true}
      />
    </ChartFrame>
  )
}
