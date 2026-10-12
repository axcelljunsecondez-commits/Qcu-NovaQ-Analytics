import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * An ⓘ explanation (spec 2026-10-09 §7.12, D9): a button that opens on click, pointer hover and keyboard
 * focus, closes on Escape, and describes itself with the text while open. Unlike ``Tooltip`` the text is
 * real content, so it is exposed to assistive technology.
 */
export function InfoTip({ name, text }: { name: string; text: string }) {
  const { t } = useTranslation()
  const id = useId()
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
    <span className="info-tip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="info-tip-button" aria-label={t('calculator.about', { name })}
        aria-expanded={open} aria-describedby={open ? id : undefined}
        onClick={() => setOpen((value) => !value)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
        ⓘ
      </button>
      {open && <span id={id} role="tooltip" className="info-tip-text">{text}</span>}
    </span>
  )
}
