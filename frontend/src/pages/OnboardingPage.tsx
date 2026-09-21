import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { completeOnboarding, getOnboardingStatus } from '../api/onboarding'
import { ApiState } from '../components/ui/ApiState'
import { messageOf } from '../lib/format'

const operationTypes = [
  'retail',
  'financial',
  'healthcare',
  'government',
  'food_service',
  'support',
  'transportation',
  'education',
  'other',
] as const

const servicePointTerms = ['cashiers', 'counters', 'tellers', 'agents', 'staff', 'stations', 'service_points', 'other'] as const
const customerTerms = ['customers', 'clients', 'patients', 'passengers', 'visitors', 'other'] as const

const steps = ['welcome', 'workflow', 'structure', 'guide', 'terms'] as const
const workflowSteps = ['setup', 'current', 'optimize', 'compare', 'simulate', 'decision', 'reports'] as const
const guideSteps = ['setup', 'current', 'optimize', 'simulate', 'decide'] as const
type Structure = 'shared' | 'separate'

// The backend stores operation_type up to 50 characters; custom labels use the same limit.
const CUSTOM_LABEL_MAX = 50
const OTHER = 'other'

function safeDestination(value: string | undefined) {
  return value?.startsWith('/') && !value.startsWith('/onboarding') ? value : '/analyses'
}

/** A term chosen from a list, with free-text labels when "other" is picked. */
interface Term {
  choice: string
  plural: string
  singular: string
}

const emptyTerm: Term = { choice: '', plural: '', singular: '' }

function termComplete(term: Term, needsSingular: boolean) {
  if (!term.choice) return false
  if (term.choice !== OTHER) return true
  return term.plural.trim() !== '' && (!needsSingular || term.singular.trim() !== '')
}

export function OnboardingPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const routeState = location.state as { from?: string; replay?: boolean } | null
  const replay = searchParams.get('replay') === '1' || routeState?.replay === true
  const destination = safeDestination(routeState?.from)
  const [step, setStep] = useState(0)
  const [furthest, setFurthest] = useState(0)
  const [structure, setStructure] = useState<Structure>('shared')
  const [workflowFocus, setWorkflowFocus] = useState<(typeof workflowSteps)[number]>('setup')
  const [operation, setOperation] = useState<Term>(emptyTerm)
  const [servicePoint, setServicePoint] = useState<Term>(emptyTerm)
  const [customer, setCustomer] = useState<Term>(emptyTerm)

  const status = useQuery({ queryKey: ['onboarding'], queryFn: getOnboardingStatus })
  const complete = useMutation({
    mutationFn: completeOnboarding,
    onSuccess: (data) => {
      queryClient.setQueryData(['onboarding'], data)
      navigate(destination, { replace: true })
    },
  })

  useEffect(() => {
    if (!status.data) return
    if (status.data.completed && !replay) {
      navigate(destination, { replace: true })
      return
    }
    const terms = status.data.preferred_terminology
    setOperation({ choice: status.data.operation_type ?? '', plural: terms.operation_label ?? '', singular: '' })
    setServicePoint({ choice: terms.service_point ?? '', plural: terms.service_point_label ?? '', singular: terms.service_point_label_singular ?? '' })
    setCustomer({ choice: terms.customer ?? '', plural: terms.customer_label ?? '', singular: terms.customer_label_singular ?? '' })
  }, [destination, navigate, replay, status.data])

  const termsValid = termComplete(operation, false) && termComplete(servicePoint, true) && termComplete(customer, true)
  const lastStep = steps.length - 1

  function goTo(index: number) {
    setStep(index)
    setFurthest((current) => Math.max(current, index))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (step !== lastStep) {
      goTo(step + 1)
      return
    }
    if (!termsValid) return
    const terminology: Record<string, string> = { service_point: servicePoint.choice, customer: customer.choice }
    if (operation.choice === OTHER) terminology.operation_label = operation.plural.trim()
    if (servicePoint.choice === OTHER) {
      terminology.service_point_label = servicePoint.plural.trim()
      terminology.service_point_label_singular = servicePoint.singular.trim()
    }
    if (customer.choice === OTHER) {
      terminology.customer_label = customer.plural.trim()
      terminology.customer_label_singular = customer.singular.trim()
    }
    complete.mutate({ operation_type: operation.choice, preferred_terminology: terminology })
  }

  function termLabel(term: Term, group: 'service_point' | 'customer') {
    if (term.choice === OTHER) return term.plural.trim()
    return term.choice ? t(`onboarding.${group}.${term.choice}`) : ''
  }

  if (status.isLoading) return <ApiState.Loading />
  if (status.isError || !status.data) return <ApiState.ErrorState error={status.error} />

  const currentStep = steps[step]
  const servicePreview = termLabel(servicePoint, 'service_point')
  const customerPreview = termLabel(customer, 'customer')

  return (
    <main className="onboarding-page" id="main-content">
      <form className="onboarding-wizard" onSubmit={submit} aria-labelledby="onboarding-step-title">
        <header className="onboarding-wizard-header">
          <div className="onboarding-brand">Nova<b>Q</b></div>
          <p className="topbar-eyebrow">{replay ? t('onboarding.replay_eyebrow') : t('onboarding.first_time_eyebrow')}</p>
          <ol className="onboarding-progress" aria-label={t('onboarding.progress_label')}>
            {steps.map((key, index) => (
              <li key={key}>
                <button
                  type="button"
                  className={`onboarding-progress-dot${index === step ? ' is-current' : ''}${index < step ? ' is-done' : ''}`}
                  aria-current={index === step ? 'step' : undefined}
                  disabled={index > furthest}
                  onClick={() => goTo(index)}
                >
                  <span aria-hidden="true">{index + 1}</span>
                  <span className="onboarding-progress-label">{t(`onboarding.step.${key}`)}</span>
                </button>
              </li>
            ))}
          </ol>
          <p className="onboarding-progress-count" aria-live="polite">
            {t('onboarding.step_count', { current: step + 1, total: steps.length })}
          </p>
        </header>

        <section className="onboarding-wizard-body">
          {currentStep === 'welcome' && (
            <>
              <h1 id="onboarding-step-title" className="onboarding-title">{t('onboarding.welcome')}</h1>
              <p className="onboarding-description">{t('onboarding.welcome_desc')}</p>
              <h2 className="card-title">{t('onboarding.what_is')}</h2>
              <ul className="onboarding-pillars">
                {(['measure', 'improve', 'decide'] as const).map((pillar) => (
                  <li key={pillar} className="onboarding-pillar">
                    <strong>{t(`onboarding.pillar.${pillar}`)}</strong>
                    <span>{t(`onboarding.pillar.${pillar}_desc`)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {currentStep === 'workflow' && (
            <>
              <h1 id="onboarding-step-title" className="section-title">{t('onboarding.workflow_title')}</h1>
              <p className="onboarding-description">{t('onboarding.workflow_desc')}</p>
              <div className="onboarding-workflow" role="group" aria-label={t('workflow.navigation')}>
                {workflowSteps.map((key, index) => (
                  <button
                    type="button"
                    key={key}
                    className={`onboarding-step${workflowFocus === key ? ' is-selected' : ''}`}
                    aria-pressed={workflowFocus === key}
                    onClick={() => setWorkflowFocus(key)}
                  >
                    <span className="onboarding-step-number" aria-hidden="true">{index + 1}</span>
                    <span className="onboarding-step-label">{t(`nav.${key}`)}</span>
                  </button>
                ))}
              </div>
              <div className="onboarding-facts" aria-live="polite">
                <h2 className="card-title">{t(`nav.${workflowFocus}`)}</h2>
                <p>{t(`onboarding.workflow.${workflowFocus}`)}</p>
              </div>
            </>
          )}

          {currentStep === 'structure' && (
            <>
              <h1 id="onboarding-step-title" className="section-title">{t('onboarding.structure_title')}</h1>
              <p className="onboarding-description">{t('onboarding.structure_desc')}</p>
              <fieldset className="onboarding-structures">
                <legend className="sr-only">{t('onboarding.structure_title')}</legend>
                {(['shared', 'separate'] as const).map((key) => (
                  <label key={key} className={`onboarding-structure${structure === key ? ' is-selected' : ''}`}>
                    <input type="radio" name="onboarding-structure" value={key} checked={structure === key} onChange={() => setStructure(key)} />
                    <QueueDiagram structure={key} />
                    <strong>{t(`onboarding.structure.${key}`)}</strong>
                    <span>{t(`onboarding.structure.${key}_desc`)}</span>
                    <span className="form-hint">{t(`onboarding.structure.${key}_example`)}</span>
                  </label>
                ))}
              </fieldset>
              <p className="form-hint">{t('onboarding.structure_note')}</p>
            </>
          )}

          {currentStep === 'guide' && (
            <>
              <h1 id="onboarding-step-title" className="section-title">{t(`onboarding.guide.${structure}_title`)}</h1>
              <p className="onboarding-description">{t(`onboarding.guide.${structure}_desc`)}</p>
              <ol className="onboarding-guide">
                {guideSteps.map((key) => (
                  <li key={key}>
                    <strong>{t(`onboarding.guide.${key}_title`)}</strong>
                    <span>{t(`onboarding.guide.${structure}_${key}`)}</span>
                  </li>
                ))}
              </ol>
              <button type="button" className="btn-ghost onboarding-switch" onClick={() => setStructure(structure === 'shared' ? 'separate' : 'shared')}>
                {t(structure === 'shared' ? 'onboarding.guide.show_separate' : 'onboarding.guide.show_shared')}
              </button>
            </>
          )}

          {currentStep === 'terms' && (
            <>
              <h1 id="onboarding-step-title" className="section-title">{t('onboarding.preferences_title')}</h1>
              <p className="page-caption">{t('onboarding.preferences_desc')}</p>

              <TermField
                id="onboarding-operation"
                label={t('onboarding.operation_type')}
                options={operationTypes.map((value) => ({ value, label: t(`onboarding.operation.${value}`) }))}
                term={operation}
                onChange={setOperation}
                pluralLabel={t('onboarding.custom_operation')}
                pluralPlaceholder={t('onboarding.custom_operation_placeholder')}
              />
              <TermField
                id="onboarding-service-point"
                label={t('onboarding.service_point_term')}
                options={servicePointTerms.map((value) => ({ value, label: t(`onboarding.service_point.${value}`) }))}
                term={servicePoint}
                onChange={setServicePoint}
                pluralLabel={t('onboarding.custom_plural')}
                pluralPlaceholder={t('onboarding.custom_service_point_plural_placeholder')}
                singularLabel={t('onboarding.custom_singular')}
                singularPlaceholder={t('onboarding.custom_service_point_singular_placeholder')}
              />
              <TermField
                id="onboarding-customer"
                label={t('onboarding.customer_term')}
                options={customerTerms.map((value) => ({ value, label: t(`onboarding.customer.${value}`) }))}
                term={customer}
                onChange={setCustomer}
                pluralLabel={t('onboarding.custom_plural')}
                pluralPlaceholder={t('onboarding.custom_customer_plural_placeholder')}
                singularLabel={t('onboarding.custom_singular')}
                singularPlaceholder={t('onboarding.custom_customer_singular_placeholder')}
              />

              {servicePreview && customerPreview && (
                <p className="onboarding-preview" aria-live="polite">
                  {t('onboarding.preview', { servicePoints: servicePreview, customers: customerPreview })}
                </p>
              )}

              {complete.isError && (
                <div className="alert alert-error" role="alert">{messageOf(complete.error, t('onboarding.error'))}</div>
              )}
            </>
          )}
        </section>

        <footer className="onboarding-actions">
          {replay && (
            <button type="button" className="btn-ghost" onClick={() => navigate(destination, { replace: true })}>
              {t('common.cancel')}
            </button>
          )}
          {step > 0 && (
            <button type="button" className="btn-ghost" onClick={() => goTo(step - 1)}>
              {t('onboarding.back')}
            </button>
          )}
          {step < lastStep && (
            <button type="button" className="btn-ghost" onClick={() => goTo(lastStep)}>
              {t('onboarding.skip_intro')}
            </button>
          )}
          {step < lastStep ? (
            <button type="submit">{t('onboarding.next')}</button>
          ) : (
            <button type="submit" disabled={complete.isPending || !termsValid}>
              {complete.isPending ? t('common.saving') : replay ? t('onboarding.save_preferences') : t('onboarding.complete')}
            </button>
          )}
        </footer>
      </form>
    </main>
  )
}

interface TermFieldProps {
  id: string
  label: string
  options: { value: string; label: string }[]
  term: Term
  onChange: (term: Term) => void
  pluralLabel: string
  pluralPlaceholder: string
  singularLabel?: string
  singularPlaceholder?: string
}

function TermField({ id, label, options, term, onChange, pluralLabel, pluralPlaceholder, singularLabel, singularPlaceholder }: TermFieldProps) {
  const { t } = useTranslation()
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      <select id={id} required value={term.choice} onChange={(event) => onChange({ ...term, choice: event.target.value })}>
        <option value="">{t('onboarding.choose_option')}</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      {term.choice === OTHER && (
        <fieldset className="onboarding-custom">
          <legend className="sr-only">{label}</legend>
          <div className="form-field">
            <label htmlFor={`${id}-custom`}>{pluralLabel}</label>
            <input
              id={`${id}-custom`}
              type="text"
              required
              maxLength={CUSTOM_LABEL_MAX}
              placeholder={pluralPlaceholder}
              value={term.plural}
              onChange={(event) => onChange({ ...term, plural: event.target.value })}
            />
          </div>
          {singularLabel && (
            <div className="form-field">
              <label htmlFor={`${id}-custom-singular`}>{singularLabel}</label>
              <input
                id={`${id}-custom-singular`}
                type="text"
                required
                maxLength={CUSTOM_LABEL_MAX}
                placeholder={singularPlaceholder}
                value={term.singular}
                onChange={(event) => onChange({ ...term, singular: event.target.value })}
              />
            </div>
          )}
        </fieldset>
      )}
    </div>
  )
}

/** Small schematic: one line feeding every server, or one line per server. */
function QueueDiagram({ structure }: { structure: Structure }) {
  const servers = [20, 50, 80]
  return (
    <svg className="onboarding-diagram" viewBox="0 0 160 100" aria-hidden="true" focusable="false">
      {servers.map((y) => <rect key={`s-${y}`} x="122" y={y - 9} width="26" height="18" rx="4" className="diagram-server" />)}
      {structure === 'shared' ? (
        <>
          {[14, 32, 50, 68].map((x) => <circle key={x} cx={x} cy="50" r="6" className="diagram-person" />)}
          {servers.map((y) => <line key={`l-${y}`} x1="82" y1="50" x2="118" y2={y} className="diagram-line" />)}
        </>
      ) : (
        servers.map((y) => (
          <g key={`q-${y}`}>
            {[62, 80, 98].map((x) => <circle key={x} cx={x} cy={y} r="6" className="diagram-person" />)}
          </g>
        ))
      )}
    </svg>
  )
}
