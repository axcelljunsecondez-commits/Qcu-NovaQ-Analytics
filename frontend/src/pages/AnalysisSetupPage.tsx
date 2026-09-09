import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { getAnalysis, getAnalysisCurrent, listAnalysisDatasets, patchAnalysis, uploadAnalysisDataset } from '../api/analyses'
import type { QueueSetup } from '../api/types'
import { ApiState } from '../components/ui/ApiState'

const emptySetup: QueueSetup = { queue_structure: 'unknown', fixed_server_count: null, staffing_varies_by_period: false, capacity_mode: 'unknown', total_system_capacity: null, abandonment_mode: 'unknown', patience_rate_per_hour: null }

function messageOf(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
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
  useEffect(() => { if (analysis.data) setSetup(analysis.data.analysis.queue_setup) }, [analysis.data])
  const save = useMutation({
    mutationFn: () => patchAnalysis(id, { queue_setup: setup }),
    onSuccess: () => { setNotice(t('analyses.setup_saved')); void client.invalidateQueries({ queryKey: ['analysis', id] }) },
  })
  const upload = useMutation({
    mutationFn: (selected: File) => uploadAnalysisDataset(id, selected),
    onSuccess: (data) => { setNotice(data.dataset.validation.message); void client.invalidateQueries({ queryKey: ['datasets', id] }); void client.invalidateQueries({ queryKey: ['current', id] }) },
    onError: (error) => setNotice(messageOf(error, t('errors.upload'))),
  })
  if (analysis.isLoading) return <ApiState.Loading />
  function set<K extends keyof QueueSetup>(key: K, value: QueueSetup[K]) { setSetup((old) => ({ ...old, [key]: value })) }
  function submit(event: FormEvent) { event.preventDefault(); save.mutate() }
  function pick(event: ChangeEvent<HTMLInputElement>) { setFile(event.target.files?.[0] ?? null); setNotice(null) }
  return (
    <div>
      <h1 className="page-title">{t('analyses.setup')}</h1>
      <form className="card" onSubmit={submit}>
        <h2 className="card-title">{t('analyses.queue_setup')}</h2>
        <div className="form-field"><label htmlFor="queue-structure">{t('analyses.queue_structure')}</label><select id="queue-structure" value={setup.queue_structure} onChange={(e) => { const value = e.target.value as QueueSetup['queue_structure']; setSetup((old) => ({ ...old, queue_structure: value, ...(value === 'single_server' ? { fixed_server_count: 1, staffing_varies_by_period: false } : {}) })) }}><option value="unknown">{t('analyses.unknown')}</option><option value="shared_queue">{t('analyses.shared')}</option><option value="single_server">{t('analyses.single')}</option><option value="separate_queues">{t('analyses.separate')}</option></select></div>
        {setup.queue_structure === 'separate_queues' && <div className="alert alert-warn">{t('analyses.separate_unsupported')}</div>}
        <div className="form-field"><label htmlFor="server-count">{t('analyses.server_count')}</label><input id="server-count" type="number" min="1" disabled={setup.queue_structure === 'single_server'} value={setup.queue_structure === 'single_server' ? 1 : setup.fixed_server_count ?? ''} onChange={(e) => set('fixed_server_count', e.target.value ? Number(e.target.value) : null)} /></div>
        <label><input type="checkbox" checked={setup.staffing_varies_by_period} onChange={(e) => set('staffing_varies_by_period', e.target.checked)} /> {t('analyses.staffing_varies')}</label>
        <div className="form-field"><label htmlFor="capacity-mode">{t('analyses.capacity')}</label><select id="capacity-mode" value={setup.capacity_mode} onChange={(e) => { const value = e.target.value as QueueSetup['capacity_mode']; setSetup((old) => ({ ...old, capacity_mode: value, ...(value !== 'finite' ? { total_system_capacity: null } : {}) })) }}><option value="unknown">{t('analyses.unknown')}</option><option value="unlimited">{t('analyses.unlimited')}</option><option value="finite">{t('analyses.finite')}</option></select></div>
        {setup.capacity_mode === 'finite' && <div className="form-field"><label htmlFor="capacity-total">{t('analyses.total_capacity')}</label><input id="capacity-total" type="number" min="1" value={setup.total_system_capacity ?? ''} onChange={(e) => set('total_system_capacity', e.target.value ? Number(e.target.value) : null)} /></div>}
        <div className="form-field"><label htmlFor="abandonment-mode">{t('analyses.abandonment')}</label><select id="abandonment-mode" value={setup.abandonment_mode} onChange={(e) => { const value = e.target.value as QueueSetup['abandonment_mode']; setSetup((old) => ({ ...old, abandonment_mode: value, ...(value !== 'modeled' ? { patience_rate_per_hour: null } : {}) })) }}><option value="unknown">{t('analyses.unknown')}</option><option value="not_modeled">{t('analyses.not_modeled')}</option><option value="modeled">{t('analyses.modeled')}</option></select></div>
        {setup.abandonment_mode === 'modeled' && <div className="form-field"><label htmlFor="patience-rate">{t('analyses.theta')}</label><input id="patience-rate" type="number" min="0" step="any" value={setup.patience_rate_per_hour ?? ''} onChange={(e) => set('patience_rate_per_hour', e.target.value ? Number(e.target.value) : null)} /><span className="form-hint">{t('analyses.theta_required')}</span></div>}
        {save.isError && <div className="alert alert-error">{messageOf(save.error, t('errors.server'))}</div>}
        <button type="submit" disabled={save.isPending}>{t('common.save')}</button>
      </form>
      <div className="card">
        <h2 className="card-title">{t('analyses.upload')}</h2>
        <p className="page-caption">{t('analyses.upload_help')}</p>
        <input aria-label={t('analyses.upload')} type="file" accept=".csv,.xlsx" onChange={pick} />
        <button type="button" disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)}>{t('analyses.process')}</button>
        {notice && <div className={`alert ${upload.isError ? 'alert-error' : 'alert-ok'}`}>{notice}</div>}
      </div>
      {current.data && <div className="card"><h2 className="card-title">{t('analyses.why_model')}</h2><p><strong>{current.data.selected_model}</strong></p>{current.data.explanations.map((item) => <details key={item.time}><summary>{item.time}: {item.selected_model}</summary><p>{item.selection_reason}</p><h3>{t('analyses.operational_facts')}</h3><ul>{item.operational_facts.map((fact) => <li key={fact}>{fact}</li>)}</ul><h3>{t('analyses.measured')}</h3><ul>{item.measured_characteristics.map((fact) => <li key={fact}>{fact}</li>)}</ul><h3>{t('analyses.assumptions')}</h3><ul>{item.model_assumptions.map((fact) => <li key={fact}>{fact}</li>)}</ul></details>)}<Link className="button-link" to="../current">{t('analyses.view_current')}</Link></div>}
    </div>
  )
}
