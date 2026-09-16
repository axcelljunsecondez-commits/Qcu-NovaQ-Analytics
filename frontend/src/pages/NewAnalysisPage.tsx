import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { createAnalysis } from '../api/analyses'
import type { QueueSetup, QueueStructure } from '../api/types'
import { QueueIdEditor } from '../components/analysis/QueueIdEditor'

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
}

type Choice = 'shared_queue' | 'separate_queues'

export function NewAnalysisPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [serviceType, setServiceType] = useState('')
  const [location, setLocation] = useState('')
  const [choice, setChoice] = useState<Choice>('shared_queue')
  const [queueIds, setQueueIds] = useState<string[]>([''])
  const create = useMutation({
    mutationFn: createAnalysis,
    onSuccess: ({ analysis }) => {
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
      navigate(`/analyses/${analysis.id}/setup`, { replace: true })
    },
  })
  const help = useMutation({
    mutationFn: createAnalysis,
    onSuccess: ({ analysis }) => {
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
      navigate(`/analyses/${analysis.id}/guided-setup`, { replace: true })
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
  function helpMeChoose() {
    help.mutate({ ...details(), queue_setup: setupFor('unknown') })
  }
  const trimmedIds = queueIds.map((queueId) => queueId.trim())
  const idsValid = choice === 'shared_queue'
    || (trimmedIds.length > 0 && trimmedIds.every((queueId) => queueId !== '') && new Set(trimmedIds).size === trimmedIds.length)
  const pending = create.isPending || help.isPending
  return (
    <div>
      <h1 className="page-title">{t('analyses.new')}</h1>
      <p className="page-caption">{t('analyses.details_help')}</p>
      <form className="card" role="dialog" aria-labelledby="new-analysis-title" onSubmit={submit}>
        <h2 id="new-analysis-title" className="card-title">{t('analyses.new')}</h2>
        <div className="form-field"><label htmlFor="analysis-name">{t('analyses.name')}</label><input id="analysis-name" required value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="service-type">{t('analyses.service_type')}</label><input id="service-type" value={serviceType} onChange={(e) => setServiceType(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="location-label">{t('analyses.location')}</label><input id="location-label" value={location} onChange={(e) => setLocation(e.target.value)} /></div>
        <fieldset className="form-field">
          <legend>{t('analyses.structure_title')}</legend>
          <div className="card-grid">
            <label className="card">
              <input type="radio" name="queue_structure" value="shared_queue" checked={choice === 'shared_queue'} onChange={() => setChoice('shared_queue')} />
              <strong>{t('analyses.structure_shared')}</strong>
              <span className="form-hint">{t('analyses.structure_shared_desc')}</span>
              <span className="form-hint" aria-hidden="true">Customers ↓ Shared Line ↓ S1 S2 S3</span>
            </label>
            <label className="card">
              <input type="radio" name="queue_structure" value="separate_queues" checked={choice === 'separate_queues'} onChange={() => setChoice('separate_queues')} />
              <strong>{t('analyses.structure_separate')}</strong>
              <span className="form-hint">{t('analyses.structure_separate_desc')}</span>
              <span className="form-hint" aria-hidden="true">Q1 → S1 · Q2 → S2 · Q3 → S3</span>
            </label>
          </div>
        </fieldset>
        {choice === 'separate_queues' && (
          <QueueIdEditor ids={queueIds} onChange={setQueueIds} inputIdPrefix="new-queue-id" />
        )}
        {(create.isError || help.isError) && <div role="alert" className="alert alert-error">{t('errors.server')}</div>}
        <div className="form-row">
          <button type="submit" className="btn-primary" disabled={!name.trim() || !idsValid || pending}>{t('analyses.continue')}</button>
          <button type="button" className="btn-ghost" disabled={!name.trim() || pending} onClick={helpMeChoose}>{t('analyses.structure_help_choose')}</button>
        </div>
      </form>
    </div>
  )
}
