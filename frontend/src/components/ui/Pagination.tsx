import { useEffect, useRef, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'

export function Pagination({ page, pageCount, onPageChange }: {
  page: number
  pageCount: number
  onPageChange: (page: number) => void
}) {
  const { t } = useTranslation()
  const previous = useRef<HTMLButtonElement>(null)
  const next = useRef<HTMLButtonElement>(null)
  // K-SAI-4: a focused button that becomes disabled on the first or last page would drop keyboard
  // focus to the page; keep it on the other button instead.
  const moved = useRef<'previous' | 'next' | null>(null)
  useEffect(() => {
    const from = moved.current
    moved.current = null
    if (from === 'next' && next.current?.disabled) previous.current?.focus()
    if (from === 'previous' && previous.current?.disabled) next.current?.focus()
  }, [page, pageCount])
  if (pageCount < 2) return null

  function go(event: MouseEvent<HTMLButtonElement>, target: number, from: 'previous' | 'next') {
    moved.current = event.currentTarget === document.activeElement ? from : null
    onPageChange(target)
  }

  return (
    <div className="table-pagination">
      <button ref={previous} type="button" className="btn-secondary" disabled={page === 0} onClick={(event) => go(event, page - 1, 'previous')}>
        {t('common.previous_page')}
      </button>
      <span role="status">{t('common.page_of', { page: page + 1, count: pageCount })}</span>
      <button ref={next} type="button" className="btn-secondary" disabled={page === pageCount - 1} onClick={(event) => go(event, page + 1, 'next')}>
        {t('common.next_page')}
      </button>
    </div>
  )
}
