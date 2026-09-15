import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  downloadTemplate,
  getTemplateGuide,
  type TemplateSchema,
  type TemplateStructure,
} from '../../api/templates'
import { ApiState } from '../ui/ApiState'

interface SetupDataTemplatesProps {
  queueStructure: TemplateStructure | 'unknown' | 'single_server'
}

export function SetupDataTemplates({ queueStructure }: SetupDataTemplatesProps) {
  const { t } = useTranslation()
  const [schema, setSchema] = useState<TemplateSchema>('aggregate')
  const [showGuide, setShowGuide] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const structure: TemplateStructure | null = queueStructure === 'shared_queue' || queueStructure === 'separate_queues'
    ? queueStructure
    : null
  const guide = useQuery({
    queryKey: ['template-guide', structure, schema],
    queryFn: () => getTemplateGuide(structure!, schema),
    enabled: structure !== null && showGuide,
  })

  if (structure === null) return null

  async function download(format: 'csv' | 'xlsx') {
    setError(null)
    setDownloading(true)
    try {
      await downloadTemplate(structure!, schema, format)
    } catch {
      setError(t('errors.server'))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="card" style={{ marginTop: '12px' }}>
      <h3 className="card-title">{t('template.prepare_title')}</h3>
      <p className="form-hint">{t('template.prepare_help')}</p>
      <div className="form-row" role="group" aria-label={t('template.schema_label')}>
        <button
          type="button"
          className={schema === 'aggregate' ? 'btn-primary' : 'btn-ghost'}
          aria-pressed={schema === 'aggregate'}
          onClick={() => setSchema('aggregate')}
        >
          {t('template.schema_aggregate')}
        </button>
        <button
          type="button"
          className={schema === 'events' ? 'btn-primary' : 'btn-ghost'}
          aria-pressed={schema === 'events'}
          onClick={() => setSchema('events')}
        >
          {t('template.schema_events')}
        </button>
      </div>
      <div className="form-row">
        <button type="button" className="btn-secondary" disabled={downloading} onClick={() => void download('csv')}>
          {t('template.download_csv')}
        </button>
        <button type="button" className="btn-secondary" disabled={downloading} onClick={() => void download('xlsx')}>
          {t('template.download_xlsx')}
        </button>
        <button type="button" className="btn-ghost" onClick={() => setShowGuide((value) => !value)} aria-expanded={showGuide}>
          {t(showGuide ? 'template.hide_guide' : 'template.view_guide')}
        </button>
      </div>
      {error && <div role="alert" className="alert alert-error">{error}</div>}
      {showGuide && (
        <div style={{ marginTop: '12px' }}>
          {guide.isLoading && <ApiState.Loading />}
          {guide.isError && <div role="alert" className="alert alert-error">{t('errors.server')}</div>}
          {guide.data && (
            <>
              <h4 className="section-title">{t('template.example_title')}</h4>
              <div className="card table-scroll" role="region" aria-label={t('template.example_title')} tabIndex={0}>
                <table>
                  <thead>
                    <tr>
                      {guide.data.columns.map((column) => <th scope="col" key={column}>{column}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {guide.data.example_rows.map((row, index) => (
                      <tr key={index}>
                        {guide.data.columns.map((column) => <td key={column}>{String(row[column] ?? '')}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h4 className="section-title">{t('template.guide_title')}</h4>
              <div className="card table-scroll" role="region" aria-label={t('template.guide_title')} tabIndex={0}>
                <table>
                  <thead>
                    <tr>
                      <th scope="col">{t('template.guide_field')}</th>
                      <th scope="col">{t('template.guide_meaning')}</th>
                      <th scope="col">{t('template.guide_required')}</th>
                      <th scope="col">{t('template.guide_example')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {guide.data.field_guide.map((entry) => (
                      <tr key={entry.field}>
                        <th scope="row">{entry.field}</th>
                        <td>{entry.meaning}</td>
                        <td>{entry.required}</td>
                        <td>{entry.example}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
