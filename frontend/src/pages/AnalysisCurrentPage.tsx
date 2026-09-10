/**
 * AnalysisCurrentPage — Shows current queue performance matching reference design.
 * Topbar, 4-up KPI cards, two-column charts (bar + donut), alert note, table.
 */
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { getAnalysisCurrent, listAnalysisDatasets } from '../api/analyses'
import { ApiState } from '../components/ui/ApiState'
import { NovaQInsights, generateOptimizationInsights } from '../components/insights/NovaQInsights'
import { fmtPct } from '../lib/format'

export function AnalysisCurrentPage() {
  const { t } = useTranslation()
  const id = Number(useParams().analysisId)
  const datasets = useQuery({ queryKey: ['datasets', id], queryFn: () => listAnalysisDatasets(id) })
  const datasetId = datasets.data?.datasets[0]?.id
  const query = useQuery({ queryKey: ['current', id, datasetId], queryFn: () => getAnalysisCurrent(id), enabled: Boolean(datasetId), retry: false })

  if (datasets.isLoading || query.isLoading) return <ApiState.Loading />
  if (query.isError || !query.data) {
    return (
      <div>
        <div className="topbar">
          <div>
            <div className="topbar-eyebrow">Analysis · Observed Baseline</div>
            <h1 className="page-title">{t('nav.current')}</h1>
            <p className="page-caption">{t('analyses.current_basis')}</p>
          </div>
        </div>
        <ApiState.Empty message={t('analyses.no_dataset')} />
        <Link className="button-link" to="../setup">{t('analyses.go_setup')}</Link>
      </div>
    )
  }

  const { selected_model, rows, kpis, explanations } = query.data
  const avgRho = typeof kpis?.avg_rho === 'number' ? kpis.avg_rho : null
  const avgWq = typeof kpis?.avg_wq === 'number' ? kpis.avg_wq : null

  const insights = generateOptimizationInsights(
    0, 0,
    avgWq !== null ? avgWq * 60 : null,
    null,
    avgRho,
    t,
  )

  // Compute arrival data for bar chart (group by time, count arrivals)
  const arrivalsByTime: Record<string, number> = {}
  rows.forEach((row) => {
    const time = String(row.time || '')
    const lambda = typeof row.lambda === 'number' ? row.lambda : Number(row.lambda) || 0
    arrivalsByTime[time] = (arrivalsByTime[time] || 0) + lambda
  })
  const timeLabels = Object.keys(arrivalsByTime)
  const arrivalValues = Object.values(arrivalsByTime)
  const maxArrival = Math.max(...arrivalValues, 1)

  // Model distribution for donut
  const modelCounts: Record<string, number> = {}
  rows.forEach((row) => {
    const model = String(row.model || 'Unknown')
    modelCounts[model] = (modelCounts[model] || 0) + 1
  })
  const modelEntries = Object.entries(modelCounts).sort((a, b) => b[1] - a[1])
  const totalRows = rows.length || 1

  return (
    <div>
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">Analysis · Observed Baseline</div>
          <h1 className="page-title">{t('nav.current')}</h1>
          <p className="page-caption">What is happening now, based on the uploaded observations. No optimization has been applied.</p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="kpi-row">
        <div className="card kpi-card">
          <div className="kpi-label">{t('analyses.avg_wq')}</div>
          <div className="kpi-value" style={{ color: 'var(--info)' }}>
            {avgWq !== null ? `${(avgWq * 60).toFixed(1)} min` : '—'}
          </div>
          <div className="kpi-hint" style={{ color: 'var(--success)' }}>Observed baseline</div>
        </div>
        <div className="card kpi-card">
          <div className="kpi-label">Peak Hour</div>
          <div className="kpi-value" style={{ fontSize: '18px' }}>
            {timeLabels.length > 0 ? timeLabels[timeLabels.length - 1] : '—'}
          </div>
          <div className="kpi-hint">Most customers</div>
        </div>
        <div className="card kpi-card">
          <div className="kpi-label">{t('analyses.avg_rho')}</div>
          <div className="kpi-value" style={{ color: 'var(--info)' }}>
            {avgRho !== null ? fmtPct(avgRho) : '—'}
          </div>
          <div className="kpi-hint" style={{ color: 'var(--warning)' }}>High during peak periods</div>
        </div>
        <div className="card kpi-card">
          <div className="kpi-label">Estimated Lost Customers</div>
          <div className="kpi-value" style={{ color: 'var(--danger)' }}>
            {rows.filter((r) => String(r.status || '').includes('CRITICAL')).length}
          </div>
          <div className="kpi-hint">Needs operational attention</div>
        </div>
      </div>

      {/* Two-column: Bar Chart + Donut */}
      <div className="grid g2" style={{ marginTop: '12px' }}>
        {/* Bar Chart — Arrivals by Time */}
        <div className="card" style={{ padding: '18px' }}>
          <h3 className="section-title">Customer Arrivals by Time</h3>
          <div style={{
            height: '210px',
            border: '1px solid var(--border)',
            borderRadius: '9px',
            padding: '14px',
            background: 'linear-gradient(#fff, #fbfdff)',
          }}>
            <div style={{
              height: '150px',
              display: 'flex',
              alignItems: 'end',
              gap: '8px',
              padding: '10px 8px 0',
              borderBottom: '1px solid #dfe8f1',
            }}>
              {arrivalValues.slice(0, 13).map((val, i) => (
                <span
                  key={i}
                  style={{
                    flex: 1,
                    background: 'linear-gradient(180deg, #54adff, #1887f5)',
                    borderRadius: '4px 4px 0 0',
                    minHeight: '8px',
                    height: `${(val / maxArrival) * 100}%`,
                  }}
                />
              ))}
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              color: '#8a9bad',
              fontSize: '9px',
              marginTop: '7px',
            }}>
              {timeLabels.slice(0, 13).filter((_, i) => i % 2 === 0).map((label, i) => (
                <span key={i}>{label}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Donut — Model Distribution */}
        <div className="card" style={{ padding: '18px' }}>
          <h3 className="section-title">Queue Model Used</h3>
          <div style={{
            width: '138px',
            height: '138px',
            borderRadius: '50%',
            background: `conic-gradient(var(--accent) 0 ${(modelEntries[0]?.[1] || 1) / totalRows * 100}%, var(--success) ${(modelEntries[0]?.[1] || 1) / totalRows * 100}% ${((modelEntries[0]?.[1] || 0) + (modelEntries[1]?.[1] || 0)) / totalRows * 100}%, var(--warning) ${((modelEntries[0]?.[1] || 0) + (modelEntries[1]?.[1] || 0)) / totalRows * 100}% 100%)`,
            margin: '8px auto',
            position: 'relative',
          }}>
            <div style={{
              position: 'absolute',
              inset: '27px',
              borderRadius: '50%',
              background: '#fff',
              display: 'grid',
              placeItems: 'center',
              textAlign: 'center',
              fontSize: '10px',
              fontWeight: 800,
              color: '#3d5875',
            }}>
              {selected_model || '—'}
            </div>
          </div>
          {/* Model legend */}
          <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {modelEntries.map(([model, count]) => (
              <div key={model} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent)', flexShrink: 0 }} />
                <span style={{ color: 'var(--text-secondary)' }}>{model}</span>
                <span style={{ fontWeight: 700, marginLeft: 'auto' }}>{Math.round(count / totalRows * 100)}%</span>
              </div>
            ))}
          </div>
          <div className="info" style={{ marginTop: '12px' }}>
            <strong>General service-time behavior detected.</strong> NovaQ can use the observed service-time variability instead of assuming a purely exponential distribution.
          </div>
        </div>
      </div>

      {/* Alert Note */}
      <div className="note" style={{ marginTop: '12px' }}>
        <strong>Queue pressure is concentrated in specific periods.</strong> The next step should propose staffing changes while keeping this baseline unchanged for comparison.
      </div>

      {/* NovaQ Insights */}
      {insights.length > 0 && <NovaQInsights insights={insights} />}

      {/* Model Explanation */}
      {explanations.length > 0 && (
        <div className="card" style={{ marginTop: '12px' }}>
          <h3 className="section-title">{t('analyses.model_explanation')}</h3>
          {explanations.map((exp, i) => (
            <div key={i} className="explanation-block">
              <h3 style={{ fontSize: '13px', fontWeight: 800 }}>{exp.selected_model}</h3>
              <p className="explanation-reason">{exp.selection_reason}</p>
              {exp.operational_facts.length > 0 && (
                <div className="explanation-section">
                  <strong style={{ fontSize: '11px' }}>{t('analyses.operational_facts')}</strong>
                  <ul>{exp.operational_facts.map((f, j) => <li key={j} style={{ fontSize: '11px' }}>{f}</li>)}</ul>
                </div>
              )}
              {exp.measured_characteristics.length > 0 && (
                <div className="explanation-section">
                  <strong style={{ fontSize: '11px' }}>{t('analyses.measured_characteristics')}</strong>
                  <ul>{exp.measured_characteristics.map((c, j) => <li key={j} style={{ fontSize: '11px' }}>{c}</li>)}</ul>
                </div>
              )}
              {exp.model_assumptions.length > 0 && (
                <div className="explanation-section">
                  <strong style={{ fontSize: '11px' }}>{t('analyses.model_assumptions')}</strong>
                  <ul>{exp.model_assumptions.map((a, j) => <li key={j} style={{ fontSize: '11px' }}>{a}</li>)}</ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Detailed Results Table */}
      <div className="card" style={{ marginTop: '12px' }}>
        <h3 className="section-title">{t('analyses.detailed_results')}</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('common.time')}</th>
                <th>λ</th>
                <th>μ</th>
                <th>c</th>
                <th>{t('analysis.model')}</th>
                <th>ρ</th>
                <th>Wq ({t('analyses.minutes')})</th>
                <th>{t('analyses.status')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const rho = typeof row.rho === 'number' ? row.rho : null
                const wq = typeof row.Wq === 'number' ? row.Wq : null
                const status = String(row.status || '')
                const isCritical = status.includes('CRITICAL') || status.includes('Unstable')
                return (
                  <tr key={String(row.time ?? index)} className={isCritical ? 'row-warning' : undefined}>
                    <td>{String(row.time)}</td>
                    <td>{String(row.lambda)}</td>
                    <td>{String(row.mu)}</td>
                    <td>{String(row.c)}</td>
                    <td>{String(row.model)}</td>
                    <td>{rho !== null ? fmtPct(rho) : '—'}</td>
                    <td>{wq !== null ? (wq * 60).toFixed(2) : '—'}</td>
                    <td>
                      <span className={`status-badge ${isCritical ? 'status-warning' : 'status-ok'}`}>
                        {status}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Navigation */}
      <div className="btnrow" style={{ justifyContent: 'flex-start' }}>
        <Link to="../setup" className="btn-ghost" style={{ textDecoration: 'none' }}>
          ← {t('setup.back')}
        </Link>
        <Link to="../optimize" className="button-link">
          Optimize Staffing →
        </Link>
      </div>
    </div>
  )
}
