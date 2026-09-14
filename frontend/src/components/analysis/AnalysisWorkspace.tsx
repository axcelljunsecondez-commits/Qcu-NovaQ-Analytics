import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Navigate, Outlet, useLocation, useNavigate, useParams } from 'react-router-dom'
import { getAnalysis, listAnalyses } from '../../api/analyses'
import { ApiState } from '../ui/ApiState'
import { WorkflowNavigator } from './WorkflowNavigator'
import { analysisWorkflow } from '../../lib/workflow'

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
  const currentStep = analysisWorkflow.find(([path]) => location.pathname.endsWith(path))?.[0] ?? 'current'
  return (
    <div>
      <div className="analysis-context card">
        <div><span className="form-hint">{t('analyses.active')}</span><h1 className="card-title">{analysis.data.analysis.name}</h1></div>
        <div className="form-field">
          <label htmlFor="analysis-switcher">{t('analyses.switch')}</label>
          <select id="analysis-switcher" value={String(id)} onChange={(e) => navigate(`/analyses/${e.target.value}/${currentStep}`)}>
            {(analyses.data?.analyses ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
      </div>
      <div key={analysisId}><Outlet /></div>
      <WorkflowNavigator />
    </div>
  )
}
