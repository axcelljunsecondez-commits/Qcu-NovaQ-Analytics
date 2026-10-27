import { useEffect, useId, useRef } from 'react'

interface ConfirmDialogProps {
  title: string
  message: string
  confirmLabel: string
  cancelLabel: string
  onConfirm: () => void
  onCancel: () => void
}

// Accessible confirmation (spec §10): modal dialog, focus moves to Cancel,
// Tab stays inside, Escape cancels, and the caller returns focus to its trigger.
export function ConfirmDialog({ title, message, confirmLabel, cancelLabel, onConfirm, onCancel }: ConfirmDialogProps) {
  const titleId = useId()
  const messageId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    cancelRef.current?.focus()
  }, [])

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onCancel()
      return
    }
    if (event.key !== 'Tab') return
    const buttons = Array.from(dialogRef.current?.querySelectorAll<HTMLButtonElement>('button') ?? [])
    const first = buttons[0]
    const last = buttons[buttons.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first?.focus()
    }
  }

  return (
    <div className="dialog-backdrop">
      <div
        ref={dialogRef}
        className="card confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        onKeyDown={onKeyDown}
      >
        <h2 lang="en" id={titleId} className="card-title">{title}</h2>
        <p id={messageId}>{message}</p>
        <div className="form-row">
          <button ref={cancelRef} type="button" className="btn-ghost" onClick={onCancel}>{cancelLabel}</button>
          <button type="button" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
