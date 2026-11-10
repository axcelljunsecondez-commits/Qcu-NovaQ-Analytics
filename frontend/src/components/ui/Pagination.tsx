import { useTranslation } from 'react-i18next'

export function Pagination({ page, pageCount, onPageChange }: {
  page: number
  pageCount: number
  onPageChange: (page: number) => void
}) {
  const { t } = useTranslation()
  if (pageCount < 2) return null

  return (
    <div className="table-pagination">
      <button type="button" className="btn-secondary" disabled={page === 0} onClick={() => onPageChange(page - 1)}>
        {t('common.previous_page')}
      </button>
      <span role="status">{t('common.page_of', { page: page + 1, count: pageCount })}</span>
      <button type="button" className="btn-secondary" disabled={page === pageCount - 1} onClick={() => onPageChange(page + 1)}>
        {t('common.next_page')}
      </button>
    </div>
  )
}
