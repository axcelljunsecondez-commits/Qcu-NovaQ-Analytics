import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { listAnalyses } from '../api/analyses'
import { listDatasets } from '../api/datasets'
import { useAuth } from '../auth/useAuth'
import { MetricCard } from '../components/ui/MetricCard'
import { ApiState } from '../components/ui/ApiState'

const quickActions = [
  { key: 'datasets', globalTo: '/datasets', i18n: 'nav.datasets' },
  { key: 'analysis', globalTo: '/analysis', i18n: 'nav.analysis' },
  { key: 'optimize', scopedPath: 'optimize', i18n: 'nav.optimize' },
  { key: 'compare', scopedPath: 'compare', i18n: 'nav.compare' },
  { key: 'simulate', scopedPath: 'simulate', i18n: 'nav.simulate' },
] as const

export function DashboardPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const datasetsQuery = useQuery({ queryKey: ['datasets'], queryFn: () => listDatasets() })
  const analysesQuery = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  const datasets = datasetsQuery.data?.datasets ?? []
  const analyses = analysesQuery.data?.analyses ?? []
  const latestAnalysis = [...analyses].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0]
  const lastUpload = datasets.length > 0 ? datasets[0].created_at : null
  const totalRows = datasets.reduce((sum, dataset) => sum + dataset.row_count, 0)
  const loading = datasetsQuery.isLoading || analysesQuery.isLoading
  const error = datasetsQuery.error ?? analysesQuery.error

  return (
    <div className="page-stack">
      <header className="page-header">
        <h1 className="page-title">{t('dashboard.title')}</h1>
        <p className="page-caption">{t('dashboard.greeting')}, <strong>{user?.email}</strong> — {t('dashboard.subtitle')}</p>
      </header>

      {loading && <ApiState.Loading />}
      {error && <ApiState.ErrorState error={error} />}

      {!loading && !error && (
        <>
          <div className="card-grid">
            <MetricCard label={t('dashboard.datasets')} value={String(datasets.length)} />
            <MetricCard label={t('datasets.rows')} value={String(totalRows)} sub={lastUpload ? `${t('dashboard.last_upload')}: ${new Date(lastUpload).toLocaleDateString()}` : undefined} />
          </div>

          <section className="card" aria-labelledby="dashboard-actions-title">
            <h2 id="dashboard-actions-title" className="card-title">{t('dashboard.quick_actions')}</h2>
            <p className="page-caption">
              {latestAnalysis
                ? t('dashboard.analysis_context', { name: latestAnalysis.name })
                : t('dashboard.no_analysis_context')}
            </p>
            <div className="quick-actions">
              {quickActions.map((action) => {
                const to = 'globalTo' in action
                  ? action.globalTo
                  : latestAnalysis
                    ? `/analyses/${latestAnalysis.id}/${action.scopedPath}`
                    : '/analyses'
                return <Link key={action.key} to={to} className="quick-action-link">{t(action.i18n)}</Link>
              })}
            </div>
          </section>

          {datasets.length > 0 ? (
            <section className="card" aria-labelledby="dashboard-datasets-title">
              <h2 id="dashboard-datasets-title" className="card-title">{t('dashboard.datasets')}</h2>
              <div className="table-scroll" role="region" aria-labelledby="dashboard-datasets-title" tabIndex={0}>
                <table>
                  <caption className="sr-only">{t('dashboard.dataset_table_caption')}</caption>
                  <thead><tr><th scope="col">{t('datasets.title')}</th><th scope="col">{t('datasets.rows')}</th><th scope="col">{t('dashboard.last_upload')}</th><th scope="col">{t('dashboard.validation')}</th></tr></thead>
                  <tbody>
                    {datasets.map((dataset) => (
                      <tr key={dataset.id}>
                        <th scope="row">{dataset.name}</th>
                        <td>{dataset.row_count}</td>
                        <td>{new Date(dataset.created_at).toLocaleDateString()}</td>
                        <td><span className={`badge ${dataset.validation.ok ? 'badge-ok' : 'badge-bad'}`}>{dataset.validation.ok ? t('dashboard.valid') : t('dashboard.invalid')}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : <ApiState.Empty message={t('dashboard.no_data')} />}
        </>
      )}
    </div>
  )
}
