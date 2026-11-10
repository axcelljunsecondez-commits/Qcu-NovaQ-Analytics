import { useId, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { selectWorkflowScenario } from '../api/workflow'
import { messageOf } from '../lib/format'
import { headingText } from '../lib/headingText'
import { eligibleSavedPlans, useSelectedPlan } from './results/useSelectedPlan'

export function SavedPlanPicker({ analysisId, separate = false, disabled = false, onSelected }: {
  analysisId: number
  separate?: boolean
  disabled?: boolean
  /** Called once the server has accepted a different saved plan, so the page can drop its own older save messages. */
  onSelected?: () => void
}) {
  const { t } = useTranslation()
  const plan = useSelectedPlan(analysisId, separate, true)
  const id = useId()
  const Heading = separate ? 'h3' : 'h2'
  if (plan.kind === 'loading') return <p className="form-hint" role="status">{t('common.loading')}</p>
  if (plan.kind === 'error') return <div className="alert alert-error" role="alert">{t('results.plan_error')}</div>

  const options = eligibleSavedPlans(plan)
  const selected = plan.kind === 'shared'
    ? { id: Number(plan.scenario.id), name: plan.scenario.name, usable: plan.usable, reason: plan.scenario.evidence_reasons?.[0]?.detail }
    : plan.kind === 'separate'
      ? { id: plan.plan.scenario_id, name: plan.plan.name, usable: plan.usable, reason: plan.plan.valid_reason }
      : null
  if (options.length === 0 && selected === null) return null

  return (
    <section className={separate ? 'supervisor-save' : 'card'} aria-labelledby={id}>
      <Heading lang="en" id={id} className="section-title">{headingText(t, 'results.choose_saved_plan')}</Heading>
      {options.length > 0 && (
        <Switcher key={analysisId} options={options} selectedId={selected?.id ?? null} analysisId={analysisId} disabled={disabled} onSelected={onSelected} />
      )}
      {selected && (selected.usable ? (
        <p role="status" className="form-hint">{t('compare.selected_for_simulation', { name: selected.name })}</p>
      ) : (
        <div className="alert alert-warn" role="status">
          {t('results.plan_not_current', { name: selected.name })}
          {selected.reason && <p className="form-hint">{selected.reason}</p>}
        </div>
      ))}
    </section>
  )
}

function Switcher({ options, selectedId, analysisId, disabled, onSelected }: {
  options: { id: number; name: string }[]
  selectedId: number | null
  analysisId: number
  disabled: boolean
  onSelected?: () => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const id = useId()
  const field = useRef<HTMLSelectElement>(null)
  const fallback = options.some((option) => option.id === selectedId) ? String(selectedId) : ''
  const [draft, setDraft] = useState<{ selectedId: number | null; value: string }>()
  const eligibleDraft = draft && draft.selectedId === selectedId && options.some((option) => String(option.id) === draft.value)
    ? draft
    : undefined
  if (draft && !eligibleDraft) setDraft(undefined)
  const choice = eligibleDraft?.value ?? fallback
  const select = useMutation({
    mutationKey: ['select-saved-plan', analysisId],
    mutationFn: (scenarioId: number) => selectWorkflowScenario(analysisId, scenarioId),
    onSuccess: async () => {
      onSelected?.()
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] }),
        queryClient.invalidateQueries({ queryKey: ['separate-comparison', analysisId] }),
      ])
    },
    onSettled: () => {
      requestAnimationFrame(() => {
        if (document.activeElement === document.body) field.current?.focus()
      })
    },
  })
  return (
    <div className="plan-switcher">
      <div className="form-field">
        <label htmlFor={id}>{t('results.plan_label')}</label>
        <select id={id} ref={field} value={choice} disabled={disabled || select.isPending} onChange={(event) => {
          select.reset()
          setDraft({ selectedId, value: event.target.value })
        }}>
          {!fallback && <option value="" disabled>{t('results.choose_saved_plan')}</option>}
          {options.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
        </select>
      </div>
      {choice !== '' && Number(choice) !== selectedId && (
        <button type="button" className="btn-primary" disabled={disabled || select.isPending} onClick={() => select.mutate(Number(choice))}>
          {select.isPending ? t('common.loading') : t('results.use_for_simulation')}
        </button>
      )}
      {select.isError && <div role="alert" className="alert alert-error">{messageOf(select.error, t('errors.server'))}</div>}
    </div>
  )
}
