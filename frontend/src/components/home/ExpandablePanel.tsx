import { useId, type ReactNode } from 'react'

export function Chevron({ direction }: { direction: 'left' | 'right' | 'down' }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={direction === 'left' ? 'm15 6-6 6 6 6' : direction === 'right' ? 'm9 6 6 6-6 6' : 'm6 9 6 6 6-6'} /></svg>
}

interface ExpandablePanelProps {
  id?: string
  title: string
  description: string
  open: boolean
  onOpenChange: (open: boolean) => void
  className?: string
  children: ReactNode
}

/** Shared disclosure semantics and in-place reveal for workflow slides and the queue comparison. */
export function ExpandablePanel({ id, title, description, open, onOpenChange, className = '', children }: ExpandablePanelProps) {
  const uniqueId = useId()
  const baseId = id ?? uniqueId
  return <section className={`home-guide ${open ? 'is-open' : ''} ${className}`} data-guide={id}>
    <h2 className="home-guide-heading">
      <button id={`${baseId}-trigger`} type="button" className="home-guide-toggle" aria-expanded={open}
        aria-controls={`${baseId}-panel`} aria-labelledby={`${baseId}-title`} aria-describedby={`${baseId}-description`} onClick={() => onOpenChange(!open)}>
        <span><strong lang="en" id={`${baseId}-title`}>{title}</strong><small id={`${baseId}-description`}>{description}</small></span><Chevron direction="down" />
      </button>
    </h2>
    <div id={`${baseId}-panel`} className="home-guide-panel" role="region" aria-labelledby={`${baseId}-trigger`}
      aria-hidden={!open} inert={!open}>
      <div className="home-guide-inner"><div className="home-guide-body">{children}</div></div>
    </div>
  </section>
}
