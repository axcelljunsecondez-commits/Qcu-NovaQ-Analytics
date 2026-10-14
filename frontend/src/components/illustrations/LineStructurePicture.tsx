import { useTranslation } from 'react-i18next'

// Static pictures of the two queue structures (spec §7.1, D5, D8). They are
// drawings only: no counts, waits or other results appear in them.

function Person({ x, y }: { x: number; y: number }) {
  return (
    <g className="lsp-person" transform={`translate(${x} ${y})`}>
      <circle cx="8" cy="5" r="5" />
      <path d="M1 26v-8a7 7 0 0 1 14 0v8Z" />
    </g>
  )
}

function Counter({ y, label, state, free = false }: { y: number; label: string; state?: string; free?: boolean }) {
  return (
    <g>
      <rect className={`lsp-desk${free ? ' is-free' : ''}`} x="228" y={y} width="66" height="32" rx="6" />
      <text className="lsp-label" x="236" y={y + 14}>{label}</text>
      {state && <text className={`lsp-state${free ? ' is-free' : ''}`} x="236" y={y + 27}>{state}</text>}
    </g>
  )
}

export function LineStructurePicture({ variant }: { variant: 'shared' | 'separate' }) {
  const { t } = useTranslation()
  const counter = (index: number) => t('home.picture_counter', { number: index })
  const rows = [12, 59, 106]

  if (variant === 'shared') {
    return (
      <svg className="line-structure-picture" viewBox="0 0 300 140" role="img" aria-label={t('home.picture_shared_label')}>
        <rect className="lsp-lane" x="6" y="58" width="168" height="34" rx="17" />
        {[18, 44, 70, 96, 122, 148].map((x) => <Person key={x} x={x} y={62} />)}
        <text className="lsp-note" x="146" y="52">{t('home.picture_next')}</text>
        <path className="lsp-flow" d="M176 75 C200 75 205 28 224 28" />
        <path className="lsp-flow is-go" d="M176 75 H224" />
        <path className="lsp-flow" d="M176 75 C200 75 205 122 224 122" />
        <Counter y={rows[0]} label={counter(1)} state={t('home.picture_busy')} />
        <Counter y={rows[1]} label={counter(2)} state={t('home.picture_free')} free />
        <Counter y={rows[2]} label={counter(3)} state={t('home.picture_busy')} />
      </svg>
    )
  }

  const people = [[140, 166, 192], [192], [114, 140, 166, 192]]
  return (
    <svg className="line-structure-picture" viewBox="0 0 300 140" role="img" aria-label={t('home.picture_separate_label')}>
      {rows.map((y, row) => (
        <g key={y}>
          <rect className="lsp-lane" x="6" y={y} width="210" height="32" rx="16" />
          {people[row].map((x) => <Person key={x} x={x} y={y + 3} />)}
          <path className="lsp-flow" d={`M216 ${y + 16} H224`} />
          <Counter y={y} label={counter(row + 1)} />
        </g>
      ))}
    </svg>
  )
}
