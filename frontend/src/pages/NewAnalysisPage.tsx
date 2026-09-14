import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { createAnalysis } from '../api/analyses'

export function NewAnalysisPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [serviceType, setServiceType] = useState('')
  const [location, setLocation] = useState('')
  const create = useMutation({
    mutationFn: createAnalysis,
    onSuccess: ({ analysis }) => {
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
      navigate(`/analyses/${analysis.id}/setup`, { replace: true })
    },
  })
  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate({ name: name.trim(), service_type: serviceType || null, location_label: location || null })
  }
  return (
    <div>
      <h1 className="page-title">{t('analyses.new')}</h1>
      <p className="page-caption">{t('analyses.details_help')}</p>
      <form className="card" onSubmit={submit}>
        <div className="form-field"><label htmlFor="analysis-name">{t('analyses.name')}</label><input id="analysis-name" required value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="service-type">{t('analyses.service_type')}</label><input id="service-type" value={serviceType} onChange={(e) => setServiceType(e.target.value)} /></div>
        <div className="form-field"><label htmlFor="location-label">{t('analyses.location')}</label><input id="location-label" value={location} onChange={(e) => setLocation(e.target.value)} /></div>
        {create.isError && <div role="alert" className="alert alert-error">{t('errors.server')}</div>}
        <button type="submit" disabled={!name.trim() || create.isPending}>{t('analyses.continue')}</button>
      </form>
    </div>
  )
}
