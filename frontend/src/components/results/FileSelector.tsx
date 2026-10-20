import { useTranslation } from 'react-i18next'
import type { DatasetOut } from '../../api/types'
import { formatDataDates, formatDay } from '../../lib/results'

function tagKey(dataset: DatasetOut): string | null {
  if (dataset.is_current === true) return 'results.tag_planning'
  if (dataset.purpose === 'review') return 'results.tag_review'
  return null
}

/** "View results from": every successfully processed file of the analysis (spec §7.7, D15). */
export function FileSelector({ files, selected, onSelect }: { files: DatasetOut[]; selected: DatasetOut; onSelect: (id: number) => void }) {
  const { t, i18n } = useTranslation()
  const covers = (dataset: DatasetOut) => formatDataDates(dataset.data_dates, i18n.language) ?? t('results.data_period_unavailable')
  const tag = tagKey(selected)
  return (
    <section className="card results-file">
      <div className="form-field">
        <label htmlFor="results-file">{t('results.view_from')}</label>
        <select id="results-file" value={String(selected.id)} onChange={(event) => onSelect(Number(event.target.value))}>
          {files.map((dataset) => {
            const key = tagKey(dataset)
            return (
              <option key={dataset.id} value={dataset.id}>
                {[dataset.source_filename || dataset.name, covers(dataset), key ? t(key) : null].filter(Boolean).join(' · ')}
              </option>
            )
          })}
        </select>
      </div>
      <p className="results-source-name">{selected.source_filename || selected.name}</p>
      <dl className="results-file-facts">
        <div><dt>{t('results.data_covers')}</dt><dd>{covers(selected)}</dd></div>
        <div><dt>{t('results.uploaded_on')}</dt><dd>{formatDay(selected.created_at, i18n.language)}</dd></div>
        {tag && <div><dt className="sr-only">{t('results.file_role')}</dt><dd><span className={`badge ${selected.is_current ? 'badge-info' : 'badge-warn'}`}>{t(tag)}</span></dd></div>}
      </dl>
    </section>
  )
}
