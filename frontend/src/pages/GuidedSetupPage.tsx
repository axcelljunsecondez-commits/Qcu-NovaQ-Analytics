import { Navigate, useParams } from 'react-router-dom'

export function GuidedSetupPage() {
  const { analysisId } = useParams()
  return <Navigate to={`/analyses/${analysisId}/setup`} replace />
}
