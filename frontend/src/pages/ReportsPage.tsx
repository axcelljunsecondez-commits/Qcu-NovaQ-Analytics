/**
 * ReportsPage - Shows report preview with 10 sections and download options.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { listDatasets } from '../api/datasets'
import { listScenarios } from '../api/scenarios'
import {
  downloadReport,
  fetchReport,
  reportFileExtension,
  type ReportFormat,
  type ReportKind,
} from '../api/reports'
import { ApiState } from '../components/ui/ApiState'
import { getWorkflow } from '../api/workflow'

interface ReportSection {
  id: string
  titleKey: string
  descriptionKey: string
}

const REPORT_SECTIONS: ReportSection[] = [
  { id: 'executive', titleKey: 'reports.section_executive', descriptionKey: 'reports.section_executive_desc' },
  { id: 'operation', titleKey: 'reports.section_operation', descriptionKey: 'reports.section_operation_desc' },
  { id: 'current', titleKey: 'reports.section_current', descriptionKey: 'reports.section_current_desc' },
  { id: 'model', titleKey: 'reports.section_model', descriptionKey: 'reports.section_model_desc' },
  { id: 'optimization', titleKey: 'reports.section_optimization', descriptionKey: 'reports.section_optimization_desc' },
  { id: 'simulation', titleKey: 'reports.section_simulation', descriptionKey: 'reports.section_simulation_desc' },
  { id: 'comparison', titleKey: 'reports.section_comparison', descriptionKey: 'reports.section_comparison_desc' },
  { id: 'roi', titleKey: 'reports.section_roi', descriptionKey: 'reports.section_roi_desc' },
  { id: 'recommendations', titleKey: 'reports.section_recommendations', descriptionKey: 'reports.section_recommendations_desc' },
  { id: 'appendix', titleKey: 'reports.section_appendix', descriptionKey: 'reports.section_appendix_desc' },
]

export function ReportsPage() {
  const { t } = useTranslation()
  const analysisParam = useParams().analysisId
  const analysisId = analysisParam ? Number(analysisParam) : undefined
  const [datasetId, setDatasetId] = useState('')
  const [scenarioId, setScenarioId] = useState('')
  const [fetching, setFetching] = useState<ReportKind | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloaded, setDownloaded] = useState(false)

  const datasets = useQuery({ queryKey: ['datasets', analysisId], queryFn: () => listDatasets(analysisId) })
  const scenarios = useQuery({ queryKey: ['scenarios', analysisId], queryFn: () => listScenarios(analysisId) })
  const workflow = useQuery({
    queryKey: ['workflow', analysisId],
    queryFn: () => getWorkflow(analysisId!),
    enabled: Number.isInteger(analysisId),
  })

  if (datasets.isLoading || scenarios.isLoading || workflow.isLoading) return <ApiState.Loading />
  if (datasets.isError || scenarios.isError || workflow.isError) return <ApiState.ErrorState />

  const datasetList = datasets.data?.datasets ?? []
  const scenarioList = scenarios.data?.scenarios ?? []
  const effectiveDatasetId = datasetId || String(datasetList[0]?.id ?? '')
  const effectiveScenarioId = scenarioId
    || String(workflow.data?.scenario?.id ?? scenarioList[0]?.id ?? '')
  const decision = workflow.data?.decision?.result ?? null
  const scenarioDecisionReady = Boolean(
    decision
    && decision.scenario_id === Number(effectiveScenarioId)
    && !workflow.data?.decision_stale,
  )

  if (datasetList.length === 0 && scenarioList.length === 0) {
    return (
      <div>
        {/* Topbar */}
        <div className="topbar">
          <div>
            <div className="topbar-eyebrow">Reports · Export Analysis Results</div>
            <h1 className="page-title">{t('reports.title')}</h1>
            <p className="page-caption">Export your analysis and scenario data as PDF or Excel reports.</p>
          </div>
        </div>
        <ApiState.Empty message={t('reports.empty')} />
      </div>
    )
  }

  async function handleDownload(kind: ReportKind, format: ReportFormat) {
    const id = Number(kind === 'datasets' ? effectiveDatasetId : effectiveScenarioId)
    if (!id) return
    setFetching(kind)
    setError(null)
    setDownloaded(false)
    try {
      const blob = analysisId
        ? await fetchReport(kind, id, format, analysisId)
        : await fetchReport(kind, id, format)
      downloadReport(blob, `novaq_${kind}_${id}.${reportFileExtension(format)}`)
      setDownloaded(true)
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('errors.server'))
    } finally {
      setFetching(null)
    }
  }

  return (
    <div>
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">Reports · Export Analysis Results</div>
          <h1 className="page-title">{t('reports.title')}</h1>
          <p className="page-caption">Export your analysis and scenario data as PDF or Excel reports.</p>
        </div>
      </div>

      {downloaded && <div className="alert alert-ok" style={{ marginTop: '12px' }}>{t('reports.download')}</div>}
      {error && <div className="alert alert-error" style={{ marginTop: '12px' }}>{error}</div>}
      {analysisId && decision && (
        <div className="card" data-testid="report-decision" style={{ marginTop: '12px' }}>
          <span className="badge badge-ok">{t('reports.decision_source')}</span>
          <h3 className="section-title">{decision.headline}</h3>
          <p>{decision.recommendation}</p>
          <p className="form-hint">{decision.provenance_warning}</p>
        </div>
      )}
      {analysisId && !decision && (
        <div className="alert alert-warn" style={{ marginTop: '12px' }}>
          {workflow.data?.decision_stale ? t('reports.decision_stale') : t('reports.decision_required')}{' '}
          <Link to={`/analyses/${analysisId}/decision`}>{t('nav.decision')}</Link>
        </div>
      )}

      {/* Report Preview */}
      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.preview_title')}</h3>
        <p className="form-hint" style={{ marginTop: '2px' }}>{t('reports.preview_hint')}</p>
        <div className="report-sections" style={{ marginTop: '12px' }}>
          {REPORT_SECTIONS.map((section, index) => (
            <div key={section.id} className="report-section" style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
              <div className="report-section-number" style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#f3f8ff', display: 'grid', placeItems: 'center', fontSize: '11px', fontWeight: 800, color: 'var(--accent)', flexShrink: 0 }}>
                {index + 1}
              </div>
              <div className="report-section-content">
                <h3 className="report-section-title" style={{ fontSize: '12px', fontWeight: 800, margin: 0 }}>{t(section.titleKey)}</h3>
                <p className="report-section-desc" style={{ fontSize: '11px', color: '#76889e', margin: '2px 0 0' }}>{t(section.descriptionKey)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Dataset Report */}
      <div className="card" data-testid="report-card-datasets" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.source_dataset')}</h3>
        <div className="form-row" style={{ alignItems: 'flex-end', gap: '10px', marginTop: '8px' }}>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="report-dataset" style={{ fontSize: '11px', fontWeight: 800 }}>{t('reports.source_dataset')}</label>
            <select
              id="report-dataset"
              aria-label={t('reports.source_dataset')}
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
            >
              {datasetList.length === 0 && <option value="">—</option>}
              {datasetList.map((d) => (
                <option key={d.id} value={String(d.id)}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              disabled={fetching !== null || datasetList.length === 0}
              onClick={() => handleDownload('datasets', 'pdf')}
              style={{ padding: '8px 16px', background: '#1a2b4a', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '12px', fontWeight: 700, cursor: fetching !== null ? 'not-allowed' : 'pointer' }}
            >
              {fetching === 'datasets' ? '...' : t('reports.pdf')}
            </button>
            <button
              type="button"
              disabled={fetching !== null || datasetList.length === 0}
              onClick={() => handleDownload('datasets', 'excel')}
              style={{ padding: '8px 16px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '12px', fontWeight: 700, cursor: fetching !== null ? 'not-allowed' : 'pointer' }}
            >
              {fetching === 'datasets' ? '...' : t('reports.excel')}
            </button>
          </div>
        </div>
      </div>

      {/* Scenario Report */}
      <div className="card" data-testid="report-card-scenarios" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('reports.source_scenario')}</h3>
        <div className="form-row" style={{ alignItems: 'flex-end', gap: '10px', marginTop: '8px' }}>
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="report-scenario" style={{ fontSize: '11px', fontWeight: 800 }}>{t('reports.source_scenario')}</label>
            <select
              id="report-scenario"
              aria-label={t('reports.source_scenario')}
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
            >
              {scenarioList.length === 0 && <option value="">—</option>}
              {scenarioList.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              disabled={fetching !== null || scenarioList.length === 0 || Boolean(analysisId && !scenarioDecisionReady)}
              onClick={() => handleDownload('scenarios', 'pdf')}
              style={{ padding: '8px 16px', background: '#1a2b4a', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '12px', fontWeight: 700, cursor: fetching !== null ? 'not-allowed' : 'pointer' }}
            >
              {fetching === 'scenarios' ? '...' : t('reports.pdf')}
            </button>
            <button
              type="button"
              disabled={fetching !== null || scenarioList.length === 0 || Boolean(analysisId && !scenarioDecisionReady)}
              onClick={() => handleDownload('scenarios', 'excel')}
              style={{ padding: '8px 16px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '12px', fontWeight: 700, cursor: fetching !== null ? 'not-allowed' : 'pointer' }}
            >
              {fetching === 'scenarios' ? '...' : t('reports.excel')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
