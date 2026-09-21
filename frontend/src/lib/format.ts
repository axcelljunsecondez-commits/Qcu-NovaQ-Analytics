/**
 * Shared formatting utilities for NovaQ frontend.
 */

/**
 * Format a number to fixed decimal places.
 * Returns '—' for null, undefined, or NaN values.
 */
export function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—'
  }
  return value.toFixed(digits)
}

/**
 * Value rounded to `digits` decimal places. Trailing zeros are dropped only
 * when the shorter number is exact (allowing float noise), so a zero on screen
 * always means rounding happened: 2.4285714 → "2.4286", 2.5 → "2.5", 3 → "3",
 * but 2.99996 → "3.0000" and 89.510002 → "89.5100". A rounded value therefore
 * never looks like it sits exactly on a threshold or target. Display only.
 * Returns '—' for null, undefined, or NaN values.
 */
export function fmtDecimal(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—'
  }
  const fixed = value.toFixed(digits)
  // A tiny negative such as -0.00001 would otherwise show as "-0.0000".
  const rounded = Number(fixed) === 0 ? (0).toFixed(digits) : fixed
  const short = rounded.includes('.') ? rounded.replace(/\.?0+$/, '') : rounded
  // Tolerance absorbs float noise such as 0.29 * 100 = 28.999999999999996.
  const exact = Math.abs(Number(short) - value) <= 1e-9 * Math.max(1, Math.abs(value))
  return exact ? short : rounded
}

/**
 * A 0-1 ratio as a percentage with the fmtDecimal rule
 * (0.7142857 → "71.4286%", 0.8951 → "89.51%", 0.5 → "50%").
 * Returns '—' for null, undefined, or NaN values.
 */
export function fmtPctDecimal(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—'
  }
  return `${fmtDecimal(value * 100, digits)}%`
}

/**
 * Format a number as a percentage (0-1 → "XX%").
 * Returns '—' for null, undefined, or NaN values.
 */
export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '—'
  }
  return Math.round(value * 100) + '%'
}

/**
 * Format a confidence interval as "XX%–XX%".
 * Returns '—' for null, undefined, or NaN values.
 */
export function fmtFrCi(lower: number | null | undefined, upper: number | null | undefined): string {
  if (lower === null || upper === null || lower === undefined || upper === undefined || !Number.isFinite(lower) || !Number.isFinite(upper)) {
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
