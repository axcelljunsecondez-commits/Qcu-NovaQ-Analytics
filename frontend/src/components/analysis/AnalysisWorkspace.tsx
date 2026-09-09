import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { NavLink, Navigate, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom'
import { getAnalysis, listAnalyses } from '../../api/analyses'
import { ApiState } from '../ui/ApiState'

const steps = [
  ['setup', 'analyses.progress.setup'],
  ['setup', 'analyses.progress.upload'],
  ['setup', 'analyses.progress.model'],
  ['current', 'analyses.progress.analyze'],
] as const

const workspacePages = [
  ['current', 'nav.current'], ['optimize', 'nav.optimize'], ['simulate', 'nav.simulate'],
  ['compare', 'nav.compare'], ['reports', 'nav.reports'],
] as const

export function AnalysisWorkspace() {
  const { t } = useTranslation()
  const { analysisId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const id = Number(analysisId)
  const analysis = useQuery({ queryKey: ['analysis', id], queryFn: () => getAnalysis(id), enabled: Number.isInteger(id) })
  const analyses = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses })
  if (!Number.isInteger(id)) return <Navigate to="/analyses" replace />
  if (analysis.isLoading) return <ApiState.Loading />
  if (analysis.isError || !analysis.data) return <ApiState.ErrorState />
  const currentSection = location.pathname.split('/').pop() || 'setup'
  return (
    <div>
      <div className="analysis-context card">
        <div><span className="form-hint">{t('analyses.active')}</span><h1 className="card-title">{analysis.data.analysis.name}</h1></div>
        <div className="form-field">
          <label htmlFor="analysis-switcher">{t('analyses.switch')}</label>
          <select id="analysis-switcher" value={String(id)} onChange={(e) => navigate(`/analyses/${e.target.value}/current`)}>
            {(analyses.data?.analyses ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
      </div>
      <nav className="analysis-progress" aria-label={t('analyses.progress.label')}>
        {steps.map(([path, label], index) => <NavLink key={`${path}-${index}`} className={currentSection === path ? 'active' : undefined} to={path}>{index + 1}. {t(label)}</NavLink>)}
      </nav>
      <nav className="analysis-tabs">
        <NavLink to="setup">{t('analyses.setup')}</NavLink>
        {workspacePages.map(([path, label]) => <NavLink key={path} to={path}>{t(label)}</NavLink>)}
      </nav>
      <div key={analysisId}><Outlet /></div>
    </div>
  )
}
