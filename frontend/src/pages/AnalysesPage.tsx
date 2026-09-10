import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { archiveAnalysis, listAnalyses } from '../api/analyses'
import { ApiState } from '../components/ui/ApiState'

export function AnalysesPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  const archive = useMutation({
    mutationFn: archiveAnalysis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['analyses'] }),
  })
  if (query.isLoading) return <ApiState.Loading />
  if (query.isError) return <ApiState.ErrorState />
  const analyses = query.data?.analyses ?? []
  return (
    <div>
      <div className="page-heading-row">
        <div>
          <h1 className="page-title">{t('analyses.title')}</h1>
          <p className="page-caption">{t('analyses.caption')}</p>
        </div>
        <Link className="button-link" to="/analyses/new">{t('analyses.new')}</Link>
      </div>
      {analyses.length === 0 ? (
        <div className="card">
          <ApiState.Empty message={t('analyses.empty')} />
          <Link className="button-link" to="/analyses/new">{t('analyses.create_first')}</Link>
        </div>
      ) : (
        <div className="card-grid">
          {analyses.map((analysis) => (
            <article className="card" key={analysis.id}>
              <h2 className="card-title">{analysis.name}</h2>
              <p>{analysis.location_label || analysis.service_type || t('analyses.no_details')}</p>
              <span className="badge">{t(`analyses.status.${analysis.setup_status}`)}</span>
              <div className="form-row">
                <Link className="button-link" to={`/analyses/${analysis.id}/setup`}>{t('analyses.open')}</Link>
                <button className="btn-ghost" type="button" onClick={() => archive.mutate(analysis.id)}>
                  {t('analyses.archive')}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
