import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { TutorialWatch } from '../components/help/TutorialWatch'
import { Link, useSearchParams } from 'react-router-dom'
import { archiveAnalysis, listAnalyses } from '../api/analyses'
import type { AnalysisProjectOut } from '../api/types'
import { ApiState } from '../components/ui/ApiState'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'

type StructureFilter = 'all' | 'shared_queue' | 'separate_queues'

const FILTERS: Array<{ id: StructureFilter; labelKey: string }> = [
  { id: 'all', labelKey: 'analyses.filter_all' },
  { id: 'shared_queue', labelKey: 'analyses.filter_shared' },
  { id: 'separate_queues', labelKey: 'analyses.filter_separate' },
]

function structureBadgeKey(structure: string | undefined): string {
  if (structure === 'separate_queues') return 'home.structure_separate_title'
  if (structure === 'single_server') return 'analyses.single'
  if (structure === 'shared_queue') return 'home.structure_shared_title'
  return 'analyses.unknown'
}

// Operating window from the saved time segments only; nothing is inferred when none are saved.
function operatingWindow(analysis: AnalysisProjectOut): string | null {
  const segments = analysis.queue_setup?.segments ?? []
  if (segments.length === 0) return null
  const starts = segments.map((segment) => segment.start_time.slice(0, 5)).sort()
  const ends = segments.map((segment) => segment.end_time.slice(0, 5)).sort()
  return `${starts[0]}–${ends[ends.length - 1]}`
}

function matchesSearch(analysis: AnalysisProjectOut, search: string): boolean {
  const needle = search.trim().toLocaleLowerCase()
  if (!needle) return true
  return [analysis.name, analysis.location_label, analysis.service_type]
    .some((field) => field?.toLocaleLowerCase().includes(needle))
}

export function AnalysesPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const structure = searchParams.get('structure')
  const filter: StructureFilter = structure === 'shared_queue' || structure === 'separate_queues' ? structure : 'all'
  const search = searchParams.get('q') ?? ''
  const [confirming, setConfirming] = useState<AnalysisProjectOut | null>(null)
  const archiveTrigger = useRef<HTMLButtonElement | null>(null)
  const query = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  const archive = useMutation({
    mutationFn: archiveAnalysis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['analyses'] }),
  })
  if (query.isLoading) return <ApiState.Loading />
  if (query.isError) return <ApiState.ErrorState />
  const all = query.data?.analyses ?? []
  const analyses = all.filter(
    (analysis) => (filter === 'all' || analysis.queue_setup?.queue_structure === filter) && matchesSearch(analysis, search),
  )

  // Filter and search live in the URL so reload and Back restore the same list.
  function updateParams(next: { structure?: StructureFilter; q?: string }) {
    const params = new URLSearchParams(searchParams)
    if (next.structure !== undefined) {
      if (next.structure === 'all') params.delete('structure')
      else params.set('structure', next.structure)
    }
    if (next.q !== undefined) {
      if (next.q) params.set('q', next.q)
      else params.delete('q')
    }
    setSearchParams(params, { replace: true })
  }

  function closeDialog() {
    setConfirming(null)
    archiveTrigger.current?.focus()
  }

  return (
    <div>
      <div className="page-heading-row">
        <div>
          <h1 className="page-title">{t('analyses.title')}</h1>
          <p className="page-caption">{t('analyses.caption')}</p>
        </div>
        <div className="tutorial-heading-actions"><TutorialWatch id="analysis-workflow" /><Link className="button-link" to="/analyses/new">{t('analyses.new')}</Link></div>
      </div>
      {archive.isError && <div role="alert" className="alert alert-error">{t('errors.server')}</div>}
      {all.length === 0 ? (
        <div className="card">
          <ApiState.Empty message={t('analyses.empty')} />
          <div className="form-row">
            <Link className="button-link" to="/analyses/new">{t('analyses.create_first')}</Link>
            <Link to="/help">{t('analyses.empty_help')}</Link>
          </div>
        </div>
      ) : (
        <>
          <div className="analyses-toolbar">
            <div className="form-field analyses-search">
              <label htmlFor="analyses-search">{t('analyses.search_label')}</label>
              <input
                id="analyses-search"
                type="search"
                value={search}
                onChange={(event) => updateParams({ q: event.target.value })}
                placeholder={t('analyses.search_placeholder')}
              />
            </div>
            <div className="form-row" role="group" aria-label={t('analyses.filter_label')}>
              {FILTERS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={filter === item.id ? 'btn-primary' : 'btn-ghost'}
                  aria-pressed={filter === item.id}
                  onClick={() => updateParams({ structure: item.id })}
                >
                  {t(item.labelKey)}
                </button>
              ))}
            </div>
          </div>
          <p className="page-caption" role="status">{t('analyses.count', { count: analyses.length })}</p>
          <div className="card-grid">
            {analyses.length === 0 && <p className="form-hint">{t('analyses.filter_empty')}</p>}
            {analyses.map((analysis) => {
              const window = operatingWindow(analysis)
              return (
                <article className="card" key={analysis.id}>
                  <h2 className="card-title">{analysis.name}</h2>
                  <p>{analysis.location_label || analysis.service_type || t('analyses.no_details')}</p>
                  <span className="badge badge-neutral" data-testid="analysis-structure-badge">
                    {t(structureBadgeKey(analysis.queue_setup?.queue_structure))}
                  </span>{' '}
                  <span className="badge">{t(`analyses.status.${analysis.setup_status}`)}</span>
                  {window && <p className="form-hint">{t('analyses.operating_window', { window })}</p>}
                  <div className="form-row">
                    <Link className="button-link" to={`/analyses/${analysis.id}/data`}>{t('analyses.open')}</Link>
                    {analysis.queue_setup?.queue_structure === 'unknown' && (
                      <Link className="button-link" to={`/analyses/${analysis.id}/guided-setup`}>{t('analyses.choose_structure')}</Link>
                    )}
                    <button
                      className="btn-ghost"
                      type="button"
                      onClick={(event) => {
                        archiveTrigger.current = event.currentTarget
                        setConfirming(analysis)
                      }}
                    >
                      {t('analyses.archive')}
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        </>
      )}
      {confirming && (
        <ConfirmDialog
          title={t('analyses.archive_confirm_title', { name: confirming.name })}
          message={t('analyses.archive_confirm_message')}
          confirmLabel={t('analyses.archive')}
          cancelLabel={t('common.cancel')}
          onCancel={closeDialog}
          onConfirm={() => {
            archive.mutate(confirming.id)
            setConfirming(null)
            // The archived card leaves the list, so focus moves to the search box.
            document.getElementById('analyses-search')?.focus()
          }}
        />
      )}
    </div>
  )
}
