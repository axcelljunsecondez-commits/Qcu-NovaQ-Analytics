import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { getAnalysis, getAnalysisCurrent, listAnalysisDatasets, patchAnalysis, uploadAnalysisDataset } from '../api/analyses'
import type { QueueSetup } from '../api/types'
import { ApiState } from '../components/ui/ApiState'
import { QueueIdEditor } from '../components/analysis/QueueIdEditor'
import { SetupDataTemplates } from '../components/analysis/SetupDataTemplates'
import { messageOf } from '../lib/format'

const emptySetup: QueueSetup = { queue_structure: 'unknown', fixed_server_count: null, staffing_varies_by_period: false, capacity_mode: 'unknown', total_system_capacity: null, abandonment_mode: 'unknown', patience_rate_per_hour: null, segments: [], separate_queue_closure_policy: 'drain_existing', queue_ids: [] }

function normalizeSetup(value: QueueSetup): QueueSetup {
  return {
    ...emptySetup,
    ...value,
    queue_ids: value.queue_ids ?? [],
    segments: (value.segments ?? []).map((segment) => ({ ...segment, active_queue_ids: segment.active_queue_ids ?? null })),
  }
}

function structureDisplayKey(structure: QueueSetup['queue_structure']): string {
  if (structure === 'shared_queue') return 'analyses.shared'
  if (structure === 'single_server') return 'analyses.single'
  if (structure === 'separate_queues') return 'analyses.separate'
  return 'analyses.unknown'
}

function nextSegmentId(segments: QueueSetup['segments']): string {
  const used = new Set(segments.map((segment) => segment.id))
  let index = segments.length + 1
  while (used.has(`segment_${index}`)) index += 1
  return `segment_${index}`
}

export function AnalysisSetupPage() {
  const { t } = useTranslation()
  const id = Number(useParams().analysisId)
  const client = useQueryClient()
  const analysis = useQuery({ queryKey: ['analysis', id], queryFn: () => getAnalysis(id) })
  const datasets = useQuery({ queryKey: ['datasets', id], queryFn: () => listAnalysisDatasets(id) })
  const current = useQuery({ queryKey: ['current', id, datasets.data?.datasets[0]?.id], queryFn: () => getAnalysisCurrent(id), enabled: Boolean(datasets.data?.datasets.length), retry: false })
  const [setup, setSetup] = useState<QueueSetup>(emptySetup)
  const [file, setFile] = useState<File | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  useEffect(() => { if (analysis.data) { setSetup(normalizeSetup(analysis.data.analysis.queue_setup)) } }, [analysis.data])
  const save = useMutation({
    mutationFn: () => patchAnalysis(id, { queue_setup: setup }),
    onSuccess: () => { setFormError(null); setNotice(t('analyses.setup_saved')); void client.invalidateQueries({ queryKey: ['analysis', id] }) },
  })
  const upload = useMutation({
    mutationFn: (selected: File) => uploadAnalysisDataset(id, selected),
    onSuccess: (data) => { setNotice(data.dataset.validation.message); void client.invalidateQueries({ queryKey: ['datasets', id] }); void client.invalidateQueries({ queryKey: ['current', id] }) },
    onError: (error) => setNotice(messageOf(error, t('errors.upload'))),
  })
  if (analysis.isLoading) return <ApiState.Loading />
  if (analysis.isError || !analysis.data) return <ApiState.ErrorState error={analysis.error} />
  function set<K extends keyof QueueSetup>(key: K, value: QueueSetup[K]) { setSetup((old) => ({ ...old, [key]: value })) }
  function changeQueueStructure(value: QueueSetup['queue_structure']) {
    if (value === 'separate_queues') {
      setSetup((old) => ({ ...old, queue_structure: value, queue_ids: [], segments: old.segments.map((segment) => ({ ...segment, active_queue_ids: null })) }))
      return
    }
    setSetup((old) => ({ ...old, queue_structure: value, queue_ids: [], segments: old.segments.map((segment) => ({ ...segment, active_queue_ids: null })) }))
  }
  function changeQueueIds(next: string[]) {
    const removed = setup.queue_ids.filter((queueId) => !next.includes(queueId))
    const referenced = setup.segments.some((segment) => (segment.active_queue_ids ?? []).some((queueId) => removed.includes(queueId)))
    if (referenced) {
      setFormError(t('analyses.queue_remove_referenced'))
      return
    }
    setFormError(null)
    set('queue_ids', next)
  }
  function updateSegment(index: number, update: Partial<QueueSetup['segments'][number]>) {
    set('segments', setup.segments.map((segment, segmentIndex) => segmentIndex === index ? { ...segment, ...update } : segment))
  }
  function toggleSegmentQueue(index: number, queueId: string) {
    const segment = setup.segments[index]
    const selected = new Set(segment.active_queue_ids ?? [])
    if (selected.has(queueId)) selected.delete(queueId)
    else selected.add(queueId)
    updateSegment(index, { active_queue_ids: [...selected] })
  }
  function validateSetup(): string | null {
    if (setup.queue_structure === 'separate_queues' && setup.queue_ids.length === 0) return t('analyses.queue_ids_required')
    if (setup.queue_structure === 'separate_queues') {
      const trimmed = setup.queue_ids.map((queueId) => queueId.trim())
      if (trimmed.some((queueId) => queueId === '')) return t('analyses.queue_id_blank')
      if (new Set(trimmed).size !== trimmed.length) return t('analyses.queue_id_duplicate')
    }
    if (setup.queue_structure === 'separate_queues' && setup.staffing_varies_by_period && setup.segments.some((segment) => !segment.active_queue_ids?.length)) return t('analyses.active_queue_required')
    const ordered = [...setup.segments].sort((left, right) => left.start_time.localeCompare(right.start_time))
    if (ordered.some((segment) => !segment.start_time || !segment.end_time || segment.end_time <= segment.start_time)) return t('analyses.segment_time_error')
    if (ordered.slice(1).some((segment, index) => segment.start_time < ordered[index].end_time)) return t('analyses.segment_overlap_error')
    return null
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    if (setup.abandonment_mode === 'modeled' && (setup.patience_rate_per_hour === null || !Number.isFinite(setup.patience_rate_per_hour) || setup.patience_rate_per_hour <= 0)) {
      setFormError(t('analyses.theta_positive'))
      return
    }
    const validationError = validateSetup()
    if (validationError) { setFormError(validationError); return }
    setFormError(null)
    save.mutate()
  }
  function pick(event: ChangeEvent<HTMLInputElement>) { setFile(event.target.files?.[0] ?? null); setNotice(null) }
  return (
    <div>
      <header className="page-header">
        <p className="topbar-eyebrow">{t('setup.canonical_eyebrow')}</p>
        <h1 className="page-title">{t('analyses.setup')}</h1>
        <p className="page-caption">{t('setup.canonical_description')}</p>
      </header>
      {setup.queue_structure === 'unknown' && (
        <div className="alert alert-warn" style={{ marginBottom: '12px' }}>
          {t('analyses.unknown_structure_help')}{' '}
          <Link to="../guided-setup">{t('analyses.choose_structure')}</Link>
        </div>
      )}
      <form className="card" onSubmit={submit}>
        <h2 className="card-title">{t('analyses.queue_setup')}</h2>
        {setup.queue_structure === 'unknown' ? (
          <div className="form-field"><label htmlFor="queue-structure">{t('analyses.queue_structure')}</label><select id="queue-structure" aria-describedby="queue-structure-help" value={setup.queue_structure} onChange={(e) => changeQueueStructure(e.target.value as QueueSetup['queue_structure'])}><option value="unknown">{t('analyses.unknown')}</option><option value="shared_queue">{t('analyses.shared')}</option><option value="single_server">{t('analyses.single')}</option><option value="separate_queues">{t('analyses.separate')}</option></select><span id="queue-structure-help" className="form-hint">{t('setup.queue_structure_help')}</span></div>
        ) : (
          <div className="form-field"><span id="queue-structure-label">{t('analyses.queue_structure')}</span><strong data-testid="queue-structure-readonly" aria-labelledby="queue-structure-label">{t(structureDisplayKey(setup.queue_structure))}</strong><span className="form-hint">{t('setup.queue_structure_locked_help')}</span></div>
        )}
        {setup.queue_structure === 'separate_queues' && <QueueIdEditor ids={setup.queue_ids} onChange={changeQueueIds} />}
        <div className="form-field"><label htmlFor="server-count">{t('analyses.server_count')}</label><input id="server-count" type="number" min="1" disabled={setup.queue_structure === 'single_server'} value={setup.queue_structure === 'single_server' ? 1 : setup.fixed_server_count ?? ''} onChange={(e) => set('fixed_server_count', e.target.value ? Number(e.target.value) : null)} /></div>
        <label><input type="checkbox" checked={setup.staffing_varies_by_period} onChange={(e) => set('staffing_varies_by_period', e.target.checked)} /> {t('analyses.staffing_varies')}</label>
        {setup.queue_structure === 'separate_queues' && <div className="card"><h3 className="card-title">{t('analyses.segments')}</h3>{setup.segments.map((segment, index) => <fieldset key={segment.id ?? `segment-${index}`} className="form-field"><legend>{segment.id ?? `Segment ${index + 1}`}</legend><label htmlFor={`segment-start-${index}`}>{t('analyses.segment_start')}</label><input id={`segment-start-${index}`} type="time" value={segment.start_time} onChange={(e) => updateSegment(index, { start_time: e.target.value })} /><label htmlFor={`segment-end-${index}`}>{t('analyses.segment_end')}</label><input id={`segment-end-${index}`} type="time" value={segment.end_time} onChange={(e) => updateSegment(index, { end_time: e.target.value })} />{setup.staffing_varies_by_period && <div>{setup.queue_ids.map((queueId) => <label key={queueId}><input type="checkbox" checked={(segment.active_queue_ids ?? []).includes(queueId)} onChange={() => toggleSegmentQueue(index, queueId)} /> {queueId}</label>)}</div>}<button type="button" onClick={() => set('segments', setup.segments.filter((_, segmentIndex) => segmentIndex !== index))}>{t('analyses.remove_segment')}</button></fieldset>)}<button type="button" onClick={() => set('segments', [...setup.segments, { id: nextSegmentId(setup.segments), start_time: '07:00', end_time: '08:00', active_queue_ids: setup.staffing_varies_by_period ? [...setup.queue_ids] : null }])}>{t('analyses.add_segment')}</button></div>}
        <div className="form-field"><label htmlFor="capacity-mode">{t('analyses.capacity')}</label><select id="capacity-mode" value={setup.capacity_mode} onChange={(e) => { const value = e.target.value as QueueSetup['capacity_mode']; setSetup((old) => ({ ...old, capacity_mode: value, ...(value !== 'finite' ? { total_system_capacity: null } : {}) })) }}><option value="unknown">{t('analyses.unknown')}</option><option value="unlimited">{t('analyses.unlimited')}</option><option value="finite">{t('analyses.finite')}</option></select></div>
        {setup.capacity_mode === 'finite' && <div className="form-field"><label htmlFor="capacity-total">{t('analyses.total_capacity')}</label><input id="capacity-total" type="number" min="1" value={setup.total_system_capacity ?? ''} onChange={(e) => set('total_system_capacity', e.target.value ? Number(e.target.value) : null)} /></div>}
        <div className="form-field"><label htmlFor="abandonment-mode">{t('analyses.abandonment')}</label><select id="abandonment-mode" value={setup.abandonment_mode} onChange={(e) => { const value = e.target.value as QueueSetup['abandonment_mode']; setSetup((old) => ({ ...old, abandonment_mode: value, ...(value !== 'modeled' ? { patience_rate_per_hour: null } : {}) })) }}><option value="unknown">{t('analyses.unknown')}</option><option value="not_modeled">{t('analyses.not_modeled')}</option><option value="modeled">{t('analyses.modeled')}</option></select></div>
        {setup.abandonment_mode === 'modeled' && <div className="form-field"><label htmlFor="patience-rate">{t('analyses.theta')}</label><input id="patience-rate" type="number" step="any" required aria-invalid={Boolean(formError)} aria-describedby="patience-rate-help" value={setup.patience_rate_per_hour ?? ''} onChange={(e) => { setFormError(null); set('patience_rate_per_hour', e.target.value ? Number(e.target.value) : null) }} /><span id="patience-rate-help" className="form-hint">{t('analyses.theta_required')}</span></div>}
        {formError && <div className="alert alert-error" role="alert">{formError}</div>}
        {save.isError && <div className="alert alert-error">{messageOf(save.error, t('errors.server'))}</div>}
        <button type="submit" disabled={save.isPending}>{t('common.save')}</button>
      </form>
      <div className="card">
        <h2 className="card-title">{t('analyses.upload')}</h2>
        <p className="page-caption">{t('analyses.upload_help')}</p>
        <input aria-label={t('analyses.upload')} type="file" accept=".csv,.xlsx" onChange={pick} />
        <button type="button" disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)}>{t('analyses.process')}</button>
        {notice && <div className={`alert ${upload.isError ? 'alert-error' : 'alert-ok'}`} role={upload.isError ? 'alert' : 'status'}>{notice}</div>}
      </div>
      <SetupDataTemplates queueStructure={setup.queue_structure} />
      {current.data && <div className="card"><h2 className="card-title">{t('analyses.why_model')}</h2><p><strong>{current.data.selected_model}</strong></p>{current.data.explanations.map((item) => <details key={item.time}><summary>{item.time}: {item.selected_model}</summary><p>{item.selection_reason}</p><h3>{t('analyses.operational_facts')}</h3><ul>{item.operational_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul><h3>{t('analyses.measured')}</h3><ul>{item.measured_characteristics.map((fact) => <li key={fact}>{fact}</li>)}</ul><h3>{t('analyses.assumptions')}</h3><ul>{item.model_assumptions.map((fact) => <li key={fact}>{fact}</li>)}</ul></details>)}<Link className="button-link" to="../current">{t('analyses.view_current')}</Link></div>}
    </div>
  )
}
