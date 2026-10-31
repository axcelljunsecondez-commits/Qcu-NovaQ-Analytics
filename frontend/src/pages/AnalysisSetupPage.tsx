import { headingText } from '../lib/headingText'
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { applySharedAggregateDataset, downloadSetupWorkbook, getAnalysis, getAnalysisCurrent, listAnalysisDatasets, patchAnalysis, previewAnalysisDataset, previewSharedAggregateDataset, uploadAnalysisDataset } from '../api/analyses'
import { getClosingPolicy, putClosingPolicy } from '../api/continuous'
import type { DatasetPreviewOut, DatasetPurpose, EventPeriodBasis, QueueSetup, SharedAggregatePreviewOut } from '../api/types'
import { ApiState } from '../components/ui/ApiState'
import { BreakEditor } from '../components/analysis/BreakEditor'
import { CounterBreakEditor } from '../components/analysis/CounterBreakEditor'
import { counterBreaksValid } from '../lib/counterBreaks'
import { QueueIdEditor } from '../components/analysis/QueueIdEditor'
import { SetupDataTemplates } from '../components/analysis/SetupDataTemplates'
import { messageOf } from '../lib/format'
import { currentDatasetId } from '../lib/datasets'
import { missingSetupFields } from '../lib/setupStatus'
import { MakePeriodsHelper } from '../components/setup/MakePeriodsHelper'
import { ManualEntry } from '../components/setup/ManualEntry'
import { HelpLink } from '../components/ui/HelpLink'
import { FileReadSummary } from '../components/setup/FileReadSummary'
import { MissingChoices, type ClosingChoice } from '../components/setup/MissingChoices'
import { deferredSharedChoices, sharedChoicesComplete } from '../lib/sharedAggregateSetup'
import '../styles/sharedFileSetup.css'

const emptySetup: QueueSetup = { queue_structure: 'unknown', fixed_server_count: null, staffing_varies_by_period: false, capacity_mode: 'unknown', total_system_capacity: null, abandonment_mode: 'unknown', patience_rate_per_hour: null, segments: [], separate_queue_closure_policy: 'drain_existing',     queue_ids: [], breaks: [] }

function normalizeSetup(value: QueueSetup): QueueSetup {
  return {
    ...emptySetup,
    ...value,
    queue_ids: value.queue_ids ?? [],
    segments: (value.segments ?? []).map((segment) => ({ ...segment, active_queue_ids: segment.active_queue_ids ?? null })),
    breaks: (value.breaks ?? []).map((entry) => ({ ...entry })),
  }
}

// Setup fields a file upload can change, labelled with the Setup form's own keys.
const SETUP_FIELD_LABELS: Record<string, string> = {
  queue_structure: 'analyses.queue_structure',
  queue_ids: 'analyses.upload_field_queue_ids',
  segments: 'analyses.segments',
  staffing_varies_by_period: 'analyses.staffing_varies',
  fixed_server_count: 'analyses.server_count',
  event_period_basis: 'analyses.period_basis',
  breaks: 'analyses.breaks_title',
  capacity_mode: 'analyses.capacity',
  total_system_capacity: 'analyses.total_capacity',
  abandonment_mode: 'analyses.abandonment',
  patience_rate_per_hour: 'analyses.theta',
  separate_queue_closure_policy: 'analyses.upload_field_closure_policy',
  counter_breaks: 'analyses.counter_breaks_title',
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
  const id = Number(useParams().analysisId)
  return <AnalysisSetupForId key={id} id={id} />
}

function AnalysisSetupForId({ id }: { id: number }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const currentTranslation = useRef(t)
  currentTranslation.current = t
  const client = useQueryClient()
  const analysis = useQuery({ queryKey: ['analysis', id], queryFn: () => getAnalysis(id) })
  const datasets = useQuery({ queryKey: ['datasets', id], queryFn: () => listAnalysisDatasets(id) })
  // B10: results follow the current planning dataset, not the newest upload.
  const currentId = currentDatasetId(datasets.data?.datasets)
  const aggregatePlanning = datasets.data?.datasets.find((dataset) => dataset.id === currentId)?.validation?.schema === 'aggregate'
  const current = useQuery({ queryKey: ['current', id, currentId], queryFn: () => getAnalysisCurrent(id), enabled: currentId !== null, retry: false })
  const [setup, setSetup] = useState<QueueSetup>(emptySetup)
  const [file, setFile] = useState<File | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  useEffect(() => { if (analysis.data) { setSetup(normalizeSetup(analysis.data.analysis.queue_setup)) } }, [analysis.data])
  const save = useMutation({
    mutationFn: () => patchAnalysis(id, { queue_setup: setup }),
    onSuccess: () => {
      // U10 F3: the period basis is applied when a file is read, so a change needs the planning file uploaded again.
      const basisChanged = (analysis.data?.analysis.queue_setup.event_period_basis ?? 'per_date') !== (setup.event_period_basis ?? 'per_date')
      setFormError(null); setNoticeIsError(false)
      setNotice(basisChanged && currentId !== null ? `${t('analyses.setup_saved')} ${t('setup.basis_reupload')}` : t('analyses.setup_saved'))
      void client.invalidateQueries({ queryKey: ['analysis', id] })
      // Workflow evidence records the Setup it was computed for: drop it so no page shows evidence
      // of the previous Setup, even while its fresh request is in flight (invalidation would).
      void client.resetQueries({ queryKey: ['workflow', id] })
      // A Setup change can make saved scenarios stale: drop their cached evidence status (4d).
      void client.resetQueries({ queryKey: ['scenarios', id] })
    },
  })
  const [preview, setPreview] = useState<Extract<DatasetPreviewOut, { mode: 'multi_sheet' }> | null>(null)
  const [pendingConfirm, setPendingConfirm] = useState(false)
  const [readErrors, setReadErrors] = useState<string[]>([])
  const [checking, setChecking] = useState(false)
  const [noticeIsError, setNoticeIsError] = useState(false)
  // B10 (D16): every upload says what it is for; nothing is preselected.
  const [purpose, setPurpose] = useState<DatasetPurpose | null>(null)
  const [sharedRead, setSharedRead] = useState<{ file: File; result: SharedAggregatePreviewOut } | null>(null)
  const [sharedChecking, setSharedChecking] = useState(false)
  const [sharedError, setSharedError] = useState<string | null>(null)
  const [readAgain, setReadAgain] = useState(0)
  const [recoveryError, setRecoveryError] = useState<{ file: File; message: string } | null>(null)
  const [closing, setClosing] = useState<ClosingChoice>(null)
  const [confirmShared, setConfirmShared] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applied, setApplied] = useState(false)
  const [closingError, setClosingError] = useState<string | null>(null)
  const [closingSaving, setClosingSaving] = useState(false)
  const readSequence = useRef(0)
  const applyLock = useRef(false)
  const appliedFile = useRef<File | null>(null)
  const currentInput = useRef({ file, purpose })
  currentInput.current = { file, purpose }
  const savedShared = analysis.data?.analysis.queue_setup.queue_structure === 'shared_queue'
  const savedSetup = analysis.data?.analysis.queue_setup
  const aggregate = sharedRead?.file === file && purpose === 'planning' ? sharedRead.result : null
  const choices = aggregate?.mode === 'shared_aggregate' ? deferredSharedChoices(aggregate) : {}
  const savedClosing = useQuery({ queryKey: ['closing-policy', id], queryFn: () => getClosingPolicy(id), enabled: aggregate?.mode === 'shared_aggregate' })
  const closingState = useRef({ ready: savedClosing.isSuccess, policy: savedClosing.data?.closing_policy })
  closingState.current = { ready: savedClosing.isSuccess, policy: savedClosing.data?.closing_policy }
  useEffect(() => {
    const sequence = ++readSequence.current
    // Consume only the cache update produced by this apply. Later input or saved-Setup
    // changes must read again, including returning from Review to the same planning file.
    if (file !== null && appliedFile.current === file && purpose === 'planning') { appliedFile.current = null; return }
    appliedFile.current = null
    setRecoveryError((previous) => previous?.file === file && purpose === 'planning' ? previous : null)
    setSharedRead(null); setSharedError(null); setClosing(null); setConfirmShared(false); setApplied(false); setClosingError(null)
    if (!savedShared || purpose !== 'planning' || !file) { setSharedChecking(false); return }
    setSharedChecking(true)
    void previewSharedAggregateDataset(id, file).then((result) => {
      if (sequence === readSequence.current) setSharedRead({ file, result })
    }).catch((error) => {
      if (sequence === readSequence.current) setSharedError(messageOf(error, currentTranslation.current('errors.upload')))
    }).finally(() => {
      if (sequence === readSequence.current) setSharedChecking(false)
    })
    return () => { readSequence.current += 1 }
  }, [id, file, purpose, savedShared, savedSetup, readAgain])
  const upload = useMutation({
    mutationFn: ({ selected, applySetup, purpose: filePurpose }: { selected: File; applySetup: boolean; purpose?: DatasetPurpose }) =>
      filePurpose === 'review'
        ? uploadAnalysisDataset(id, selected, { purpose: 'review' })
        : applySetup ? uploadAnalysisDataset(id, selected, { applySetup: true }) : uploadAnalysisDataset(id, selected),
    onSuccess: (data, variables) => {
      setPurpose(null)
      if (variables.purpose === 'review') {
        // A review-only file never becomes current: plans, simulations and checks stay as they are.
        setNotice(t('setup.review_uploaded'))
        void client.invalidateQueries({ queryKey: ['datasets', id] })
        return
      }
      setNotice(data.dataset.validation.message)
      void client.invalidateQueries({ queryKey: ['datasets', id] })
      void client.invalidateQueries({ queryKey: ['current', id] })
      // The new dataset is now current: drop cached workflow evidence so a page never shows the
      // previous dataset's runs, even while its fresh request is in flight (invalidation would).
      void client.resetQueries({ queryKey: ['workflow', id] })
      // Saved scenarios of the replaced dataset are no longer current (4d).
      void client.resetQueries({ queryKey: ['scenarios', id] })
      if (variables.applySetup) void client.invalidateQueries({ queryKey: ['analysis', id] })
    },
    onError: (error) => setNotice(messageOf(error, t('errors.upload'))),
  })
  if (analysis.isLoading) return <ApiState.Loading />
  if (analysis.isError || !analysis.data) return <ApiState.ErrorState error={analysis.error} />
  const separate = setup.queue_structure === 'separate_queues'
  // Operating segments and the period basis apply to shared lines too (B4b addendum, 2026-10-12);
  // the per-segment counter lists stay separate-lines only.
  const periodLayout = separate || setup.queue_structure === 'shared_queue'
  function set<K extends keyof QueueSetup>(key: K, value: QueueSetup[K]) { setSetup((old) => ({ ...old, [key]: value })) }
  function changeQueueStructure(value: QueueSetup['queue_structure']) {
    if (value === 'separate_queues') {
      setSetup((old) => ({ ...old, queue_structure: value, queue_ids: [], event_period_basis: undefined, segments: old.segments.map((segment) => ({ ...segment, active_queue_ids: null })) }))
      return
    }
    setSetup((old) => ({ ...old, queue_structure: value, queue_ids: [], event_period_basis: undefined, segments: old.segments.map((segment) => ({ ...segment, active_queue_ids: null })) }))
  }
  function changeQueueIds(next: string[]) {
    const removed = setup.queue_ids.filter((queueId) => !next.includes(queueId))
    const segmentReferenced = setup.segments.some((segment) => (segment.active_queue_ids ?? []).some((queueId) => removed.includes(queueId)))
    const breakReferenced = (setup.breaks ?? []).some((entry) => removed.includes(entry.queue_id))
    if (segmentReferenced || breakReferenced) {
      setFormError(t(breakReferenced && !segmentReferenced
        ? 'analyses.break_remove_referenced'
        : 'analyses.queue_remove_referenced'))
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
    if (setup.queue_structure === 'shared_queue' && !counterBreaksValid(setup.counter_breaks ?? [])) return t('analyses.counter_break_error')
    if (setup.queue_structure === 'separate_queues' && (setup.breaks ?? []).some((entry) => !entry.queue_id.trim() || !entry.scheduled_start_time || !Number.isFinite(entry.duration_minutes) || entry.duration_minutes <= 0)) return t('analyses.break_invalid')
    // Saved times arrive as HH:MM:SS, typed ones as HH:MM; compare on HH:MM only.
    const hhmm = (value: string) => value.slice(0, 5)
    const ordered = [...setup.segments].sort((left, right) => hhmm(left.start_time).localeCompare(hhmm(right.start_time)))
    if (ordered.some((segment) => !segment.start_time || !segment.end_time || hhmm(segment.end_time) <= hhmm(segment.start_time))) return t('analyses.segment_time_error')
    if (ordered.slice(1).some((segment, index) => hhmm(segment.start_time) < hhmm(ordered[index].end_time))) return t('analyses.segment_overlap_error')
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
  function pick(event: ChangeEvent<HTMLInputElement>) { setFile(event.target.files?.[0] ?? null); setNotice(null); setPreview(null); setPendingConfirm(false); setReadErrors([]) }
  async function processFile(selected: File) {
    setNotice(null); setNoticeIsError(false); setPreview(null); setPendingConfirm(false); setReadErrors([])
    if (purpose === null) return
    // A review-only file is uploaded as it is: it is never previewed for, and never changes, the Setup.
    if (purpose === 'review') { upload.mutate({ selected, applySetup: false, purpose: 'review' }); return }
    if (!selected.name.toLowerCase().endsWith('.xlsx')) { upload.mutate({ selected, applySetup: false }); return }
    setChecking(true)
    try {
      const result = await previewAnalysisDataset(id, selected)
      if (result.mode === 'legacy') { upload.mutate({ selected, applySetup: false }); return }
      if (result.errors.length > 0 || !result.derived_setup) { setReadErrors(result.errors); return }
      setPreview(result)
      if (result.needs_confirmation) setPendingConfirm(true)
      else upload.mutate({ selected, applySetup: true })
    } catch (error) {
      setNoticeIsError(true)
      setNotice(messageOf(error, t('errors.upload')))
    } finally {
      setChecking(false)
    }
  }
  async function exportWorkbook() {
    try { await downloadSetupWorkbook(id) } catch (error) { setNoticeIsError(true); setNotice(messageOf(error, t('errors.server'))) }
  }
  async function saveFileClosing() {
    if (closingSaving || !closingState.current.ready || closingState.current.policy !== null || (closing !== 'DRAIN' && closing !== 'HARD_CUTOFF')) return
    setClosingSaving(true); setClosingError(null)
    try {
      await putClosingPolicy(id, closing)
      void client.invalidateQueries({ queryKey: ['closing-policy', id] })
      void client.invalidateQueries({ queryKey: ['continuous-compat', id] })
    } catch (error) { setClosingError(messageOf(error, t('errors.server'))) }
    finally { setClosingSaving(false) }
  }
  async function applyFile(confirmReplace = false) {
    if (applyLock.current || applied || !file || !aggregate || aggregate.mode !== 'shared_aggregate'
      || !aggregate.derived_setup || aggregate.conflicts.length > 0 || !sharedChoicesComplete(aggregate, choices)) return
    if (aggregate.needs_confirmation && !confirmReplace) { setConfirmShared(true); return }
    applyLock.current = true
    setApplying(true); setSharedError(null); setRecoveryError(null)
    const selected = file
    try {
      const result = await applySharedAggregateDataset(id, selected, {
        file_digest: aggregate.file_digest, setup_revision: aggregate.setup_revision, confirm_replace: confirmReplace, choices,
      })
      // The server has committed both records; refresh only this analysis's dependent evidence.
      appliedFile.current = selected
      client.setQueryData(['analysis', id], { analysis: result.analysis })
      void client.invalidateQueries({ queryKey: ['datasets', id] })
      void client.invalidateQueries({ queryKey: ['current', id] })
      void client.resetQueries({ queryKey: ['workflow', id] })
      void client.resetQueries({ queryKey: ['scenarios', id] })
      if (currentInput.current.file === selected && currentInput.current.purpose === 'planning') {
        setApplied(true); setConfirmShared(false); setSetup(normalizeSetup(result.analysis.queue_setup))
      }
      // Closing is a separately persisted, explicit operational choice, never part of the Setup fingerprint.
      await saveFileClosing()
    } catch (error) {
      if (currentInput.current.file === selected && currentInput.current.purpose === 'planning') {
        const detail = (error as { response?: { data?: { detail?: { code?: string; reasons?: Array<{ detail?: string }> } } } }).response?.data?.detail
        if (detail?.code === 'setup_changed' || detail?.code === 'file_changed') {
          // Refresh read-only evidence once. Never retry the write or preserve old answers.
          const previousSetup = client.getQueryData<{ analysis: { queue_setup: QueueSetup } }>(['analysis', id])?.analysis.queue_setup
          setRecoveryError({ file: selected, message: t('errors.upload') })
          setSharedRead(null); setClosing(null); setConfirmShared(false); setSharedChecking(true)
          readSequence.current += 1
          await Promise.all([
            client.refetchQueries({ queryKey: ['analysis', id], exact: true }),
            client.refetchQueries({ queryKey: ['datasets', id], exact: true }),
          ])
          if (currentInput.current.file === selected && currentInput.current.purpose === 'planning'
            && client.getQueryData<{ analysis: { queue_setup: QueueSetup } }>(['analysis', id])?.analysis.queue_setup === previousSetup) {
            // A changed Setup triggers the existing effect; unchanged file-only errors need a fresh read too.
            setReadAgain((value) => value + 1)
          }
        } else if (detail?.code === 'confirmation_required') setConfirmShared(true)
        else setSharedError(detail?.reasons?.map((reason) => reason.detail).filter(Boolean).join(' ') || messageOf(error, t('errors.upload')))
      }
    } finally { applyLock.current = false; setApplying(false) }
  }
  const savedIsSeparate = analysis.data.analysis.queue_setup.queue_structure === 'separate_queues'
  const savedIsShared = analysis.data.analysis.queue_setup.queue_structure === 'shared_queue'
  const read = preview?.derived_setup ?? null
  // U10 F4/F10: name what the saved Setup still needs, and open the field that sets it.
  const savedMissing = analysis.data.analysis.setup_status === 'incomplete' ? missingSetupFields(normalizeSetup(analysis.data.analysis.queue_setup)) : []
  const bannerMissing = savedMissing.filter((item) => !(savedIsShared && currentId === null && item.field === 'fixed_server_count'))
  const firstMissingInput = savedMissing.find((item) => item.inputId !== null)?.inputId ?? null
  function sharedDiffValue(field: string, value: unknown, side: QueueSetup): string {
    if (field === 'fixed_server_count' && value === null && side.staffing_varies_by_period) return t('analyses.staffing_varies')
    if (value === null || value === undefined) return t('results.unavailable')
    if (typeof value === 'boolean') return t(value ? 'guided.yes' : 'guided.no')
    if (field === 'segments' && Array.isArray(value)) return `${t('analyses.upload_read_segments', { count: value.length })}${value.length ? ` · ${value.map((entry: QueueSetup['segments'][number]) => `${entry.start_time.slice(0, 5)}–${entry.end_time.slice(0, 5)}`).join(', ')}` : ''}`
    if ((field === 'breaks' || field === 'counter_breaks') && Array.isArray(value)) return value.length ? value.map((entry: { start_time?: string; scheduled_start_time?: string; duration_minutes?: number }) => `${(entry.start_time ?? entry.scheduled_start_time ?? '').slice(0, 5)} · ${t('analyses.break_minutes', { minutes: entry.duration_minutes })}`).join(', ') : t('analyses.upload_read_no_breaks')
    if (field === 'queue_structure') return t(structureDisplayKey(value as QueueSetup['queue_structure']))
    if (field === 'capacity_mode' || field === 'abandonment_mode') return t(`analyses.${String(value)}`)
    if (field === 'event_period_basis') return t(`analyses.period_basis_${String(value)}`)
    if (Array.isArray(value)) return value.join(', ')
    return String(value)
  }
  function openField(inputId: string) {
    if (savedIsShared && ['capacity-mode', 'capacity-total', 'abandonment-mode', 'patience-rate'].includes(inputId)) {
      navigate(`/simulation/results?analysis=${id}&plan=current&advanced=model`)
      return
    }
    setAdvancedOpen(true)
    window.setTimeout(() => document.getElementById(inputId)?.focus(), 0)
  }
  const openMissing = firstMissingInput && (
    <button type="button" className="btn-ghost btn-inline" onClick={() => openField(firstMissingInput)}>{t('setup.incomplete_open')}</button>
  )
  // Data and setup (spec 2026-10-09 §7.6): numbered steps around the unchanged Setup
  // form, upload flow and cache resets. Advanced settings open by default only while
  // the queue structure is still unknown, because choosing it is needed first.
  return (
    <div className="setup-page">
      <header className="page-header">
        <p className="topbar-eyebrow">{t('setup.canonical_eyebrow')}</p>
        <div className="title-row"><h1 lang="en" className="page-title">{headingText(t, 'setup.data_title')}</h1><HelpLink topic="data" /></div>
        <p className="page-caption">{t('setup.data_description')}</p>
      </header>
      {setup.queue_structure === 'unknown' && (
        <div className="alert alert-warn" style={{ marginBottom: '12px' }}>
          {t('analyses.unknown_structure_help')}{' '}
          <Link to="../guided-setup">{t('analyses.choose_structure')}</Link>
        </div>
      )}
      {setup.queue_structure !== 'unknown' && bannerMissing.length > 0 && (
        <div className="alert alert-warn" role="status" data-testid="setup-incomplete">
          <strong>{t('setup.incomplete_title')}</strong>{' '}
          {t('setup.incomplete_body', { items: bannerMissing.map((item) => t(SETUP_FIELD_LABELS[item.field] ?? item.field)).join(', ') })}{' '}
          {openMissing}
        </div>
      )}
      <ol className="setup-steps">
        {!savedIsShared && <li className="setup-step">
          <h2 lang="en" className="setup-step-title">{headingText(t, 'setup.step_template')}</h2>
          <p className="page-caption">{t('setup.step_template_help')}</p>
          {setup.queue_structure === 'shared_queue' || setup.queue_structure === 'separate_queues'
            ? <SetupDataTemplates queueStructure={setup.queue_structure} />
            : <p className="form-hint">{t('setup.step_template_needs_structure')}</p>}
        </li>}
        <li className="setup-step">
          <h2 lang="en" className="setup-step-title">{headingText(t, 'setup.step_add_data')}</h2>
          <div className="card">
            <h3 lang="en" className="card-title">{headingText(t, 'analyses.upload')}</h3>
            <p className="page-caption">{t('analyses.upload_help')}</p>
            <fieldset className="form-field setup-purpose">
              <legend>{t('setup.purpose_question')}</legend><HelpLink topic="data" section="purpose" />
              {(['planning', 'review'] as const).map((value) => (
                <label key={value} className="setup-purpose-option">
                  <input type="radio" name="dataset-purpose" value={value} checked={purpose === value} disabled={applying || upload.isPending} onChange={() => setPurpose(value)} />
                  <span><strong>{t(`setup.purpose_${value}`)}</strong><span className="page-caption">{t(`setup.purpose_${value}_help`)}</span></span>
                </label>
              ))}
            </fieldset>
            <input aria-label={t('analyses.upload')} type="file" accept=".csv,.xlsx" disabled={applying || upload.isPending} onChange={pick} />
            {(!savedIsShared || purpose === 'review' || aggregate?.mode === 'declined') && (
              <button type="button" disabled={!file || purpose === null || upload.isPending || checking || applying} onClick={() => file && void processFile(file)}>{t('analyses.process')}</button>
            )}
            {purpose === null && <p className="form-hint">{t('setup.purpose_required')}</p>}
            {sharedChecking && <p role="status" className="form-hint">{t('common.loading')}</p>}
            {(sharedError || (recoveryError?.file === file && purpose === 'planning')) && <div role="alert" className="alert alert-error">{sharedError || recoveryError?.message}</div>}
            {aggregate?.mode === 'declined' && <div role="status" className="alert alert-warn">
              <p>{t('setup.read_declined')}</p><ul>{aggregate.reasons.map((reason) => <li key={reason.code}>{reason.detail}</li>)}</ul>
            </div>}
            {notice && <div className={`alert ${upload.isError || noticeIsError ? 'alert-error' : 'alert-ok'}`} role={upload.isError || noticeIsError ? 'alert' : 'status'}>{notice}{(upload.isError || noticeIsError) && openMissing && <> {openMissing}</>}</div>}
            {readErrors.length > 0 && (
              <div className="alert alert-error" role="alert">
                <strong>{t('analyses.upload_read_errors')}</strong>
                <ul>{readErrors.map((message) => <li key={message}>{message}</li>)}</ul>
              </div>
            )}
            {pendingConfirm && preview && (
              <div className="alert alert-warn">
                <strong>{t('analyses.upload_confirm_title')}</strong>
                <p>{t('analyses.upload_confirm_help')}</p>
                <ul>{preview.diff.map((change) => <li key={change.field}>{t(SETUP_FIELD_LABELS[change.field] ?? change.field)}</li>)}</ul>
                <button type="button" disabled={upload.isPending} onClick={() => { setPendingConfirm(false); if (file) upload.mutate({ selected: file, applySetup: true }) }}>{t('analyses.upload_confirm')}</button>
                <button type="button" className="btn-ghost" onClick={() => { setPendingConfirm(false); setPreview(null) }}>{t('common.cancel')}</button>
              </div>
            )}
          </div>
        </li>
        {(aggregate?.facts || preview || current.data || (datasets.data?.datasets.length ?? 0) > 0 || !savedIsShared) && <li className="setup-step">
          <h2 lang="en" className="setup-step-title">{headingText(t, 'setup.step_review')}</h2>
          {aggregate?.mode === 'shared_aggregate' && aggregate.facts && aggregate.derived_setup && (
            <FileReadSummary facts={aggregate.facts} derived={aggregate.derived_setup} analysisName={analysis.data.analysis.name} />
          )}
          {preview && read && (
            <section className="card" aria-label={t('analyses.upload_read_title')}>
              <h3 lang="en" className="card-title">{headingText(t, 'analyses.upload_read_title')}</h3>
              <dl>
                <dt>{t('analyses.upload_read_queues')}</dt>
                <dd>{read.queue_ids.join(', ')}</dd>
                <dt>{t('analyses.upload_read_shifts')}</dt>
                <dd>{preview.staff.length > 0 ? <ul>{preview.staff.map((row) => <li key={row.queue_id}>{`${row.queue_id}: ${row.shift_start}–${row.shift_end}`}</li>)}</ul> : t('analyses.upload_read_no_staff')}</dd>
                <dt>{t('analyses.upload_read_segments', { count: read.segments.length })}</dt>
                <dd><ul>{read.segments.map((segment) => <li key={segment.id ?? segment.start_time}>{`${segment.id}: ${(segment.active_queue_ids ?? read.queue_ids).join(', ')}`}</li>)}</ul></dd>
                <dt>{t('analyses.upload_read_breaks')}</dt>
                <dd>{preview.breaks.length > 0 ? <ul>{preview.breaks.map((row) => <li key={row.row}>{`${row.queue_id} · ${row.break_name || t('analyses.break_label', { number: (row.label ?? '').replace(/^Break /, '') })} · ${row.start} · ${t('analyses.break_minutes', { minutes: row.minutes })}`}</li>)}</ul> : t('analyses.upload_read_no_breaks')}</dd>
                <dt>{t('analyses.period_basis')}</dt>
                <dd>{t(read.event_period_basis === 'representative_day' ? 'analyses.period_basis_representative_day' : 'analyses.period_basis_per_date')}</dd>
              </dl>
            </section>
          )}
          {current.data && !aggregate && <div className="card"><h3 lang="en" className="card-title">{headingText(t, 'analyses.why_model')}</h3><p><strong>{current.data.selected_model}</strong></p><details className="collapsible-inline"><summary>{t('filters.show_per_period', { count: current.data.explanations.length })}</summary>{current.data.explanations.map((item, index) => <details key={`${item.time}-${item.queue_id ?? ''}-${index}`}><summary>{item.time}{item.queue_id ? ` · ${item.queue_id}` : ''}: {item.selected_model}</summary><p>{item.selection_reason}</p><h4 lang="en">{headingText(t, 'analyses.operational_facts')}</h4><ul>{item.operational_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul><h4 lang="en">{headingText(t, 'analyses.measured')}</h4><ul>{item.measured_characteristics.map((fact) => <li key={fact}>{fact}</li>)}</ul><h4 lang="en">{headingText(t, 'analyses.assumptions')}</h4><ul>{item.model_assumptions.map((fact) => <li key={fact}>{fact}</li>)}</ul></details>)}</details><Link className="button-link" to={`/results?analysis=${id}`}>{t('analyses.view_current')}</Link></div>}
          {!current.data && !aggregate && !(preview && read) && (
            <p className="form-hint">{t(currentId === null && (datasets.data?.datasets.length ?? 0) > 0 ? 'setup.only_review_files' : 'setup.step_review_empty')}</p>
          )}
        </li>}
        {aggregate?.mode === 'shared_aggregate' && aggregate.derived_setup && <li className="setup-step">
          <div className="card shared-file-apply">
            <MissingChoices closing={closing} onClosingChange={setClosing}
              savedClosing={savedClosing.data?.closing_policy} closingReady={savedClosing.isSuccess} analysisId={id} disabled={applying || applied} />
            {!applied && !sharedChoicesComplete(aggregate, choices) && <Link to={`/simulation/results?analysis=${id}&plan=current&advanced=model`}>{t('setup.incomplete_open')}</Link>}
            {savedClosing.isPending && <p role="status">{t('continuous.closing_title')}: {t('common.loading')}</p>}
            {savedClosing.isError && <p role="alert">{t('continuous.closing_title')}: {messageOf(savedClosing.error, t('errors.server'))}{' '}<Link to={`/simulation/results?analysis=${id}&plan=current`}>{t('continuous.change')}</Link></p>}
            {aggregate.conflicts.length > 0 && <div role="alert" className="alert alert-error"><ul>{aggregate.conflicts.map((conflict) => <li key={conflict.code}>{conflict.detail}{conflict.problems && <ul>{conflict.problems.filter((problem) => !conflict.detail.includes(problem)).map((problem) => <li key={problem}>{problem}</li>)}</ul>}</li>)}</ul></div>}
            {!applied && !confirmShared && <button type="button" className="btn-primary" disabled={applying || aggregate.conflicts.length > 0 || !sharedChoicesComplete(aggregate, choices)} onClick={() => void applyFile()}>{applying ? t('common.saving') : t('analyses.process')}</button>}
            {confirmShared && !applied && <div className="alert alert-warn" role="status">
              <strong>{t(aggregate.diff.length ? 'analyses.upload_confirm_title' : 'analyses.upload')}</strong><p>{t(aggregate.diff.length ? 'analyses.upload_confirm_help' : 'setup.purpose_planning_help')}</p>
              <ul>{aggregate.diff.map((change) => <li key={change.field}>{t(SETUP_FIELD_LABELS[change.field] ?? change.field)}: {sharedDiffValue(change.field, change.saved, aggregate.saved_setup)} → {sharedDiffValue(change.field, change.derived, aggregate.derived_setup!)}</li>)}</ul>
              <button type="button" disabled={applying} onClick={() => void applyFile(true)}>{applying ? t('common.saving') : t(aggregate.diff.length ? 'analyses.upload_confirm' : 'analyses.process')}</button>
              <button type="button" className="btn-ghost" disabled={applying} onClick={() => setConfirmShared(false)}>{t('common.cancel')}</button>
            </div>}
            {applied && <div role="status" className="alert alert-ok"><p>{t('analyses.setup_saved')} · {t('datasets.purpose_planning_current')}</p><div className="button-row">
              <Link className="button-link" to={`/results?analysis=${id}`}>{t('analyses.view_current')}</Link>
              <Link className="button-link" to={`/simulation/results?analysis=${id}&plan=current`}>{t('continuous.title')}</Link>
            </div></div>}
            {applied && closingError && <div role="alert" className="alert alert-error"><p>{t('continuous.closing_title')}: {closingError}</p><button type="button" disabled={closingSaving} onClick={() => void saveFileClosing()}>{closingSaving ? t('common.saving') : t('common.save')}</button></div>}
          </div>
        </li>}
        {savedIsShared && <li className="setup-optional">
          <details className="setup-manual"><summary>{t('setup.step_template')}</summary><p className="page-caption">{t('setup.step_template_help')}</p><SetupDataTemplates queueStructure="shared_queue" /></details>
          <ManualEntry disabled={purpose === null || upload.isPending || checking || applying} onUpload={(selected) => { setFile(selected); if (purpose !== 'planning') void processFile(selected) }} />
        </li>}
        <li className={savedIsShared ? 'setup-optional' : 'setup-step'}>
          <details className="setup-advanced" open={setup.queue_structure === 'unknown' || advancedOpen || undefined} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}>
            <summary lang="en" className={savedIsShared ? 'setup-option-title' : 'setup-step-title'}>{headingText(t, 'setup.step_advanced')}</summary>
            {!savedIsShared && <p className="page-caption">{t('setup.step_advanced_help')}</p>}
            <form className="card" onSubmit={submit}>
              <h3 lang="en" className="card-title">{headingText(t, 'analyses.queue_setup')}</h3>
              {setup.queue_structure === 'unknown' ? (
                <div className="form-field"><label htmlFor="queue-structure">{t('analyses.queue_structure')}</label><select id="queue-structure" aria-describedby="queue-structure-help" value={setup.queue_structure} onChange={(e) => changeQueueStructure(e.target.value as QueueSetup['queue_structure'])}><option value="unknown">{t('analyses.unknown')}</option><option value="shared_queue">{t('analyses.shared')}</option><option value="single_server">{t('analyses.single')}</option><option value="separate_queues">{t('analyses.separate')}</option></select><span id="queue-structure-help" className="form-hint">{t('setup.queue_structure_help')}</span></div>
              ) : (
                <div className="form-field"><span id="queue-structure-label">{t('analyses.queue_structure')}</span><strong data-testid="queue-structure-readonly" aria-labelledby="queue-structure-label">{t(structureDisplayKey(setup.queue_structure))}</strong><span className="form-hint">{t('setup.queue_structure_locked_help')}</span></div>
              )}
              {setup.queue_structure === 'separate_queues' && <QueueIdEditor ids={setup.queue_ids} onChange={changeQueueIds} />}
              {periodLayout && !aggregatePlanning && <div className="form-field"><label htmlFor="period-basis">{t('analyses.period_basis')}</label> <HelpLink topic="data" section="advanced" /><select id="period-basis" aria-describedby="period-basis-help" value={setup.event_period_basis ?? 'per_date'} onChange={(e) => set('event_period_basis', e.target.value as EventPeriodBasis)}><option value="per_date">{t('analyses.period_basis_per_date')}</option><option value="representative_day">{t('analyses.period_basis_representative_day')}</option></select><span id="period-basis-help" className="form-hint">{t('analyses.period_basis_help')}{(setup.event_period_basis ?? 'per_date') === 'per_date' && ` ${t('analyses.period_basis_per_date_limits')}`}</span></div>}
              {setup.queue_structure === 'separate_queues' && <BreakEditor queueIds={setup.queue_ids} breaks={setup.breaks ?? []} onChange={(breaks) => set('breaks', breaks)} />}
              {setup.queue_structure === 'shared_queue' && <CounterBreakEditor breaks={setup.counter_breaks ?? []} onChange={(breaks) => set('counter_breaks', breaks)} />}
              <div className="form-field"><label htmlFor="server-count">{t('analyses.server_count')}</label><input id="server-count" type="number" min="1" disabled={setup.queue_structure === 'single_server'} value={setup.queue_structure === 'single_server' ? 1 : setup.fixed_server_count ?? ''} onChange={(e) => set('fixed_server_count', e.target.value ? Number(e.target.value) : null)} /></div>
              <label><input type="checkbox" checked={setup.staffing_varies_by_period} onChange={(e) => set('staffing_varies_by_period', e.target.checked)} /> {t('analyses.staffing_varies')}</label>
              {periodLayout && <div className="card"><h4 lang="en" className="card-title">{headingText(t, 'analyses.segments')}</h4>{setup.segments.map((segment, index) => <fieldset key={segment.id ?? `segment-${index}`} className="form-field"><legend>{segment.id ?? `Segment ${index + 1}`}</legend><label htmlFor={`segment-start-${index}`}>{t('analyses.segment_start')}</label><input id={`segment-start-${index}`} type="time" value={segment.start_time} onChange={(e) => updateSegment(index, { start_time: e.target.value })} /><label htmlFor={`segment-end-${index}`}>{t('analyses.segment_end')}</label><input id={`segment-end-${index}`} type="time" value={segment.end_time} onChange={(e) => updateSegment(index, { end_time: e.target.value })} />{separate && setup.staffing_varies_by_period && <div>{setup.queue_ids.map((queueId) => <label key={queueId}><input type="checkbox" checked={(segment.active_queue_ids ?? []).includes(queueId)} onChange={() => toggleSegmentQueue(index, queueId)} /> {queueId}</label>)}</div>}<button type="button" onClick={() => set('segments', setup.segments.filter((_, segmentIndex) => segmentIndex !== index))}>{t('analyses.remove_segment')}</button></fieldset>)}<MakePeriodsHelper hasSegments={setup.segments.length > 0} onMake={(periods) => set('segments', periods.map((period, index) => ({ id: `segment_${index + 1}`, start_time: period.start, end_time: period.end, active_queue_ids: separate && setup.staffing_varies_by_period ? [...setup.queue_ids] : null })))} /><button type="button" onClick={() => set('segments', [...setup.segments, { id: nextSegmentId(setup.segments), start_time: '07:00', end_time: '08:00', active_queue_ids: separate && setup.staffing_varies_by_period ? [...setup.queue_ids] : null }])}>{t('analyses.add_segment')}</button></div>}
              {!savedIsShared && setup.queue_structure !== 'shared_queue' && <>
              <div className="form-field"><label htmlFor="capacity-mode">{t('analyses.capacity')}</label><select id="capacity-mode" value={setup.capacity_mode} onChange={(e) => { const value = e.target.value as QueueSetup['capacity_mode']; setSetup((old) => ({ ...old, capacity_mode: value, ...(value !== 'finite' ? { total_system_capacity: null } : {}) })) }}><option value="unknown">{t('analyses.unknown')}</option><option value="unlimited">{t('analyses.unlimited')}</option><option value="finite">{t('analyses.finite')}</option></select></div>
              {setup.capacity_mode === 'finite' && <div className="form-field"><label htmlFor="capacity-total">{t('analyses.total_capacity')}</label><input id="capacity-total" type="number" min="1" value={setup.total_system_capacity ?? ''} onChange={(e) => set('total_system_capacity', e.target.value ? Number(e.target.value) : null)} /></div>}
              <div className="form-field"><label htmlFor="abandonment-mode">{t('analyses.abandonment')}</label><select id="abandonment-mode" value={setup.abandonment_mode} onChange={(e) => { const value = e.target.value as QueueSetup['abandonment_mode']; setSetup((old) => ({ ...old, abandonment_mode: value, ...(value !== 'modeled' ? { patience_rate_per_hour: null } : {}) })) }}><option value="unknown">{t('analyses.unknown')}</option><option value="not_modeled">{t('analyses.not_modeled')}</option><option value="modeled">{t('analyses.modeled')}</option></select></div>
              {setup.abandonment_mode === 'modeled' && <div className="form-field"><label htmlFor="patience-rate">{t('analyses.theta')}</label><input id="patience-rate" type="number" step="any" required aria-invalid={Boolean(formError)} aria-describedby="patience-rate-help" value={setup.patience_rate_per_hour ?? ''} onChange={(e) => { setFormError(null); set('patience_rate_per_hour', e.target.value ? Number(e.target.value) : null) }} /><span id="patience-rate-help" className="form-hint">{t('analyses.theta_required')}</span></div>}
              </>}
              {formError && <div className="alert alert-error" role="alert">{formError}</div>}
              {save.isError && <div className="alert alert-error">{messageOf(save.error, t('errors.server'))}</div>}
              <button type="submit" disabled={save.isPending || applying}>{t('common.save')}</button>
            </form>
          </details>
        </li>
        {savedIsSeparate && (
          <li className="setup-step">
            <h2 lang="en" className="setup-step-title">{headingText(t, 'setup.step_download_setup')}</h2>
            <button type="button" className="btn-secondary" onClick={() => void exportWorkbook()}>{t('analyses.setup_workbook_download')}</button>
            <p className="form-hint">{t('analyses.setup_workbook_help')}</p>
          </li>
        )}
      </ol>
    </div>
  )
}
