import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { archiveAnalysis, listAnalyses } from '../api/analyses'
import { ApiState } from '../components/ui/ApiState'

type StructureFilter = 'all' | 'shared_queue' | 'separate_queues'

const FILTERS: Array<{ id: StructureFilter; labelKey: string }> = [
  { id: 'all', labelKey: 'analyses.filter_all' },
  { id: 'shared_queue', labelKey: 'analyses.filter_shared' },
  { id: 'separate_queues', labelKey: 'analyses.filter_separate' },
]

function structureBadgeKey(structure: string | undefined): string {
  if (structure === 'separate_queues') return 'analyses.separate'
  if (structure === 'single_server') return 'analyses.single'
  if (structure === 'shared_queue') return 'analyses.shared'
  return 'analyses.unknown'
}

export function AnalysesPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const initial = searchParams.get('structure')
  const [filter, setFilter] = useState<StructureFilter>(
    initial === 'shared_queue' || initial === 'separate_queues' ? initial : 'all',
  )
  const query = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  const archive = useMutation({
    mutationFn: archiveAnalysis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['analyses'] }),
  })
  if (query.isLoading) return <ApiState.Loading />
  if (query.isError) return <ApiState.ErrorState />
  const analyses = (query.data?.analyses ?? []).filter(
    (analysis) => filter === 'all' || analysis.queue_setup?.queue_structure === filter,
  )
  function chooseFilter(next: StructureFilter) {
    setFilter(next)
    setSearchParams(next === 'all' ? {} : { structure: next }, { replace: true })
  }
  return (
    <div>
      <div className="page-heading-row">
        <div>
          <h1 className="page-title">{t('analyses.title')}</h1>
          <p className="page-caption">{t('analyses.caption')}</p>
        </div>
        <Link className="button-link" to="/analyses/new">{t('analyses.new')}</Link>
      </div>
      {archive.isError && <div role="alert" className="alert alert-error">{t('errors.server')}</div>}
      {query.data && query.data.analyses.length > 0 && (
        <div className="form-row" role="group" aria-label={t('analyses.filter_label')}>
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={filter === item.id ? 'btn-primary' : 'btn-ghost'}
              aria-pressed={filter === item.id}
              onClick={() => chooseFilter(item.id)}
            >
              {t(item.labelKey)}
            </button>
          ))}
        </div>
      )}
      {(query.data?.analyses.length ?? 0) === 0 ? (
        <div className="card">
          <ApiState.Empty message={t('analyses.empty')} />
          <Link className="button-link" to="/analyses/new">{t('analyses.create_first')}</Link>
        </div>
      ) : (
        <div className="card-grid">
          {analyses.length === 0 && <p className="form-hint">{t('analyses.filter_empty')}</p>}
          {analyses.map((analysis) => (
            <article className="card" key={analysis.id}>
              <h2 className="card-title">{analysis.name}</h2>
              <p>{analysis.location_label || analysis.service_type || t('analyses.no_details')}</p>
              <span className="badge">{t(`analyses.status.${analysis.setup_status}`)}</span>{' '}
              <span className="badge badge-neutral" data-testid="analysis-structure-badge">
                {t(structureBadgeKey(analysis.queue_setup?.queue_structure))}
              </span>
              <div className="form-row">
                <Link className="button-link" to={`/analyses/${analysis.id}/setup`}>{t('analyses.open')}</Link>
                {analysis.queue_setup?.queue_structure === 'unknown' && (
                  <Link className="button-link" to={`/analyses/${analysis.id}/guided-setup`}>{t('analyses.choose_structure')}</Link>
                )}
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
