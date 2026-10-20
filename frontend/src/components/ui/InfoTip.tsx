import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * An ⓘ explanation (spec 2026-10-09 §7.12, D9): a button that opens on click, pointer hover and keyboard
 * focus, closes on Escape, and describes itself with the text while open. Unlike ``Tooltip`` the text is
 * real content, so it is exposed to assistive technology.
 */
export function InfoTip({ name, text, stableInteraction = false }: { name: string; text: string; stableInteraction?: boolean }) {
  const { t } = useTranslation()
  const id = useId()
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const root = useRef<HTMLSpanElement>(null)
  const popup = useRef<HTMLSpanElement>(null)
  const focused = useRef(false)
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  function cancelLeave() {
    if (leaveTimer.current !== null) clearTimeout(leaveTimer.current)
    leaveTimer.current = null
  }
  useEffect(() => () => cancelLeave(), [])

  useLayoutEffect(() => {
    if (!stableInteraction || !open) return
    function position() {
      const anchor = root.current?.querySelector('button')?.getBoundingClientRect()
      const tooltip = popup.current
      if (!anchor || !tooltip) return
      const bounds = tooltip.getBoundingClientRect()
      tooltip.style.left = `${Math.max(16, Math.min(anchor.left, window.innerWidth - bounds.width - 16))}px`
      const below = anchor.bottom + bounds.height <= window.innerHeight - 16
      tooltip.style.top = `${below ? anchor.bottom : Math.max(16, anchor.top - bounds.height)}px`
    }
    position()
    window.addEventListener('resize', position)
    window.addEventListener('scroll', position, true)
    return () => {
      window.removeEventListener('resize', position)
      window.removeEventListener('scroll', position, true)
    }
  }, [open, stableInteraction, text])

  useEffect(() => {
    if (!open) return
    function dismiss(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        setPinned(false)
      }
    }
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) {
        setOpen(false)
        setPinned(false)
      }
    }
    document.addEventListener('keydown', dismiss)
    if (stableInteraction) document.addEventListener('pointerdown', outside)
    return () => {
      document.removeEventListener('keydown', dismiss)
      document.removeEventListener('pointerdown', outside)
    }
  }, [open, stableInteraction])

  return (
    <span ref={root} className={`info-tip${stableInteraction ? ' info-tip-stable' : ''}`} onMouseEnter={() => { cancelLeave(); setOpen(true) }} onMouseLeave={(event) => {
      if (!stableInteraction) setOpen(false)
      else if (event.relatedTarget instanceof Node && root.current?.contains(event.relatedTarget)) return
      else if (!pinned && !focused.current) leaveTimer.current = setTimeout(() => setOpen(false), 120)
    }}>
      <button type="button" className="info-tip-button" aria-label={t('calculator.about', { name })}
        aria-expanded={open} aria-describedby={open ? id : undefined}
        onClick={() => {
          cancelLeave()
          if (stableInteraction) {
            setOpen(!pinned)
            setPinned(!pinned)
          } else setOpen((value) => !value)
        }} onFocus={() => { cancelLeave(); focused.current = true; setOpen(true) }} onBlur={() => {
          focused.current = false
          setOpen(false)
          setPinned(false)
        }}>
        ⓘ
      </button>
      {open && <span ref={popup} id={id} role="tooltip" className="info-tip-text">{text}</span>}
    </span>
  )
}
