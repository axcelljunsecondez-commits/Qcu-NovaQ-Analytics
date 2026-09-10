import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { listDatasets } from '../api/datasets'
import { useAuth } from '../auth/useAuth'
import { MetricCard } from '../components/ui/MetricCard'
import { ApiState } from '../components/ui/ApiState'

const quickActions = [
  { key: 'datasets', to: '/datasets', i18n: 'nav.datasets' },
  { key: 'analysis', to: '/analysis', i18n: 'nav.analysis' },
  { key: 'optimize', to: '/optimize', i18n: 'nav.optimize' },
  { key: 'simulate', to: '/simulate', i18n: 'nav.simulate' },
  { key: 'compare', to: '/compare', i18n: 'nav.compare' },
] as const

export function DashboardPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const datasetsQuery = useQuery({
    queryKey: ['datasets'],
    queryFn: () => listDatasets(),
  })

  const datasets = datasetsQuery.data?.datasets ?? []

  const lastUpload = datasets.length > 0 ? datasets[0].created_at : null
  const totalRows = datasets.reduce((sum, d) => sum + d.row_count, 0)

  return (
    <div>
      <h1 className="page-title">{t('dashboard.title')}</h1>
      <p className="page-caption">
        {t('dashboard.greeting')}, <strong>{user?.email}</strong> — {t('dashboard.subtitle')}
      </p>

      {datasetsQuery.isLoading && <ApiState.Loading />}
      {datasetsQuery.isError && <ApiState.ErrorState error={datasetsQuery.error} />}

      {datasetsQuery.isSuccess && (
        <>
          <div className="card-grid">
            <MetricCard label={t('dashboard.datasets')} value={String(datasets.length)} />
            <MetricCard
              label={t('datasets.rows')}
              value={String(totalRows)}
              sub={lastUpload ? `${t('dashboard.last_upload')}: ${new Date(lastUpload).toLocaleDateString()}` : undefined}
            />
          </div>

          <div className="card">
            <h2 className="card-title">{t('dashboard.quick_actions')}</h2>
            <div className="quick-actions">
              {quickActions.map((action) => (
                <Link key={action.key} to={action.to} className="quick-action-link">
                  {t(action.i18n)}
                </Link>
              ))}
            </div>
          </div>

          {datasets.length > 0 && (
            <div className="card">
              <h2 className="card-title">{t('dashboard.datasets')}</h2>
              <table>
                <thead>
                  <tr>
                    <th>{t('datasets.title')}</th>
                    <th>{t('datasets.rows')}</th>
                    <th>{t('dashboard.last_upload')}</th>
                    <th>{t('datasets.valid_ok')}</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.map((d) => (
                    <tr key={d.id}>
                      <td>{d.name}</td>
                      <td>{d.row_count}</td>
                      <td>{new Date(d.created_at).toLocaleDateString()}</td>
                      <td>
                        <span className={`badge ${d.validation.ok ? 'badge-ok' : 'badge-bad'}`}>
                          {d.validation.ok ? '✓' : '✗'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {datasets.length === 0 && <ApiState.Empty message={t('dashboard.no_data')} />}
        </>
      )}
    </div>
  )
}
