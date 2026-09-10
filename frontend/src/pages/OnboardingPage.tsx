/**
 * OnboardingPage — Two-column welcome card matching the reference design.
 * Left: illustration area with workflow flow text.
 * Right: "What is NovaQ?" with 4 numbered points.
 */
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { completeOnboarding, getOnboardingStatus } from '../api/onboarding'

export function OnboardingPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const status = useQuery({
    queryKey: ['onboarding'],
    queryFn: getOnboardingStatus,
  })

  const complete = useMutation({
    mutationFn: completeOnboarding,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['onboarding'] })
      void queryClient.invalidateQueries({ queryKey: ['me'] })
      navigate('/analyses', { replace: true })
    },
  })

  useEffect(() => {
    if (status.data?.completed) {
      navigate('/analyses', { replace: true })
    }
  }, [status.data?.completed, navigate])

  function handleSkip() {
    complete.mutate({
      operation_type: 'other',
      preferred_terminology: {},
    })
  }

  function handleNext() {
    complete.mutate({
      operation_type: 'other',
      preferred_terminology: {},
    })
  }

  return (
    <div style={{
      minHeight: 'calc(100vh - 43px)',
      background: 'linear-gradient(135deg, #f7fbff, #eaf4ff)',
      display: 'grid',
      placeItems: 'center',
      padding: '28px',
    }}>
      <div style={{
        width: 'min(980px, 100%)',
        background: '#fff',
        border: '1px solid var(--border)',
        borderRadius: '18px',
        boxShadow: 'var(--shadow-md)',
        overflow: 'hidden',
        display: 'grid',
        gridTemplateColumns: '1.1fr .9fr',
      }}>
        {/* Left — Illustration */}
        <div style={{ padding: '48px' }}>
          <div style={{ fontWeight: 900, fontSize: '20px', marginBottom: '22px' }}>
            Nova<b style={{ color: 'var(--accent)' }}>Q</b>
          </div>
          <h1 style={{ fontSize: '31px', margin: '0 0 8px', letterSpacing: '-1px' }}>
            Welcome to NovaQ
          </h1>
          <p style={{ color: '#667990', fontSize: '13px', lineHeight: 1.6 }}>
            A short introduction helps first-time users understand the workflow before entering operational information.
          </p>
          <div style={{
            height: '250px',
            borderRadius: '14px',
            background: 'linear-gradient(155deg, #ddecff, #f8fbff)',
            position: 'relative',
            overflow: 'hidden',
            margin: '22px 0',
          }}>
            <div style={{
              position: 'absolute',
              left: '14%',
              right: '14%',
              bottom: '28px',
              height: '105px',
              borderRadius: '14px',
              background: 'white',
              border: '1px solid #cfe1f4',
              boxShadow: '0 14px 30px rgba(20,71,125,.08)',
            }} />
            <div style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              transform: 'translate(-50%, -50%)',
              fontSize: '12px',
              fontWeight: 800,
              color: '#0c71dc',
              width: '78%',
              textAlign: 'center',
              letterSpacing: '0.02em',
            }}>
              CURRENT → OPTIMIZE → SIMULATE → COMPARE
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginTop: '16px' }}>
            <button type="button" className="btn-ghost" onClick={handleSkip}>
              Skip for now
            </button>
            <button type="button" onClick={handleNext}>
              Next →
            </button>
          </div>
        </div>

        {/* Right — Info Panel */}
        <div style={{ padding: '36px', background: '#f5f9fd', borderLeft: '1px solid var(--border)' }}>
          <h3 className="section-title">What is NovaQ?</h3>
          <p style={{ color: '#667990', fontSize: '13px', lineHeight: 1.6 }}>
            NovaQ turns observed queue data into understandable operational insights, staffing recommendations, simulation results, scenario comparisons, and reports.
          </p>
          <div style={{ display: 'grid', gap: '12px', marginTop: '18px' }}>
            {[
              { num: 1, title: 'No queueing-theory background required', desc: 'Operational questions are translated into the technical analysis underneath.' },
              { num: 2, title: 'Works from real operational data', desc: 'Arrival and service records form the baseline.' },
              { num: 3, title: 'Optimization and simulation are separate', desc: 'Optimization proposes a plan; simulation tests how it behaves.' },
              { num: 4, title: 'Decision-ready output', desc: 'Compare current vs proposed scenarios before reporting.' },
            ].map((point) => (
              <div key={point.num} style={{ display: 'flex', gap: '10px', fontSize: '12px', color: '#415b75' }}>
                <span style={{
                  width: '26px',
                  height: '26px',
                  borderRadius: '50%',
                  background: '#e0f0ff',
                  color: 'var(--accent)',
                  display: 'grid',
                  placeItems: 'center',
                  fontWeight: 900,
                  flexShrink: 0,
                }}>
                  {point.num}
                </span>
                <span>
                  <strong>{point.title}</strong><br />
                  <small style={{ color: '#697a90' }}>{point.desc}</small>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
