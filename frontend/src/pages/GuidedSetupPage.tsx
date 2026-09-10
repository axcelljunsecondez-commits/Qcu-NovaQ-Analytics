/**
 * GuidedSetupPage — Operations setup matching the reference design.
 * Step 1: Industry grid with icons
 * Step 2: Queue type selection
 * Step 3: Capacity mode
 * Step 4: Abandonment mode
 * Step 5: Review + confirm
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getAnalysis, patchAnalysis } from '../api/analyses'
import type { QueueSetup } from '../api/types'
import { ApiState } from '../components/ui/ApiState'

type Step = 1 | 2 | 3 | 4 | 5

interface OperationType {
  id: string
  label: string
  icon: string
}

const OPERATION_TYPES: OperationType[] = [
  { id: 'grocery', label: 'Grocery / Retail Store', icon: '\uD83DDED2' },
  { id: 'bank', label: 'Bank / Financial Service', icon: '\uD83C\uDFE6' },
  { id: 'clinic', label: 'Clinic / Healthcare', icon: '\u2764\uFE0F' },
  { id: 'government', label: 'Government Office', icon: '\uD83C\uDFDB\uFE0F' },
  { id: 'restaurant', label: 'Restaurant / Food Service', icon: '\uD83C\uDF7D\uFE0F' },
  { id: 'call_center', label: 'Call Center / Support', icon: '\uD83D\uDCDE' },
  { id: 'transport', label: 'Transportation / Ticketing', icon: '\uD83C\uDFAB' },
  { id: 'school', label: 'School / University', icon: '\uD83C\uDF93' },
]

interface QueueStructure {
  id: string
  label: string
  description: string
  technical: QueueSetup['queue_structure']
}

const QUEUE_STRUCTURES: QueueStructure[] = [
  { id: 'shared', label: 'One shared line', description: 'Customers go to the next available service point.', technical: 'shared_queue' },
  { id: 'separate', label: 'Separate line for each cashier', description: 'Each active cashier has an independent queue.', technical: 'separate_queues' },
  { id: 'auto', label: 'Priority or automatically assigned queue', description: 'Customers may be routed by priority or system rules.', technical: 'shared_queue' },
  { id: 'single', label: 'One service point only', description: 'Only one staff member serves customers.', technical: 'single_server' },
]

export function GuidedSetupPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { analysisId } = useParams()
  const id = Number(analysisId)

  const analysis = useQuery({
    queryKey: ['analysis', id],
    queryFn: () => getAnalysis(id),
    enabled: Number.isInteger(id),
  })

  const [step, setStep] = useState<Step>(1)
  const [operationType, setOperationType] = useState<string>('')
  const [queueStructure, setQueueStructure] = useState<string>('shared')
  const [hasCapacityLimit, setHasCapacityLimit] = useState<boolean | null>(null)
  const [hasAbandonment, setHasAbandonment] = useState<boolean | null>(null)

  const save = useMutation({
    mutationFn: (setup: QueueSetup) => patchAnalysis(id, { queue_setup: setup }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['analysis', id] })
      navigate(`/analyses/${id}/setup`, { replace: true })
    },
  })

  if (analysis.isLoading) return <ApiState.Loading />
  if (analysis.isError || !analysis.data) return <ApiState.ErrorState />

  function buildSetup(): QueueSetup {
    const base: QueueSetup = {
      queue_structure: QUEUE_STRUCTURES.find((q) => q.id === queueStructure)?.technical || 'shared_queue',
      fixed_server_count: null,
      staffing_varies_by_period: false,
      capacity_mode: hasCapacityLimit ? 'finite' : 'unlimited',
      total_system_capacity: null,
      abandonment_mode: hasAbandonment ? 'modeled' : 'not_modeled',
      patience_rate_per_hour: null,
    }
    if (queueStructure === 'single') {
      base.fixed_server_count = 1
    }
    return base
  }

  function handleComplete() {
    save.mutate(buildSetup())
  }

  function handleSkipToEnd() {
    if (analysis.data) {
      save.mutate(analysis.data.analysis.queue_setup)
    }
  }

  return (
    <div className="guided-setup-page">
      <div style={{ marginBottom: '20px' }}>
        <div className="topbar-eyebrow">Setup · Step {step} of 4</div>
        <h1 className="page-title">{t('setup.operation_type')}</h1>
        <p className="page-caption">NovaQ uses plain-language choices to configure the appropriate queue structure and analysis context.</p>
      </div>

      {/* Progress Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '18px' }}>
        {[1, 2, 3, 4].map((s) => (
          <span
            key={s}
            style={{
              height: '4px',
              flex: 1,
              background: s < step ? 'var(--accent)' : s === step ? 'var(--accent)' : '#dfe8f1',
              borderRadius: '4px',
            }}
          />
        ))}
      </div>

      <div className="card" style={{ padding: '18px' }}>
        {step === 1 && (
          <div className="setup-step">
            <h3 className="section-title">{t('setup.operation_type')}</h3>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '10px',
            }}>
              {OPERATION_TYPES.map((op) => (
                <button
                  key={op.id}
                  type="button"
                  onClick={() => setOperationType(op.id)}
                  style={{
                    border: operationType === op.id ? '2px solid var(--accent)' : '1px solid var(--border)',
                    borderRadius: '9px',
                    background: operationType === op.id ? '#f2f8ff' : '#fff',
                    padding: '14px 10px',
                    textAlign: 'center',
                    minHeight: '86px',
                    color: operationType === op.id ? 'var(--accent)' : '#49617b',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontSize: '24px' }}>{op.icon}</div>
                  <strong style={{ display: 'block', color: operationType === op.id ? 'var(--accent)' : '#173d64', fontSize: '11px', marginTop: '8px' }}>
                    {op.label}
                  </strong>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="setup-step">
            <h3 className="section-title">{t('setup.queue_structure')}</h3>
            <div className="radio-group">
              {QUEUE_STRUCTURES.map((qs) => (
                <label
                  key={qs.id}
                  className={`qopt ${queueStructure === qs.id ? 'selected' : ''}`}
                  onClick={() => setQueueStructure(qs.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '12px',
                    cursor: 'pointer',
                    ...(queueStructure === qs.id ? { borderColor: 'var(--accent)', background: '#f3f8ff' } : {}),
                  }}
                >
                  <span className="radio" style={{
                    width: '15px',
                    height: '15px',
                    border: '2px solid #9fb0c2',
                    borderRadius: '50%',
                    marginTop: '1px',
                    ...(queueStructure === qs.id ? { borderColor: 'var(--accent)', boxShadow: 'inset 0 0 0 3px #fff', background: 'var(--accent)' } : {}),
                  }} />
                  <div>
                    <strong style={{ fontSize: '12px' }}>{qs.label}</strong>
                    <small style={{ display: 'block', color: '#76889e', marginTop: '3px', fontSize: '10px' }}>{qs.description}</small>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="setup-step">
            <h3 className="section-title">{t('setup.capacity')}</h3>
            <div className="radio-group">
              {[
                { value: false, label: t('setup.capacity_unlimited') },
                { value: true, label: t('setup.capacity_finite') },
                { value: null, label: t('setup.capacity_not_sure') },
              ].map((opt) => (
                <label
                  key={String(opt.value)}
                  className={`qopt ${hasCapacityLimit === opt.value ? 'selected' : ''}`}
                  onClick={() => setHasCapacityLimit(opt.value)}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '12px',
                    cursor: 'pointer',
                    ...(hasCapacityLimit === opt.value ? { borderColor: 'var(--accent)', background: '#f3f8ff' } : {}),
                  }}
                >
                  <span className="radio" style={{
                    width: '15px',
                    height: '15px',
                    border: '2px solid #9fb0c2',
                    borderRadius: '50%',
                    marginTop: '1px',
                    ...(hasCapacityLimit === opt.value ? { borderColor: 'var(--accent)', boxShadow: 'inset 0 0 0 3px #fff', background: 'var(--accent)' } : {}),
                  }} />
                  <div>
                    <strong style={{ fontSize: '12px' }}>{opt.label}</strong>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="setup-step">
            <h3 className="section-title">{t('setup.abandonment')}</h3>
            <div className="radio-group">
              {[
                { value: true, label: t('setup.abandonment_yes') },
                { value: false, label: t('setup.abandonment_no') },
                { value: null, label: t('setup.abandonment_not_sure') },
              ].map((opt) => (
                <label
                  key={String(opt.value)}
                  className={`qopt ${hasAbandonment === opt.value ? 'selected' : ''}`}
                  onClick={() => setHasAbandonment(opt.value)}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '12px',
                    cursor: 'pointer',
                    ...(hasAbandonment === opt.value ? { borderColor: 'var(--accent)', background: '#f3f8ff' } : {}),
                  }}
                >
                  <span className="radio" style={{
                    width: '15px',
                    height: '15px',
                    border: '2px solid #9fb0c2',
                    borderRadius: '50%',
                    marginTop: '1px',
                    ...(hasAbandonment === opt.value ? { borderColor: 'var(--accent)', boxShadow: 'inset 0 0 0 3px #fff', background: 'var(--accent)' } : {}),
                  }} />
                  <div>
                    <strong style={{ fontSize: '12px' }}>{opt.label}</strong>
                  </div>
                </label>
              ))}
            </div>

            {/* Summary */}
            <div className="setup-summary" style={{ marginTop: '16px' }}>
              <h3 className="section-title">{t('setup.summary')}</h3>
              <div className="setup-summary-row">
                <span className="setup-summary-label">{t('setup.summary_operation')}</span>
                <span className="setup-summary-value">{OPERATION_TYPES.find((o) => o.id === operationType)?.label || '—'}</span>
              </div>
              <div className="setup-summary-row">
                <span className="setup-summary-label">{t('setup.summary_queue')}</span>
                <span className="setup-summary-value">{QUEUE_STRUCTURES.find((q) => q.id === queueStructure)?.label}</span>
              </div>
              <div className="setup-summary-row">
                <span className="setup-summary-label">{t('setup.summary_capacity')}</span>
                <span className="setup-summary-value">{hasCapacityLimit === true ? t('setup.capacity_finite') : hasCapacityLimit === false ? t('setup.capacity_unlimited') : t('setup.capacity_not_sure')}</span>
              </div>
              <div className="setup-summary-row">
                <span className="setup-summary-label">{t('setup.summary_abandonment')}</span>
                <span className="setup-summary-value">{hasAbandonment === true ? t('setup.abandonment_yes') : hasAbandonment === false ? t('setup.abandonment_no') : t('setup.abandonment_not_sure')}</span>
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {step > 1 && (
              <button type="button" className="btn-ghost" onClick={() => setStep((s) => (s - 1) as Step)}>
                Back
              </button>
            )}
            {step === 1 && (
              <button type="button" className="btn-ghost" onClick={handleSkipToEnd}>
                {t('setup.skip_to_standard')}
              </button>
            )}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {step < 4 ? (
              <button
                type="button"
                onClick={() => setStep((s) => (s + 1) as Step)}
                disabled={step === 1 && !operationType}
              >
                Next →
              </button>
            ) : (
              <button type="button" onClick={handleComplete} disabled={save.isPending}>
                {save.isPending ? 'Saving...' : 'Confirm Setup →'}
              </button>
            )}
          </div>
        </div>

        {save.isError && (
          <div className="alert alert-error" style={{ marginTop: '12px' }}>
            Failed to save setup. Please try again.
          </div>
        )}
      </div>
    </div>
  )
}
