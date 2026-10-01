import { useTranslation } from 'react-i18next'
import type { AttributionClosing, NamedAttribution } from '../../api/sharedNamed'
import { fmtDecimal } from '../../lib/format'

interface Props {
  attribution: NamedAttribution
}

const STATES = ['WAITING_FOR_REGISTER', 'AVAILABLE', 'SERVING', 'SERVING_BREAK_DUE', 'SERVING_SHIFT_ENDED', 'ON_BREAK']

function ClosingCells({ closing }: { closing: AttributionClosing }) {
  return (
    <>
      <td>{fmtDecimal(closing.after_closing_hours)}</td>
      <td>{fmtDecimal(closing.past_scheduled_end_hours)}</td>
      <td>{fmtDecimal(closing.after_closing_and_past_scheduled_end_hours)}</td>
      <td>{fmtDecimal(closing.neither_hours)}</td>
    </>
  )
}

/** Operational simulation attribution of one replication, per shift and per employee, in hours. */
export function NamedAttributionTables({ attribution }: Props) {
  const { t } = useTranslation()
  const closingHeaders = (
    <>
      <th scope="col">{t('simulation.named_attr_after_closing')}</th>
      <th scope="col">{t('simulation.named_attr_past_end')}</th>
      <th scope="col">{t('simulation.named_attr_both')}</th>
      <th scope="col">{t('simulation.named_attr_neither')}</th>
    </>
  )
  const stateHeaders = STATES.map((state) => <th scope="col" key={state}><code>{state}</code></th>)
  return (
    <section className="card" data-testid="named-attribution" aria-label={t('simulation.named_attribution_title')}>
      <h3 className="section-title">{t('simulation.named_attribution_title')}</h3>
      <p role="note" className="alert alert-warn">{t('simulation.named_attribution_note')}</p>
      <p className="form-hint">{t('simulation.named_attribution_units')}</p>

      <div className="table-scroll" role="region" aria-label={t('simulation.named_attr_shifts_caption')} tabIndex={0}>
        <table>
          <caption>{t('simulation.named_attr_shifts_caption')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('simulation.named_col_employee')}</th>
              <th scope="col">{t('simulation.named_attr_shift')}</th>
              <th scope="col">{t('simulation.named_attr_activated')}</th>
              <th scope="col">{t('simulation.named_attr_scheduled')}</th>
              <th scope="col">{t('simulation.named_attr_on_duty')}</th>
              <th scope="col">{t('simulation.named_attr_activation_delay')}</th>
              <th scope="col">{t('simulation.named_attr_overrun')}</th>
              <th scope="col">{t('simulation.named_attr_register_wait')}</th>
              {stateHeaders}
              {closingHeaders}
            </tr>
          </thead>
          <tbody>
            {attribution.shifts.map((shift) => (
              <tr key={`${shift.employee_id}-${shift.shift_index}`} data-testid="named-attr-shift-row">
                <th scope="row">{shift.employee_id}</th>
                <td>{shift.shift_index}</td>
                <td>{shift.activated ? t('simulation.named_yes') : `${t('simulation.named_no')}${shift.not_activated_reason ? ` (${shift.not_activated_reason})` : ''}`}</td>
                <td>{fmtDecimal(shift.scheduled_duration_hours)}</td>
                <td>{fmtDecimal(shift.on_duty_hours)}</td>
                <td>{fmtDecimal(shift.activation_delay_hours)}</td>
                <td>{fmtDecimal(shift.overrun_hours)}</td>
                <td>{fmtDecimal(shift.register_wait_hours)}</td>
                {STATES.map((state) => <td key={state}>{fmtDecimal(shift.hours_by_state[state])}</td>)}
                <ClosingCells closing={shift.closing_attribution} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-scroll" role="region" aria-label={t('simulation.named_attr_employees_caption')} tabIndex={0}>
        <table>
          <caption>{t('simulation.named_attr_employees_caption')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('simulation.named_col_employee')}</th>
              <th scope="col">{t('simulation.named_attr_shifts')}</th>
              <th scope="col">{t('simulation.named_attr_activated_shifts')}</th>
              <th scope="col">{t('simulation.named_attr_on_duty')}</th>
              <th scope="col">{t('simulation.named_attr_activation_delay')}</th>
              <th scope="col">{t('simulation.named_attr_overrun')}</th>
              <th scope="col">{t('simulation.named_attr_register_wait')}</th>
              {stateHeaders}
              {closingHeaders}
            </tr>
          </thead>
          <tbody>
            {attribution.employees.map((employee) => (
              <tr key={employee.employee_id} data-testid="named-attr-employee-row">
                <th scope="row">{employee.employee_id}</th>
                <td>{employee.shift_count}</td>
                <td>{employee.activated_shift_count}</td>
                <td>{fmtDecimal(employee.on_duty_hours)}</td>
                <td>{fmtDecimal(employee.activation_delay_hours)}</td>
                <td>{fmtDecimal(employee.overrun_hours)}</td>
                <td>{fmtDecimal(employee.register_wait_hours)}</td>
                {STATES.map((state) => <td key={state}>{fmtDecimal(employee.hours_by_state[state])}</td>)}
                <ClosingCells closing={employee.closing_attribution} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {attribution.undetermined.length > 0 && (
        <details>
          <summary>{t('simulation.named_attr_undetermined')}</summary>
          <ul>{attribution.undetermined.map((item, index) => <li key={`u-${index}`}>{item}</li>)}</ul>
        </details>
      )}
      <details>
        <summary>{t('simulation.named_attr_definitions')}</summary>
        <dl>
          {Object.entries(attribution.definitions).map(([key, text]) => (
            <div key={key}><dt><code>{key}</code></dt><dd className="form-hint">{text}</dd></div>
          ))}
        </dl>
      </details>
    </section>
  )
}
