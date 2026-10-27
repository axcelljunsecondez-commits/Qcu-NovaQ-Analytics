import { headingText } from '../../lib/headingText'
import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getPreferences, savePreferences, type Preferences } from '../../api/preferences'
import { messageOf } from '../../lib/format'
import { ApiState } from '../ui/ApiState'

// Same choices the onboarding wizard offered; the stored values keep their meaning.
const operationTypes = ['retail', 'financial', 'healthcare', 'government', 'food_service', 'support', 'transportation', 'education', 'other'] as const
const servicePointTerms = ['cashiers', 'counters', 'tellers', 'agents', 'staff', 'stations', 'service_points', 'other'] as const
const customerTerms = ['customers', 'clients', 'patients', 'passengers', 'visitors', 'other'] as const

const CUSTOM_LABEL_MAX = 50
const OTHER = 'other'

interface Term {
  choice: string
  plural: string
  singular: string
}

const emptyTerm: Term = { choice: '', plural: '', singular: '' }

function termsFrom(saved: Preferences) {
  const terms = saved.preferred_terminology
  return {
    operation: { choice: saved.operation_type ?? '', plural: terms.operation_label ?? '', singular: '' },
    servicePoint: { choice: terms.service_point ?? '', plural: terms.service_point_label ?? '', singular: terms.service_point_label_singular ?? '' },
    customer: { choice: terms.customer ?? '', plural: terms.customer_label ?? '', singular: terms.customer_label_singular ?? '' },
  }
}

// Only what the user chose is sent; an empty choice saves nothing for that field.
function preferencesPayload(operation: Term, servicePoint: Term, customer: Term): Preferences {
  const terminology: Record<string, string> = {}
  if (operation.choice === OTHER) terminology.operation_label = operation.plural.trim()
  if (servicePoint.choice) terminology.service_point = servicePoint.choice
  if (servicePoint.choice === OTHER) {
    terminology.service_point_label = servicePoint.plural.trim()
    terminology.service_point_label_singular = servicePoint.singular.trim()
  }
  if (customer.choice) terminology.customer = customer.choice
  if (customer.choice === OTHER) {
    terminology.customer_label = customer.plural.trim()
    terminology.customer_label_singular = customer.singular.trim()
  }
  return { operation_type: operation.choice || null, preferred_terminology: terminology }
}

export function PreferencesSettings() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const saved = useQuery({ queryKey: ['preferences'], queryFn: getPreferences })
  const [operation, setOperation] = useState<Term>(emptyTerm)
  const [servicePoint, setServicePoint] = useState<Term>(emptyTerm)
  const [customer, setCustomer] = useState<Term>(emptyTerm)
  const save = useMutation({
    mutationFn: savePreferences,
    onSuccess: (data) => queryClient.setQueryData(['preferences'], data),
  })

  useEffect(() => {
    if (!saved.data) return
    const terms = termsFrom(saved.data)
    setOperation(terms.operation)
    setServicePoint(terms.servicePoint)
    setCustomer(terms.customer)
  }, [saved.data])

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate(preferencesPayload(operation, servicePoint, customer))
  }

  function edit(setter: (term: Term) => void) {
    return (term: Term) => {
      save.reset()
      setter(term)
    }
  }

  return (
    <div>
      <h1 lang="en" className="page-title">{headingText(t, 'settings.section_preferences')}</h1>
      {saved.isLoading && <ApiState.Loading />}
      {saved.isError && <ApiState.ErrorState error={saved.error} />}
      {saved.data && (
        <form className="card" onSubmit={submit}>
          <p className="page-caption">{t('settings.preferences_intro')}</p>
          <p className="page-caption">{t('settings.preferences_not_used')}</p>
          <TermField
            id="preferences-operation"
            label={t('onboarding.operation_type')}
            options={operationTypes.map((value) => ({ value, label: t(`onboarding.operation.${value}`) }))}
            term={operation}
            onChange={edit(setOperation)}
            pluralLabel={t('onboarding.custom_operation')}
            pluralPlaceholder={t('onboarding.custom_operation_placeholder')}
          />
          <TermField
            id="preferences-service-point"
            label={t('onboarding.service_point_term')}
            options={servicePointTerms.map((value) => ({ value, label: t(`onboarding.service_point.${value}`) }))}
            term={servicePoint}
            onChange={edit(setServicePoint)}
            pluralLabel={t('onboarding.custom_plural')}
            pluralPlaceholder={t('onboarding.custom_service_point_plural_placeholder')}
            singularLabel={t('onboarding.custom_singular')}
            singularPlaceholder={t('onboarding.custom_service_point_singular_placeholder')}
          />
          <TermField
            id="preferences-customer"
            label={t('onboarding.customer_term')}
            options={customerTerms.map((value) => ({ value, label: t(`onboarding.customer.${value}`) }))}
            term={customer}
            onChange={edit(setCustomer)}
            pluralLabel={t('onboarding.custom_plural')}
            pluralPlaceholder={t('onboarding.custom_customer_plural_placeholder')}
            singularLabel={t('onboarding.custom_singular')}
            singularPlaceholder={t('onboarding.custom_customer_singular_placeholder')}
          />
          {save.isError && <div className="alert alert-error" role="alert">{messageOf(save.error, t('settings.preferences_error'))}</div>}
          {save.isSuccess && <div className="alert alert-ok" role="status">{t('settings.preferences_saved')}</div>}
          <button type="submit" disabled={save.isPending}>{save.isPending ? t('common.saving') : t('settings.preferences_save')}</button>
        </form>
      )}
    </div>
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
      <select id={id} value={term.choice} onChange={(event) => onChange({ ...term, choice: event.target.value })}>
        <option value="">{t('settings.preferences_not_set')}</option>
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
