import { headingText } from '../lib/headingText'
import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createAnalysis } from '../api/analyses'
import type { QueueSetup, QueueStructure } from '../api/types'
import { QueueIdEditor } from '../components/analysis/QueueIdEditor'
import { LineStructurePicture } from '../components/illustrations/LineStructurePicture'
import { answered, recommend, type Answer } from '../lib/structureRecommendation'
import { analysisDestinationHref, parseAnalysisDestination } from '../lib/analysisDestination'

const baseSetup: QueueSetup = {
  queue_structure: 'unknown',
  fixed_server_count: null,
  staffing_varies_by_period: false,
  capacity_mode: 'unknown',
  total_system_capacity: null,
  abandonment_mode: 'unknown',
  patience_rate_per_hour: null,
  segments: [],
  separate_queue_closure_policy: 'drain_existing',
  queue_ids: [],
  breaks: [],
}

type Choice = 'shared_queue' | 'separate_queues'

const STRUCTURES: Array<{ value: Choice; variant: 'shared' | 'separate' }> = [
  { value: 'shared_queue', variant: 'shared' },
  { value: 'separate_queues', variant: 'separate' },
]

const ANSWERS: Array<{ value: Answer; labelKey: string }> = [
  { value: 'yes', labelKey: 'guided.yes' },
  { value: 'no', labelKey: 'guided.no' },
  { value: 'unsure', labelKey: 'guided.unsure' },
]

// New analysis (spec §7.5, D11): same fields and API as before; the structure
// choice uses the Home pictures and the two-question recommender is inline.
export function NewAnalysisPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const destination = parseAnalysisDestination(params.get('continue'))
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [serviceType, setServiceType] = useState('')
  const [location, setLocation] = useState('')
  const [choice, setChoice] = useState<Choice>('shared_queue')
  const [queueIds, setQueueIds] = useState<string[]>([''])
  const [q1, setQ1] = useState<Answer | null>(null)
  const [q2, setQ2] = useState<Answer | null>(null)
  const create = useMutation({
    mutationFn: createAnalysis,
    onSuccess: ({ analysis }) => {
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
      navigate(destination ? analysisDestinationHref(destination, analysis.id) : `/analyses/${analysis.id}/data`, { replace: true })
    },
  })
  function setupFor(structure: QueueStructure): QueueSetup {
    if (structure === 'separate_queues') {
      return { ...baseSetup, queue_structure: structure, queue_ids: queueIds.map((queueId) => queueId.trim()) }
    }
    return { ...baseSetup, queue_structure: structure }
  }
  function details() {
    return { name: name.trim(), service_type: serviceType || null, location_label: location || null }
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate({ ...details(), queue_setup: setupFor(choice) })
  }
  // Keeps the earlier option of saving the analysis with the structure still unknown.
  function decideLater() {
    create.mutate({ ...details(), queue_setup: setupFor('unknown') })
  }
  const trimmedIds = queueIds.map((queueId) => queueId.trim())
  const idsValid = choice === 'shared_queue'
    || (trimmedIds.length > 0 && trimmedIds.every((queueId) => queueId !== '') && new Set(trimmedIds).size === trimmedIds.length)
  const done = answered(q1, q2)
  const recommendation = done ? recommend(q1, q2) : null
  const structureTitle = (value: Choice) => t(value === 'shared_queue' ? 'home.structure_shared_title' : 'home.structure_separate_title')

  return (
    <div>
      <h1 lang="en" className="page-title">{headingText(t, 'analyses.new')}</h1>
      <p className="page-caption">{t('analyses.details_help')}</p>
      <form className="card" aria-label={t('analyses.new')} onSubmit={submit}>
        <div className="form-field"><label htmlFor="analysis-name">{t('analyses.name')}</label><input id="analysis-name" required value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="service-type">{t('analyses.service_type')}</label><input id="service-type" value={serviceType} onChange={(e) => setServiceType(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="location-label">{t('analyses.location')}</label><input id="location-label" value={location} onChange={(e) => setLocation(e.target.value)} /></div>
        <fieldset className="form-field structure-choice">
          <legend>{t('home.structures_title')}</legend>
          <div className="structure-choice-grid">
            {STRUCTURES.map((structure) => (
              <label key={structure.value} className={`card structure-choice-card${choice === structure.value ? ' is-selected' : ''}`}>
                <LineStructurePicture variant={structure.variant} />
                <span className="structure-choice-title">
                  <input
                    type="radio"
                    name="queue_structure"
                    value={structure.value}
                    checked={choice === structure.value}
                    onChange={() => setChoice(structure.value)}
                  />
                  <strong lang="en">{headingText(t, structure.value === 'shared_queue' ? 'home.structure_shared_title' : 'home.structure_separate_title')}</strong>
                </span>
                <span>{t(`home.structure_${structure.variant}_desc`)}</span>
                <span className="home-note">{t(`home.structure_${structure.variant}_example`)}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {choice === 'separate_queues' && (
          <QueueIdEditor ids={queueIds} onChange={setQueueIds} inputIdPrefix="new-queue-id" />
        )}

        <details className="structure-helper">
          <summary>{t('analyses.structure_helper_summary')}</summary>
          <fieldset className="form-field">
            <legend>{t('guided.common_question')}</legend>
            {ANSWERS.map((option) => (
              <label key={option.value}>
                <input type="radio" name="helper-q1" checked={q1 === option.value} onChange={() => { setQ1(option.value); setQ2(null) }} />{' '}
                {t(option.labelKey)}
              </label>
            ))}
          </fieldset>
          {q1 !== null && q1 !== 'yes' && (
            <fieldset className="form-field">
              <legend>{t('guided.own_question')}</legend>
              {ANSWERS.map((option) => (
                <label key={option.value}>
                  <input type="radio" name="helper-q2" checked={q2 === option.value} onChange={() => setQ2(option.value)} />{' '}
                  {t(option.labelKey)}
                </label>
              ))}
            </fieldset>
          )}
          {done && recommendation !== null && (
            <div className="form-row">
              <p role="status"><strong>{t('guided.recommended')}</strong> {structureTitle(recommendation)}</p>
              <button type="button" className="btn-ghost" disabled={choice === recommendation} onClick={() => setChoice(recommendation)}>
                {t('analyses.structure_helper_use')}
              </button>
            </div>
          )}
          {done && recommendation === null && (
            <>
              <p role="status">{t('guided.no_recommendation')}</p>
              <p className="page-caption">{t('analyses.structure_helper_later_help')}</p>
              <button type="button" className="btn-ghost" disabled={!name.trim() || create.isPending} onClick={decideLater}>
                {t('analyses.structure_helper_later')}
              </button>
            </>
          )}
        </details>

        {create.isError && <div role="alert" className="alert alert-error">{t('errors.server')}</div>}
        <div className="form-row">
          <button type="submit" className="btn-primary" disabled={!name.trim() || !idsValid || create.isPending}>{t(destination ? 'analysis_entry.create' : 'analyses.continue')}</button>
        </div>
      </form>
    </div>
  )
}
