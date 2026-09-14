import { useState, type ChangeEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { listDatasets, uploadDataset, deleteDataset } from '../api/datasets'
import { ApiState } from '../components/ui/ApiState'

export function DatasetsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [notice, setNotice] = useState<{ ok: boolean; message: string } | null>(null)

  const datasetsQuery = useQuery({
    queryKey: ['datasets'],
    queryFn: () => listDatasets(),
  })

  const uploadMutation = useMutation({
    mutationFn: (f: File) => uploadDataset(f),
    onSuccess: (data) => {
      setNotice({
        ok: data.dataset.validation.ok,
        message: data.dataset.validation.message,
      })
      void queryClient.invalidateQueries({ queryKey: ['datasets'] })
    },
    onError: (error: unknown) => {
      const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
      let message = t('errors.upload')
      if (typeof detail === 'string') {
        message = detail
      } else if (Array.isArray(detail)) {
        const first = detail[0] as { msg?: string } | undefined
        if (first?.msg) {
          message = first.msg
        }
      }
      setNotice({ ok: false, message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteDataset(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['datasets'] })
    },
  })

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null)
    setNotice(null)
  }

  function handleUpload() {
    if (file) {
      uploadMutation.mutate(file)
    }
  }

  function handleDelete(id: number) {
    if (window.confirm(t('datasets.confirm_delete'))) {
      deleteMutation.mutate(id)
    }
  }

  const datasets = datasetsQuery.data?.datasets ?? []

  return (
    <div>
      <h1 className="page-title">{t('datasets.title')}</h1>
      <p className="page-caption">{t('datasets.upload_hint')}</p>

      <div className="card">
        <h2 className="card-title">{t('datasets.upload')}</h2>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="dataset-file">{t('datasets.upload')}</label>
            <input
              id="dataset-file"
              aria-label={t('datasets.file')}
              type="file"
              accept=".csv,.xlsx"
              onChange={handleFileChange}
            />
          </div>
          <button type="button" onClick={handleUpload} disabled={!file || uploadMutation.isPending}>
            {t('datasets.upload')}
          </button>
        </div>
        {notice && (
          <div role={notice.ok ? 'status' : 'alert'} className={`alert ${notice.ok ? 'alert-ok' : 'alert-error'}`}>
            {notice.ok ? t('datasets.valid_ok') : `${t('datasets.valid_fail')} ${notice.message}`}
          </div>
        )}
        {uploadMutation.isPending && <ApiState.Loading />}
      </div>

      {datasetsQuery.isLoading && <ApiState.Loading />}
      {datasetsQuery.isError && <ApiState.ErrorState error={datasetsQuery.error} />}
      {deleteMutation.isError && <div role="alert" className="alert alert-error">{t('errors.server')}</div>}

      {datasetsQuery.isSuccess &&
        (datasets.length === 0 ? (
          <ApiState.Empty message={t('datasets.empty')} />
        ) : (
          <div className="card">
            <div className="table-scroll" role="region" aria-label={t('datasets.table_caption')} tabIndex={0}>
            <table>
              <caption className="sr-only">{t('datasets.table_caption')}</caption>
              <thead>
                <tr>
                  <th scope="col">{t('datasets.title')}</th>
                  <th scope="col">{t('datasets.file')}</th>
                  <th scope="col">{t('datasets.rows')}</th>
                  <th scope="col">{t('dashboard.last_upload')}</th>
                  <th scope="col">{t('datasets.status')}</th>
                  <th scope="col"><span className="sr-only">{t('common.actions')}</span></th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((d) => (
                  <tr key={d.id}>
                    <th scope="row">{d.name}</th>
                    <td>{d.source_filename}</td>
                    <td>{d.row_count}</td>
                    <td>{new Date(d.created_at).toLocaleDateString()}</td>
                    <td>
                      <span className={`badge ${d.validation.ok ? 'badge-ok' : 'badge-bad'}`}>
                        {d.validation.ok ? t('dashboard.valid') : t('dashboard.invalid')}
                      </span>
                    </td>
                    <td>
                      <button type="button" className="btn-ghost" onClick={() => handleDelete(d.id)}>
                        {t('datasets.delete')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        ))}
    </div>
  )
}
