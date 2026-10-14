import { useEffect, useState, type ReactNode } from 'react'

interface TooltipProps {
  label: string
  // When false the wrapped control already shows its label, so no tooltip is needed.
  enabled?: boolean
  children: ReactNode
}

// Shows a visible name on hover and on keyboard focus (WCAG 1.4.13): it stays
// while the pointer is over the trigger or the tooltip, and Escape dismisses it.
// The wrapped control must carry its own accessible name; the tooltip only
// repeats it visually, so it is hidden from assistive technology.
export function Tooltip({ label, enabled = true, children }: TooltipProps) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    function dismiss(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', dismiss)
    return () => document.removeEventListener('keydown', dismiss)
  }, [open])

  return (
    <span
      className="tooltip-anchor"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {enabled && open && (
        <span className="tooltip" aria-hidden="true" data-testid="tooltip">
          {label}
        </span>
      )}
    </span>
  )
}
