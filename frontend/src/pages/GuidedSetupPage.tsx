import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getAnalysis, patchAnalysis } from '../api/analyses'
import type { QueueSetup } from '../api/types'
import { QueueIdEditor } from '../components/analysis/QueueIdEditor'
import { ApiState } from '../components/ui/ApiState'

type Answer = 'yes' | 'no' | 'unsure'
type Structure = 'shared_queue' | 'separate_queues'

const OPTIONS: Array<{ value: Answer; labelKey: string }> = [
  { value: 'yes', labelKey: 'guided.yes' },
  { value: 'no', labelKey: 'guided.no' },
  { value: 'unsure', labelKey: 'guided.unsure' },
]

/** Advisory only: Q1 Yes decides shared; otherwise Q2 Yes decides separate. */
function recommend(q1: Answer | null, q2: Answer | null): Structure | null {
  if (q1 === 'yes') return 'shared_queue'
  if (q1 !== null && q2 === 'yes') return 'separate_queues'
  return null
}

export function GuidedSetupPage() {
  const { t } = useTranslation()
  const { analysisId } = useParams()
  const id = Number(analysisId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [q1, setQ1] = useState<Answer | null>(null)
  const [q2, setQ2] = useState<Answer | null>(null)
  const [queueIds, setQueueIds] = useState<string[]>([''])
  const [error, setError] = useState<string | null>(null)

  const analysis = useQuery({
    queryKey: ['analysis', id],
    queryFn: () => getAnalysis(id),
    enabled: Number.isInteger(id),
  })
  const save = useMutation({
    mutationFn: (setup: QueueSetup) => patchAnalysis(id, { queue_setup: setup }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['analysis', id] })
      navigate(`/analyses/${id}/setup`, { replace: true })
    },
    onError: () => setError(t('errors.server')),
  })

  if (!Number.isInteger(id)) return <ApiState.ErrorState />
  if (analysis.isLoading) return <ApiState.Loading />
  if (analysis.isError || !analysis.data) return <ApiState.ErrorState />

  const setup = analysis.data.analysis.queue_setup
  if (setup.queue_structure !== 'unknown') {
    return (
      <div>
        <div className="topbar">
          <div>
            <div className="topbar-eyebrow">{t('analyses.queue_setup')}</div>
            <h1 className="page-title">{t('guided.title')}</h1>
          </div>
        </div>
        <div className="card">
          <p role="status">{t('guided.already_set')}</p>
          <p className="form-hint">
            <Link to={`/analyses/${id}/setup`}>{t('guided.back_to_setup')}</Link>
          </p>
        </div>
      </div>
    )
  }

  const answered = q1 !== null && (q1 === 'yes' || q2 !== null)
  const recommendation = answered ? recommend(q1, q2) : null
  const trimmedIds = queueIds.map((queueId) => queueId.trim())
  const idsValid = trimmedIds.length > 0
    && trimmedIds.every((queueId) => queueId !== '')
    && new Set(trimmedIds).size === trimmedIds.length

  function choose(structure: Structure) {
    setError(null)
    if (structure === 'separate_queues') {
      if (!idsValid) {
        setError(t('analyses.queue_ids_required'))
        return
      }
      save.mutate({ ...setup, queue_structure: structure, queue_ids: trimmedIds })
    } else {
      save.mutate({ ...setup, queue_structure: structure })
    }
  }

  function askAgain() {
    setQ1(null)
    setQ2(null)
    setError(null)
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t('analyses.queue_setup')}</div>
          <h1 className="page-title">{t('guided.title')}</h1>
          <p className="page-caption">{t('guided.caption')}</p>
          <p className="form-hint">{t('guided.unknown_stays')}</p>
        </div>
      </div>
      <div className="card">
        <fieldset className="form-field">
          <legend>{t('guided.common_question')}</legend>
          {OPTIONS.map((option) => (
            <label key={option.value}>
              <input
                type="radio"
                name="guided-q1"
                checked={q1 === option.value}
                onChange={() => setQ1(option.value)}
              />{' '}
              {t(option.labelKey)}
            </label>
          ))}
        </fieldset>
        {q1 !== null && q1 !== 'yes' && (
          <fieldset className="form-field">
            <legend>{t('guided.own_question')}</legend>
            {OPTIONS.map((option) => (
              <label key={option.value}>
                <input
                  type="radio"
                  name="guided-q2"
                  checked={q2 === option.value}
                  onChange={() => setQ2(option.value)}
                />{' '}
                {t(option.labelKey)}
              </label>
            ))}
          </fieldset>
        )}
        {answered && recommendation !== null && (
          <p role="status">
            <strong>{t('guided.recommended')}</strong>{' '}
            {t(recommendation === 'shared_queue' ? 'analyses.structure_shared' : 'analyses.structure_separate')}
          </p>
        )}
        {answered && recommendation === null && (
          <>
            <p role="status">{t('guided.no_recommendation')}</p>
            <p className="form-hint">{t('guided.no_recommendation_help')}</p>
          </>
        )}
        {answered && (
          <>
            <div className="form-row">
              {recommendation !== null ? (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => choose(recommendation)}
                  disabled={save.isPending || (recommendation === 'separate_queues' && !idsValid)}
                >
                  {t('guided.use_structure', {
                    structure: t(recommendation === 'separate_queues' ? 'analyses.structure_separate' : 'analyses.structure_shared'),
                  })}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => choose('shared_queue')}
                    disabled={save.isPending}
                  >
                    {t('guided.use_structure', { structure: t('analyses.structure_shared') })}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => choose('separate_queues')}
                    disabled={save.isPending || !idsValid}
                  >
                    {t('guided.use_structure', { structure: t('analyses.structure_separate') })}
                  </button>
                </>
              )}
              <button type="button" className="btn-ghost" onClick={askAgain}>{t('guided.review')}</button>
            </div>
            <QueueIdEditor ids={queueIds} onChange={setQueueIds} inputIdPrefix="guided-queue-id" />
          </>
        )}
        {error && <div role="alert" className="alert alert-error">{error}</div>}
        <p className="form-hint">
          <Link to={`/analyses/${id}/setup`}>{t('guided.back_to_setup')}</Link>
        </p>
      </div>
    </div>
  )
}
