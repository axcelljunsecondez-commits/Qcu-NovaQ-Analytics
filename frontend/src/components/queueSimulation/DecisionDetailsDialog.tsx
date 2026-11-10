import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { headingText } from '../../lib/headingText'

/** Opens already saved check details; owns no request or result derivation. */
export function DecisionDetailsDialog({ label, disabled, children }: { label: string; disabled: boolean; children: ReactNode }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const close = useRef<HTMLButtonElement>(null)
  const wasOpen = useRef(false)
  const titleId = useId()

  useEffect(() => {
    const node = dialog.current
    if (!node) return
    if (open && !disabled) {
      if (!node.open) node.showModal()
      close.current?.focus()
      wasOpen.current = true
    } else {
      if (disabled && open) setOpen(false)
      if (node.open) node.close()
      if (wasOpen.current) trigger.current?.focus()
      wasOpen.current = false
    }
  }, [open, disabled])

  useEffect(() => {
    const node = dialog.current
    return () => { if (node?.open) node.close() }
  }, [])

  return <>
    <button ref={trigger} type="button" className="btn-primary" aria-haspopup="dialog" disabled={disabled}
      onClick={() => setOpen(true)}>{label}</button>
    <dialog ref={dialog} className="decision-details-dialog" aria-labelledby={titleId} aria-modal="true"
      onCancel={(event) => { event.preventDefault(); setOpen(false) }} onClose={() => setOpen(false)}>
      {open && !disabled && <>
        <header className="decision-details-dialog-heading">
          <h2 lang="en" id={titleId} className="section-title">{headingText(t, 'decision.plain.details')}</h2>
          <button ref={close} type="button" className="btn-ghost" onClick={() => setOpen(false)}>{t('tutorials.close')}</button>
        </header>
        <div className="decision-details-dialog-body">{children}</div>
      </>}
    </dialog>
  </>
}
