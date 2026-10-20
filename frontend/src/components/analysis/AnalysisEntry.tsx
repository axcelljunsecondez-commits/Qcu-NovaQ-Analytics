import { useState, useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { listAnalyses } from '../../api/analyses'
import { analysisDestinationHref, type AnalysisDestination } from '../../lib/analysisDestination'
import { resolveLastAnalysis, storedLastAnalysis, subscribeLastAnalysis } from '../../lib/lastAnalysis'
import { ApiState } from '../ui/ApiState'

export function AnalysisEntry({ destination }: { destination: AnalysisDestination }) {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const [search, setSearch] = useState('')
  const stored = useSyncExternalStore(subscribeLastAnalysis, storedLastAnalysis, () => null)
  const analyses = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  const title = t(destination === 'results' ? 'nav.analysis_results' : destination === 'reports' ? 'nav.reports' : 'nav.queue_simulation')
  const last = !analyses.isError && resolveLastAnalysis(analyses.data?.analyses, stored)
  if (!analyses.isLoading && last && !params.has('analysis') && params.get('choose') !== '1') {
    return <Navigate to={analysisDestinationHref(destination, last)} replace />
  }
  const saved = (analyses.data?.analyses ?? []).filter((analysis) => !analysis.archived_at)
  const needle = search.trim().toLocaleLowerCase()
  const matching = saved.filter((analysis) => [analysis.name, analysis.service_type, analysis.location_label]
    .some((value) => value?.toLocaleLowerCase().includes(needle)))

  return (
    <div className="page-stack">
      <header className="page-header">
        <div><h1 className="page-title">{title}</h1><p className="page-caption">{t('analysis_entry.caption')}</p></div>
        <Link className="button-link" to={`/analyses/new?continue=${encodeURIComponent(destination)}`}>{t('analyses.new')}</Link>
      </header>
      {analyses.isLoading ? <ApiState.Loading /> : analyses.isError ? (
        <div className="card">
          <ApiState.ErrorState error={analyses.error} />
          <button type="button" onClick={() => void analyses.refetch()}>{t('analysis_entry.retry')}</button>
        </div>
      ) : saved.length === 0 ? <ApiState.Empty message={t('analyses.empty')} /> : (
        <>
          <div className="form-field">
            <label htmlFor="entry-analysis-search">{t('analyses.search_label')}</label>
            <input id="entry-analysis-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} />
          </div>
          <p role="status">{t('analyses.count', { count: matching.length })}</p>
          {matching.length === 0 && <ApiState.Empty message={t('analyses.filter_empty')} />}
          <div className="card-grid">
            {matching.map((analysis) => (
              <article className="card" key={analysis.id}>
                <h2 className="card-title">{analysis.name}</h2>
                <p>{analysis.location_label || analysis.service_type || t('analyses.no_details')}</p>
                <Link className="button-link" to={analysisDestinationHref(destination, analysis.id)} aria-label={t('analysis_entry.open_named', { name: analysis.name })}>{t('analyses.open')}</Link>
              </article>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
