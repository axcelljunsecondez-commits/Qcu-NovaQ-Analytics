import type { ReactNode } from 'react'

// Use only at explicitly numeric display fields. These are existing glyph runs, not parsed numbers.
const NUMBER_RUN = /[-+\u2212]?(?:\d+(?:[\d.,\u00a0\u202f]*\d)?(?:[eE][-+]?\d+)?)/gu

export function NumericValue({ children }: { children: string | number }) {
  const text = String(children)
  const parts: ReactNode[] = []
  let cursor = 0
  for (const match of text.matchAll(NUMBER_RUN)) {
    const start = match.index
    if (start > cursor) parts.push(text.slice(cursor, start))
    parts.push(<span className="numeric-value" key={start}>{match[0]}</span>)
    cursor = start + match[0].length
  }
  if (parts.length === 0) return <>{children}</>
  if (cursor < text.length) parts.push(text.slice(cursor))
  return <>{parts}</>
}
