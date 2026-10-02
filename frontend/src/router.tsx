import { lazy, Suspense, useLayoutEffect, useSyncExternalStore } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { RequireOnboarding } from './auth/RequireOnboarding'
import { RequireRole } from './auth/RequireRole'
import { AppLayout } from './components/layout/AppLayout'
import { AnalysisWorkspace } from './components/analysis/AnalysisWorkspace'
import { ApiState } from './components/ui/ApiState'
import { bindActiveQueryClient, isClientUpdateRequired, subscribeClientUpdate } from './lib/http'

// oxlint-disable react/only-export-components -- router module intentionally owns lazy route components and router config
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then((m) => ({ default: m.RegisterPage })))
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage').then((m) => ({ default: m.OnboardingPage })))
const GuidedSetupPage = lazy(() => import('./pages/GuidedSetupPage').then((m) => ({ default: m.GuidedSetupPage })))
const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
)
const DatasetsPage = lazy(() =>
  import('./pages/DatasetsPage').then((m) => ({ default: m.DatasetsPage })),
)
const AnalysisPage = lazy(() =>
  import('./pages/AnalysisPage').then((m) => ({ default: m.AnalysisPage })),
)
const OptimizePage = lazy(() =>
  import('./pages/OptimizePage').then((m) => ({ default: m.OptimizePage })),
)
const SimulationPage = lazy(() =>
  import('./pages/SimulationPage').then((m) => ({ default: m.SimulationPage })),
)
const ComparisonPage = lazy(() =>
  import('./pages/ComparisonPage').then((m) => ({ default: m.ComparisonPage })),
)
const ReportsPage = lazy(() =>
  import('./pages/ReportsPage').then((m) => ({ default: m.ReportsPage })),
)
const AccountPage = lazy(() =>
  import('./pages/AccountPage').then((m) => ({ default: m.AccountPage })),
)
const HelpPage = lazy(() => import('./pages/HelpPage').then((m) => ({ default: m.HelpPage })))
const AdminPage = lazy(() => import('./pages/AdminPage').then((m) => ({ default: m.AdminPage })))
const AnalysesPage = lazy(() => import('./pages/AnalysesPage').then((m) => ({ default: m.AnalysesPage })))
const NewAnalysisPage = lazy(() => import('./pages/NewAnalysisPage').then((m) => ({ default: m.NewAnalysisPage })))
const AnalysisSetupPage = lazy(() => import('./pages/AnalysisSetupPage').then((m) => ({ default: m.AnalysisSetupPage })))
const AnalysisCurrentPage = lazy(() => import('./pages/AnalysisCurrentPage').then((m) => ({ default: m.AnalysisCurrentPage })))
const DecisionEndpointPage = lazy(() => import('./components/analysis/DecisionEndpointPage').then((m) => ({ default: m.DecisionEndpointPage })))

// oxlint-disable-next-line react/only-export-components -- router module intentionally mixes layout components with the router constant
function RootLayout({ reloadDocument }: { reloadDocument: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const updateRequired = useSyncExternalStore(subscribeClientUpdate, isClientUpdateRequired)
  useLayoutEffect(() => bindActiveQueryClient(queryClient), [queryClient])

  if (updateRequired) {
    return (
      <main className="empty-state" role="alert" aria-live="assertive" style={{ minHeight: '100vh' }}>
        <h1>{t('errors.client_update_title')}</h1>
        <p>{t('errors.client_update_body')}</p>
        <button type="button" className="btn-primary" onClick={reloadDocument}>
          {t('errors.client_update_reload')}
        </button>
      </main>
    )
  }

  return (
    <AuthProvider>
      <Suspense fallback={<ApiState.Loading />}>
        <Outlet />
      </Suspense>
    </AuthProvider>
  )
}

export function createAppRouter(reloadDocument: () => void = () => window.location.reload()) {
  return createBrowserRouter([
    {
      element: <RootLayout reloadDocument={reloadDocument} />,
      children: [
        {
          path: '/login',
          element: <LoginPage />,
        },
        { path: '/register', element: <RegisterPage /> },
        { path: '/verify-email', element: <VerifyEmailPage /> },
        { path: '/forgot-password', element: <ForgotPasswordPage /> },
        { path: '/reset-password', element: <ResetPasswordPage /> },
        {
          element: <RequireAuth />,
          children: [
            {
              path: '/onboarding',
              element: <OnboardingPage />,
            },
            {
              element: <RequireOnboarding />,
              children: [
                {
                  element: <AppLayout />,
                  children: [
                    { path: '/analyses', element: <AnalysesPage /> },
                    { path: '/analyses/new', element: <NewAnalysisPage /> },
                    {
                      path: '/analyses/:analysisId',
                      element: <AnalysisWorkspace />,
                      children: [
                        { index: true, element: <Navigate to="setup" replace /> },
                        { path: 'setup', element: <AnalysisSetupPage /> },
                        { path: 'guided-setup', element: <GuidedSetupPage /> },
                        { path: 'current', element: <AnalysisCurrentPage /> },
                        { path: 'optimize', element: <OptimizePage /> },
                        { path: 'compare', element: <ComparisonPage /> },
                        { path: 'simulate', element: <SimulationPage /> },
                        { path: 'decision', element: <DecisionEndpointPage /> },
                        { path: 'reports', element: <ReportsPage /> },
                      ],
                    },
                    { path: '/dashboard', element: <DashboardPage /> },
                    { path: '/datasets', element: <DatasetsPage /> },
                    { path: '/analysis', element: <AnalysisPage /> },
                    { path: '/help', element: <HelpPage /> },
                    { path: '/account', element: <AccountPage /> },
                    {
                      path: '/admin',
                      element: <RequireRole role="admin" />,
                      children: [{ index: true, element: <AdminPage /> }],
                    },
                  ],
                },
              ],
            },
          ],
        },
        {
          path: '*',
          element: <Navigate to="/login" replace />,
        },
      ],
    },
  ])
}

export const router = createAppRouter()
