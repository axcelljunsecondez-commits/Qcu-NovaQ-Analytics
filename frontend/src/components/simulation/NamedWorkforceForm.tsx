import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { DatasetOut } from '../../api/types'
import type { NamedContract } from '../../api/sharedNamed'
import {
  emptyPayField,
  type EmployeeForm,
  type NamedForm,
  type PayFieldForm,
} from '../../lib/namedWorkforce'

interface Props {
  form: NamedForm
  onChange: (form: NamedForm) => void
  contract: NamedContract
  datasets: DatasetOut[]
  disabled?: boolean
}

type PayKey = keyof EmployeeForm['pay']
const PAY_KEYS: PayKey[] = ['regular_rate_per_hour', 'overtime_rate_per_hour', 'daily_regular_paid_minutes']

function edit(form: NamedForm, change: (draft: NamedForm) => void): NamedForm {
  const draft = JSON.parse(JSON.stringify(form)) as NamedForm
  change(draft)
  return draft
}

function Field({ id, label, value, onChange, placeholder, disabled, hint }: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  hint?: string
}) {
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" value={value} placeholder={placeholder} disabled={disabled}
        onChange={(event) => onChange(event.target.value)} />
      {hint && <span className="form-hint">{hint}</span>}
    </div>
  )
}

function Section({ title, children, hint }: { title: string; children: ReactNode; hint?: string }) {
  return (
    <fieldset className="card" style={{ marginBottom: '12px' }}>
      <legend className="section-title">{title}</legend>
      {hint && <p className="form-hint">{hint}</p>}
      {children}
    </fieldset>
  )
}

/** The Named Shared Queue workforce form. Nothing is prefilled: every value comes from the user. */
export function NamedWorkforceForm({ form, onChange, contract, datasets, disabled = false }: Props) {
  const { t } = useTranslation()
  const set = (change: (draft: NamedForm) => void) => onChange(edit(form, change))
  const clock = t('simulation.named_clock_placeholder')
  const processed = datasets.filter((dataset) => dataset.validation?.ok === true)
  const maxShifts = Number(form.shift_rules.max_shifts_per_employee)
  const gapEnabled = Number.isInteger(maxShifts) && maxShifts > 1
  const employeeIds = form.employees.map((employee) => employee.employee_id).filter((id) => id.trim() !== '')

  return (
    <div data-testid="named-workforce-form">
      <Section title={t('simulation.named_dataset_title')} hint={t('simulation.named_dataset_help')}>
        <div className="form-field">
          <label htmlFor="named-dataset">{t('simulation.named_dataset_label')}</label>
          <select id="named-dataset" value={form.dataset_id} disabled={disabled}
            onChange={(event) => set((draft) => { draft.dataset_id = event.target.value })}>
            <option value="">{t('simulation.named_dataset_none')}</option>
            {processed.map((dataset) => (
              <option key={dataset.id} value={String(dataset.id)}>
                {t('simulation.named_dataset_option', { id: dataset.id, name: dataset.name })}
              </option>
            ))}
          </select>
        </div>
        {processed.length === 0 && <p role="status" className="form-hint">{t('simulation.named_dataset_empty')}</p>}
      </Section>

      <Section title={t('simulation.named_horizon_title')} hint={t('simulation.named_horizon_help')}>
        <div className="form-row">
          <Field id="named-horizon-start" label={t('simulation.named_opening')} value={form.horizon.start} placeholder={clock}
            disabled={disabled} onChange={(value) => set((draft) => { draft.horizon.start = value })} />
          <Field id="named-horizon-end" label={t('simulation.named_closing')} value={form.horizon.end} placeholder={clock}
            disabled={disabled} onChange={(value) => set((draft) => { draft.horizon.end = value })} />
        </div>
      </Section>

      <Section title={t('simulation.named_required_staffing_title')} hint={t('simulation.named_required_staffing_help')}>
        {form.required_staffing.map((segment, index) => (
          <div className="form-row" key={`segment-${index}`} data-testid="named-segment-row">
            <Field id={`named-seg-${index}-id`} label={t('simulation.named_segment_id')} value={segment.segment_id} disabled={disabled}
              onChange={(value) => set((draft) => { draft.required_staffing[index].segment_id = value })} />
            <Field id={`named-seg-${index}-start`} label={t('simulation.named_start')} value={segment.start} placeholder={clock} disabled={disabled}
              onChange={(value) => set((draft) => { draft.required_staffing[index].start = value })} />
            <Field id={`named-seg-${index}-end`} label={t('simulation.named_end')} value={segment.end} placeholder={clock} disabled={disabled}
              onChange={(value) => set((draft) => { draft.required_staffing[index].end = value })} />
            <Field id={`named-seg-${index}-servers`} label={t('simulation.named_servers')} value={segment.servers} disabled={disabled}
              onChange={(value) => set((draft) => { draft.required_staffing[index].servers = value })} />
            <button type="button" className="btn-ghost" disabled={disabled}
              onClick={() => set((draft) => { draft.required_staffing.splice(index, 1) })}>
              {t('simulation.named_remove')}
            </button>
          </div>
        ))}
        <button type="button" className="btn-ghost" disabled={disabled}
          onClick={() => set((draft) => { draft.required_staffing.push({ segment_id: '', start: '', end: '', servers: '' }) })}>
          {t('simulation.named_add_segment')}
        </button>
      </Section>

      <Section title={t('simulation.named_registers_title')}>
        <Field id="named-registers" label={t('simulation.named_register_count')} value={form.register_count} disabled={disabled}
          onChange={(value) => set((draft) => { draft.register_count = value })} />
      </Section>

      <Section title={t('simulation.named_shift_rules_title')}>
        <div className="form-row">
          <Field id="named-sr-earliest" label={t('simulation.named_sr_earliest_start')} value={form.shift_rules.earliest_start}
            placeholder={clock} disabled={disabled} onChange={(value) => set((draft) => { draft.shift_rules.earliest_start = value })} />
          <Field id="named-sr-latest" label={t('simulation.named_sr_latest_end')} value={form.shift_rules.latest_end}
            placeholder={clock} disabled={disabled} onChange={(value) => set((draft) => { draft.shift_rules.latest_end = value })} />
          <Field id="named-sr-min" label={t('simulation.named_sr_min_shift')} value={form.shift_rules.min_shift_minutes}
            disabled={disabled} onChange={(value) => set((draft) => { draft.shift_rules.min_shift_minutes = value })} />
          <Field id="named-sr-max" label={t('simulation.named_sr_max_shift')} value={form.shift_rules.max_shift_minutes}
            disabled={disabled} onChange={(value) => set((draft) => { draft.shift_rules.max_shift_minutes = value })} />
          <Field id="named-sr-granularity" label={t('simulation.named_sr_granularity')} value={form.shift_rules.boundary_granularity_minutes}
            disabled={disabled} onChange={(value) => set((draft) => { draft.shift_rules.boundary_granularity_minutes = value })} />
          <Field id="named-sr-max-shifts" label={t('simulation.named_sr_max_shifts')} value={form.shift_rules.max_shifts_per_employee}
            disabled={disabled} onChange={(value) => set((draft) => { draft.shift_rules.max_shifts_per_employee = value })} />
          <Field id="named-sr-gap" label={t('simulation.named_sr_min_between')} value={gapEnabled ? form.shift_rules.min_minutes_between_shifts : ''}
            disabled={disabled || !gapEnabled} hint={gapEnabled ? undefined : t('simulation.named_sr_min_between_hint')}
            onChange={(value) => set((draft) => { draft.shift_rules.min_minutes_between_shifts = value })} />
        </div>
      </Section>

      <Section title={t('simulation.named_break_rules_title')} hint={t('simulation.named_break_rules_help')}>
        {form.break_rules.map((rule, index) => (
          <div key={`rule-${index}`} className="card" data-testid="named-break-rule" style={{ marginBottom: '8px' }}>
            <div className="form-row">
              <Field id={`named-br-${index}-min`} label={t('simulation.named_br_min_shift')} value={rule.min_shift_minutes} disabled={disabled}
                onChange={(value) => set((draft) => { draft.break_rules[index].min_shift_minutes = value })} />
              <Field id={`named-br-${index}-max`} label={t('simulation.named_br_max_shift')} value={rule.max_shift_minutes} disabled={disabled}
                onChange={(value) => set((draft) => { draft.break_rules[index].max_shift_minutes = value })} />
              <Field id={`named-br-${index}-gap`} label={t('simulation.named_br_min_gap')} value={rule.min_gap_minutes} disabled={disabled}
                onChange={(value) => set((draft) => { draft.break_rules[index].min_gap_minutes = value })} />
              <button type="button" className="btn-ghost" disabled={disabled}
                onClick={() => set((draft) => { draft.break_rules.splice(index, 1) })}>{t('simulation.named_remove')}</button>
            </div>
            {rule.breaks.map((item, position) => (
              <div className="form-row" key={`rule-${index}-break-${position}`}>
                <Field id={`named-br-${index}-b-${position}-name`} label={t('simulation.named_break_name')} value={item.name} disabled={disabled}
                  onChange={(value) => set((draft) => { draft.break_rules[index].breaks[position].name = value })} />
                <Field id={`named-br-${index}-b-${position}-minutes`} label={t('simulation.named_break_minutes')} value={item.duration_minutes}
                  disabled={disabled} onChange={(value) => set((draft) => { draft.break_rules[index].breaks[position].duration_minutes = value })} />
                <label className="form-field" htmlFor={`named-br-${index}-b-${position}-paid`}>
                  <span>{t('simulation.named_break_paid')}</span>
                  <input id={`named-br-${index}-b-${position}-paid`} type="checkbox" checked={item.paid} disabled={disabled}
                    onChange={(event) => set((draft) => { draft.break_rules[index].breaks[position].paid = event.target.checked })} />
                </label>
                <Field id={`named-br-${index}-b-${position}-earliest`} label={t('simulation.named_break_earliest_offset')}
                  value={item.earliest_start_offset_minutes} disabled={disabled}
                  onChange={(value) => set((draft) => { draft.break_rules[index].breaks[position].earliest_start_offset_minutes = value })} />
                <Field id={`named-br-${index}-b-${position}-latest`} label={t('simulation.named_break_latest_offset')}
                  value={item.latest_start_offset_minutes} disabled={disabled}
                  onChange={(value) => set((draft) => { draft.break_rules[index].breaks[position].latest_start_offset_minutes = value })} />
                <button type="button" className="btn-ghost" disabled={disabled}
                  onClick={() => set((draft) => { draft.break_rules[index].breaks.splice(position, 1) })}>{t('simulation.named_remove')}</button>
              </div>
            ))}
            <button type="button" className="btn-ghost" disabled={disabled}
              onClick={() => set((draft) => {
                draft.break_rules[index].breaks.push({
                  name: '', duration_minutes: '', paid: false, earliest_start_offset_minutes: '', latest_start_offset_minutes: '',
                })
              })}>
              {t('simulation.named_add_break_requirement')}
            </button>
          </div>
        ))}
        <button type="button" className="btn-ghost" disabled={disabled}
          onClick={() => set((draft) => { draft.break_rules.push({ min_shift_minutes: '', max_shift_minutes: '', min_gap_minutes: '', breaks: [] }) })}>
          {t('simulation.named_add_break_rule')}
        </button>
      </Section>

      <Section title={t('simulation.named_employees_title')} hint={t('simulation.named_employees_help')}>
        {form.employees.map((employee, index) => (
          <div key={`employee-${index}`} className="card" data-testid="named-employee" style={{ marginBottom: '8px' }}>
            <div className="form-row">
              <Field id={`named-emp-${index}-id`} label={t('simulation.named_employee_id')} value={employee.employee_id}
                hint={t('simulation.named_employee_id_hint')} disabled={disabled}
                onChange={(value) => set((draft) => { draft.employees[index].employee_id = value })} />
              <button type="button" className="btn-ghost" disabled={disabled}
                onClick={() => set((draft) => { draft.employees.splice(index, 1) })}>{t('simulation.named_remove')}</button>
            </div>
            {employee.availability.map((window, position) => (
              <div className="form-row" key={`employee-${index}-window-${position}`}>
                <Field id={`named-emp-${index}-av-${position}-start`} label={t('simulation.named_available_from')} value={window.start}
                  placeholder={clock} disabled={disabled}
                  onChange={(value) => set((draft) => { draft.employees[index].availability[position].start = value })} />
                <Field id={`named-emp-${index}-av-${position}-end`} label={t('simulation.named_available_to')} value={window.end}
                  placeholder={clock} disabled={disabled}
                  onChange={(value) => set((draft) => { draft.employees[index].availability[position].end = value })} />
                <button type="button" className="btn-ghost" disabled={disabled}
                  onClick={() => set((draft) => { draft.employees[index].availability.splice(position, 1) })}>{t('simulation.named_remove')}</button>
              </div>
            ))}
            <button type="button" className="btn-ghost" disabled={disabled}
              onClick={() => set((draft) => { draft.employees[index].availability.push({ start: '', end: '' }) })}>
              {t('simulation.named_add_availability')}
            </button>
            <div className="form-row">
              {PAY_KEYS.map((key) => (
                <PayInput key={key} id={`named-emp-${index}-${key}`} label={t(`simulation.named_pay_${key}`)}
                  field={employee.pay[key]} disabled={disabled}
                  onChange={(field) => set((draft) => { draft.employees[index].pay[key] = field })} />
              ))}
            </div>
          </div>
        ))}
        <button type="button" className="btn-ghost" disabled={disabled}
          onClick={() => set((draft) => {
            draft.employees.push({
              employee_id: '',
              availability: [],
              pay: {
                regular_rate_per_hour: emptyPayField(),
                overtime_rate_per_hour: emptyPayField(),
                daily_regular_paid_minutes: emptyPayField(),
              },
            })
          })}>
          {t('simulation.named_add_employee')}
        </button>
      </Section>

      <Section title={t('simulation.named_roster_title')} hint={t('simulation.named_roster_help')}>
        {form.roster.map((shift, index) => (
          <div key={`shift-${index}`} className="card" data-testid="named-roster-shift" style={{ marginBottom: '8px' }}>
            <div className="form-row">
              <div className="form-field">
                <label htmlFor={`named-roster-${index}-employee`}>{t('simulation.named_roster_employee')}</label>
                <select id={`named-roster-${index}-employee`} value={shift.employee_id} disabled={disabled}
                  onChange={(event) => set((draft) => { draft.roster[index].employee_id = event.target.value })}>
                  <option value="">{t('simulation.named_roster_employee_none')}</option>
                  {[...new Set([...employeeIds, ...(shift.employee_id ? [shift.employee_id] : [])])].map((id) => (
                    <option key={id} value={id}>{id}</option>
                  ))}
                </select>
              </div>
              <Field id={`named-roster-${index}-start`} label={t('simulation.named_start')} value={shift.start} placeholder={clock}
                disabled={disabled} onChange={(value) => set((draft) => { draft.roster[index].start = value })} />
              <Field id={`named-roster-${index}-end`} label={t('simulation.named_end')} value={shift.end} placeholder={clock}
                disabled={disabled} onChange={(value) => set((draft) => { draft.roster[index].end = value })} />
              <button type="button" className="btn-ghost" disabled={disabled}
                onClick={() => set((draft) => { draft.roster.splice(index, 1) })}>{t('simulation.named_remove')}</button>
            </div>
            {shift.breaks.map((item, position) => (
              <div className="form-row" key={`shift-${index}-break-${position}`}>
                <Field id={`named-roster-${index}-b-${position}-name`} label={t('simulation.named_break_name')} value={item.name}
                  disabled={disabled} onChange={(value) => set((draft) => { draft.roster[index].breaks[position].name = value })} />
                <Field id={`named-roster-${index}-b-${position}-start`} label={t('simulation.named_break_start')} value={item.start}
                  placeholder={clock} disabled={disabled}
                  onChange={(value) => set((draft) => { draft.roster[index].breaks[position].start = value })} />
                <button type="button" className="btn-ghost" disabled={disabled}
                  onClick={() => set((draft) => { draft.roster[index].breaks.splice(position, 1) })}>{t('simulation.named_remove')}</button>
              </div>
            ))}
            <button type="button" className="btn-ghost" disabled={disabled}
              onClick={() => set((draft) => { draft.roster[index].breaks.push({ name: '', start: '' }) })}>
              {t('simulation.named_add_placed_break')}
            </button>
          </div>
        ))}
        <button type="button" className="btn-ghost" disabled={disabled}
          onClick={() => set((draft) => { draft.roster.push({ employee_id: '', start: '', end: '', breaks: [] }) })}>
          {t('simulation.named_add_shift')}
        </button>
      </Section>

      <Section title={t('simulation.named_closing_policy_title')}>
        <div role="radiogroup" aria-label={t('simulation.named_closing_policy_title')}>
          {contract.closing_policies.map((policy) => (
            <label key={policy} className="form-field" style={{ flexDirection: 'row', alignItems: 'flex-start', gap: '6px' }}>
              <input type="radio" name="named-closing-policy" value={policy} checked={form.closing_policy === policy}
                disabled={disabled} onChange={() => set((draft) => { draft.closing_policy = policy })} />
              <span>
                <strong>{policy}</strong> — {t(`simulation.named_closing_${policy.toLowerCase()}`, { defaultValue: '' })}
              </span>
            </label>
          ))}
        </div>
      </Section>

      <Section title={t('simulation.named_employee_policy_title')} hint={t('simulation.named_employee_policy_help')}>
        <dl data-testid="named-employee-policy">
          {Object.entries(contract.employee_policy).map(([name, item]) => (
            <div key={name} style={{ marginBottom: '6px' }}>
              <dt><code>{name}</code>: <code>{item.approved}</code></dt>
              <dd className="form-hint">{item.meaning}</dd>
            </div>
          ))}
        </dl>
      </Section>
    </div>
  )
}

function PayInput({ id, label, field, onChange, disabled }: {
  id: string
  label: string
  field: PayFieldForm
  onChange: (field: PayFieldForm) => void
  disabled?: boolean
}) {
  const { t } = useTranslation()
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" value={field.not_supplied ? '' : field.value} disabled={disabled || field.not_supplied}
        placeholder={field.not_supplied ? t('simulation.named_pay_not_supplied') : undefined}
        onChange={(event) => onChange({ ...field, value: event.target.value })} />
      <label htmlFor={`${id}-missing`} className="form-hint">
        <input id={`${id}-missing`} type="checkbox" checked={field.not_supplied} disabled={disabled}
          onChange={(event) => onChange({ value: field.value, not_supplied: event.target.checked })} />{' '}
        {t('simulation.named_pay_not_supplied')}
      </label>
    </div>
  )
}
