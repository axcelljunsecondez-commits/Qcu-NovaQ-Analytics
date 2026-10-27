import { headingText } from '../../lib/headingText'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

export function CollectionChecklist() {
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
    if (open) {
      if (!node.open) node.showModal()
      close.current?.focus()
      wasOpen.current = true
    } else {
      if (node.open) node.close()
      if (wasOpen.current) trigger.current?.focus()
      wasOpen.current = false
    }
  }, [open])
  return <>
    <button ref={trigger} type="button" className="queueing-checklist-trigger" onClick={() => setOpen(true)}>{t('queueing101.checklist')}</button>
    <dialog ref={dialog} className="queueing-checklist-dialog" aria-labelledby={titleId}
      onCancel={(event) => { event.preventDefault(); setOpen(false) }}>
      {open && <>
        <header><h2 lang="en" id={titleId}>{headingText(t, 'queueing101.checklist_title')}</h2><button ref={close} type="button" className="btn-ghost" onClick={() => setOpen(false)}>{t('tutorials.close')}</button></header>
        <div className="queueing-checklist-columns">
          <section><h3 lang="en">{headingText(t, 'queueing101.per_customer')}</h3><ul>{['identity', 'arrival', 'service', 'leave', 'outcome', 'observation_end'].map((key) => <li key={key}>{t(`queueing101.collect.${key}`)}</li>)}</ul></section>
          <section><h3 lang="en">{headingText(t, 'queueing101.per_period')}</h3><ul>{['process', 'window', 'clock', 'structure', 'availability', 'breaks'].map((key) => <li key={key}>{t(`queueing101.collect.${key}`)}</li>)}</ul></section>
        </div>
        <p className="form-hint">{t('queueing101.field_log_note')}</p>
        <div className="queueing-field-downloads"><a href="/queueing101/customer-field-log.csv" download>{t('queueing101.customer_sheet')}</a><a href="/queueing101/counter-availability-log.csv" download>{t('queueing101.availability_sheet')}</a></div>
      </>}
    </dialog>
  </>
}
