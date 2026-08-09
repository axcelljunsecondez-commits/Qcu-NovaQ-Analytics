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
    queryFn: listDatasets,
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
    onError: () => {
      setNotice({ ok: false, message: t('errors.upload') })
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
              aria-label="file"
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileChange}
            />
          </div>
          <button type="button" onClick={handleUpload} disabled={!file || uploadMutation.isPending}>
            {t('datasets.upload')}
          </button>
        </div>
        {notice && (
          <div className={`alert ${notice.ok ? 'alert-ok' : 'alert-error'}`}>
            {notice.ok ? t('datasets.valid_ok') : `${t('datasets.valid_fail')} ${notice.message}`}
          </div>
        )}
        {uploadMutation.isPending && <ApiState.Loading />}
      </div>

      {datasetsQuery.isLoading && <ApiState.Loading />}
      {datasetsQuery.isError && <ApiState.ErrorState error={datasetsQuery.error} />}

      {datasetsQuery.isSuccess &&
        (datasets.length === 0 ? (
          <ApiState.Empty message={t('datasets.empty')} />
        ) : (
          <div className="card">
            <table>
              <thead>
                <tr>
                  <th>{t('datasets.title')}</th>
                  <th>File</th>
                  <th>{t('datasets.rows')}</th>
                  <th>{t('dashboard.last_upload')}</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {datasets.map((d) => (
                  <tr key={d.id}>
                    <td>{d.name}</td>
                    <td>{d.source_filename}</td>
                    <td>{d.row_count}</td>
                    <td>{new Date(d.created_at).toLocaleDateString()}</td>
                    <td>
                      <span className={`badge ${d.validation.ok ? 'badge-ok' : 'badge-bad'}`}>
                        {d.validation.ok ? '✓' : '✗'}
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
        ))}
    </div>
  )
}
