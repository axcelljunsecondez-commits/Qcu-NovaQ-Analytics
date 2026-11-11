import { NumericValue } from './NumericValue'

export function MetricCard({
  label,
  value,
  sub,
  numeric = false,
}: {
  label: string
  value: string | number
  sub?: string
  numeric?: boolean
}) {
  return (
    <div className="metric-card" role="group" aria-label={label}>
      <div className="label">{label}</div>
      <div className="value">{numeric || typeof value === 'number' ? <NumericValue>{value}</NumericValue> : value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}
