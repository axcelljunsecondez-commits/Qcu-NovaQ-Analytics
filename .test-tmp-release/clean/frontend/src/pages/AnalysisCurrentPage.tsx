import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { getAnalysisCurrent, listAnalysisDatasets } from '../api/analyses'
import { ApiState } from '../components/ui/ApiState'

export function AnalysisCurrentPage() {
  const { t } = useTranslation()
  const id = Number(useParams().analysisId)
  const datasets = useQuery({ queryKey: ['datasets', id], queryFn: () => listAnalysisDatasets(id) })
  const datasetId = datasets.data?.datasets[0]?.id
  const query = useQuery({ queryKey: ['current', id, datasetId], queryFn: () => getAnalysisCurrent(id), enabled: Boolean(datasetId), retry: false })
  if (datasets.isLoading || query.isLoading) return <ApiState.Loading />
  if (query.isError || !query.data) return <div><h1 className="page-title">{t('nav.current')}</h1><ApiState.Empty message={t('analyses.no_dataset')} /><Link className="button-link" to="../setup">{t('analyses.go_setup')}</Link></div>
  return <div><h1 className="page-title">{t('nav.current')}</h1><p className="page-caption">{t('analyses.current_basis')}</p><div className="card"><h2 className="card-title">{query.data.selected_model}</h2><table><thead><tr><th>{t('common.time')}</th><th>λ</th><th>μ</th><th>c</th><th>{t('analysis.model')}</th><th>ρ</th><th>Wq ({t('analyses.minutes')})</th><th>Status</th></tr></thead><tbody>{query.data.rows.map((row, index) => <tr key={String(row.time ?? index)}><td>{String(row.time)}</td><td>{String(row.lambda)}</td><td>{String(row.mu)}</td><td>{String(row.c)}</td><td>{String(row.model)}</td><td>{typeof row.rho === 'number' ? (row.rho * 100).toFixed(1) + '%' : '—'}</td><td>{typeof row.Wq === 'number' ? (row.Wq * 60).toFixed(2) : '—'}</td><td>{String(row.status)}</td></tr>)}</tbody></table></div></div>
}
