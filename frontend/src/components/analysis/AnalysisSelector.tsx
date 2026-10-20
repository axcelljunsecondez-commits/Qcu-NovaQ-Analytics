import { useId } from 'react'

/** Presentation only: callers own inclusion rules, defaults, state and navigation. */
export function AnalysisSelector({ id, label, value, options, onChange }: {
  id: string
  label: string
  value: string
  options: { id: number; name: string }[]
  onChange: (value: string) => void
}) {
  const contextId = useId()
  const selected = options.find((option) => String(option.id) === value)
  return (
    <div className="form-field analysis-selector">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} aria-describedby={selected ? contextId : undefined} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
      </select>
      {selected && <p className="analysis-selector-context" id={contextId}>{selected.name}</p>}
    </div>
  )
}
