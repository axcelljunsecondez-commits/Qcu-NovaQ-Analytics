/**
 * Shared formatting utilities for NovaQ frontend.
 */

/**
 * Format a number to fixed decimal places.
 * Returns '—' for null, undefined, or NaN values.
 */
export function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return value.toFixed(digits)
}

/**
 * Format a number as a percentage (0-1 → "XX%").
 * Returns '—' for null, undefined, or NaN values.
 */
export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return Math.round(value * 100) + '%'
}

/**
 * Format a confidence interval as "XX%–XX%".
 * Returns '—' for null, undefined, or NaN values.
 */
export function fmtFrCi(lower: number | null | undefined, upper: number | null | undefined): string {
  if (lower === null || upper === null || lower === undefined || upper === undefined || Number.isNaN(lower) || Number.isNaN(upper)) {
    return '—'
  }
  return `${Math.round(lower * 100)}%–${Math.round(upper * 100)}%`
}

/**
 * Download data as a CSV file.
 */
export function downloadCsv(filename: string, rows: Array<Record<string, unknown>>): void {
  if (rows.length === 0) return
  const header = Object.keys(rows[0])
  const lines = [
    header.join(','),
    ...rows.map((row) => header.map((h) => String(row[h] ?? '')).join(',')),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Extract error message from API error response.
 * Returns fallback message if detail is not available.
 */
export function messageOf(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
