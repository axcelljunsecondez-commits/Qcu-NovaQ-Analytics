import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import Plot from 'react-plotly.js'
import type { SimDesOut, SimMcOut } from '../../api/types'

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
          title: t('simulation.heatmap.title'),
          xaxis: { title: t('simulation.heatmap.x') },
          yaxis: { title: 'Servers c' },
          height: 300,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
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
          title: t('simulation.rho_lq'),
          xaxis: { title: t('page1.caption') },
          yaxis: { title: 'ρ sim', color: '#E8A838' },
          yaxis2: { title: 'Lq sim', color: '#2E86AB', overlaying: 'y', side: 'right' },
          legend: { orientation: 'h', y: 1.12 },
          height: 350,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
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
          title: t('simulation.max_queue'),
          xaxis: { title: t('page1.caption') },
          yaxis: { title: 'Max Queue' },
          height: 350,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
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
          title: t('simulation.lq_hist'),
          xaxis: { title: 'Queue Length' },
          yaxis: { title: 'Frequency' },
          height: 300,
          margin: { l: 40, r: 40, t: 40, b: 40 },
        }}
        style={{ width: '100%' }}
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
          title: t('simulation.rho_p95'),
          xaxis: { title: t('page1.caption') },
          yaxis: { title: 'Utilization (ρ)' },
          legend: { orientation: 'h', y: 1.12 },
          height: 350,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
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
          title: t('simulation.failure_rate'),
          xaxis: { title: t('page1.caption') },
          yaxis: { title: 'Failure Rate' },
          height: 350,
          margin: MARGIN,
        }}
        style={{ width: '100%' }}
      />
    </ChartFrame>
  )
}
