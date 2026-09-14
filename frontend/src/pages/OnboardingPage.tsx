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

const servicePointTerms = ['cashiers', 'counters', 'tellers', 'agents', 'staff', 'stations', 'service_points'] as const
const customerTerms = ['customers', 'clients', 'patients', 'passengers', 'visitors'] as const

function safeDestination(value: string | undefined) {
  return value?.startsWith('/') && !value.startsWith('/onboarding') ? value : '/analyses'
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
  const [operationType, setOperationType] = useState('')
  const [servicePointTerm, setServicePointTerm] = useState('')
  const [customerTerm, setCustomerTerm] = useState('')

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
    setOperationType(status.data.operation_type ?? '')
    setServicePointTerm(status.data.preferred_terminology.service_point ?? '')
    setCustomerTerm(status.data.preferred_terminology.customer ?? '')
  }, [destination, navigate, replay, status.data])

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!operationType || !servicePointTerm || !customerTerm) return
    complete.mutate({
      operation_type: operationType,
      preferred_terminology: {
        service_point: servicePointTerm,
        customer: customerTerm,
      },
    })
  }

  if (status.isLoading) return <ApiState.Loading />
  if (status.isError || !status.data) return <ApiState.ErrorState error={status.error} />

  return (
    <main className="onboarding-page" id="main-content">
      <div className="onboarding-shell">
        <section className="onboarding-intro" aria-labelledby="onboarding-title">
          <div className="onboarding-brand">Nova<b>Q</b></div>
          <p className="topbar-eyebrow">{replay ? t('onboarding.replay_eyebrow') : t('onboarding.first_time_eyebrow')}</p>
          <h1 id="onboarding-title" className="onboarding-title">{t('onboarding.welcome')}</h1>
          <p className="onboarding-description">{t('onboarding.welcome_desc')}</p>

          <div className="onboarding-workflow" aria-label={t('workflow.navigation')}>
            {['setup', 'current', 'optimize', 'compare', 'simulate', 'decision', 'reports'].map((step, index) => (
              <div className="onboarding-step" key={step}>
                <span className="onboarding-step-number" aria-hidden="true">{index + 1}</span>
                <span className="onboarding-step-label">{t(`nav.${step}`)}</span>
              </div>
            ))}
          </div>

          <div className="onboarding-facts" aria-labelledby="onboarding-facts-title">
            <h2 id="onboarding-facts-title" className="card-title">{t('onboarding.what_is')}</h2>
            <p>{t('onboarding.what_is_desc')}</p>
            <ul>
              <li>{t('onboarding.fact_data')}</li>
              <li>{t('onboarding.fact_separate')}</li>
              <li>{t('onboarding.fact_evidence')}</li>
            </ul>
          </div>
        </section>

        <form className="onboarding-preferences" onSubmit={submit} aria-labelledby="onboarding-preferences-title">
          <h2 id="onboarding-preferences-title" className="section-title">{t('onboarding.preferences_title')}</h2>
          <p className="page-caption">{t('onboarding.preferences_desc')}</p>

          <div className="form-field">
            <label htmlFor="onboarding-operation">{t('onboarding.operation_type')}</label>
            <select id="onboarding-operation" required value={operationType} onChange={(event) => setOperationType(event.target.value)}>
              <option value="">{t('onboarding.choose_option')}</option>
              {operationTypes.map((value) => <option key={value} value={value}>{t(`onboarding.operation.${value}`)}</option>)}
            </select>
          </div>

          <div className="form-field">
            <label htmlFor="onboarding-service-point">{t('onboarding.service_point_term')}</label>
            <select id="onboarding-service-point" required value={servicePointTerm} onChange={(event) => setServicePointTerm(event.target.value)}>
              <option value="">{t('onboarding.choose_option')}</option>
              {servicePointTerms.map((value) => <option key={value} value={value}>{t(`onboarding.service_point.${value}`)}</option>)}
            </select>
          </div>

          <div className="form-field">
            <label htmlFor="onboarding-customer">{t('onboarding.customer_term')}</label>
            <select id="onboarding-customer" required value={customerTerm} onChange={(event) => setCustomerTerm(event.target.value)}>
              <option value="">{t('onboarding.choose_option')}</option>
              {customerTerms.map((value) => <option key={value} value={value}>{t(`onboarding.customer.${value}`)}</option>)}
            </select>
          </div>

          {complete.isError && (
            <div className="alert alert-error" role="alert">{messageOf(complete.error, t('onboarding.error'))}</div>
          )}

          <div className="onboarding-actions">
            {replay && (
              <button type="button" className="btn-ghost" onClick={() => navigate(destination, { replace: true })}>
                {t('common.cancel')}
              </button>
            )}
            <button type="submit" disabled={complete.isPending || !operationType || !servicePointTerm || !customerTerm}>
              {complete.isPending ? t('common.saving') : replay ? t('onboarding.save_preferences') : t('onboarding.complete')}
            </button>
          </div>
        </form>
      </div>
    </main>
  )
}
