/**
 * NovaQ Insights - Plain language explanations of queue analysis results.
 */
import { useTranslation } from 'react-i18next'

export interface Insight {
  type: 'warning' | 'success' | 'info' | 'recommendation'
  title: string
  message: string
  action?: {
    label: string
    href: string
  }
}

interface NovaQInsightsProps {
  insights: Insight[]
}

export function NovaQInsights({ insights }: NovaQInsightsProps) {
  const { t } = useTranslation()

  if (insights.length === 0) {
    return null
  }

  function getInsightClass(type: Insight['type']): string {
    switch (type) {
      case 'warning':
        return 'insight-warning'
      case 'success':
        return 'insight-success'
      case 'recommendation':
        return 'insight-recommendation'
      default:
        return 'insight-info'
    }
  }

  function getInsightIcon(type: Insight['type']): string {
    switch (type) {
      case 'warning':
        return '⚠️'
      case 'success':
        return '✓'
      case 'recommendation':
        return '💡'
      default:
        return 'ℹ'
    }
  }

  return (
    <div className="novaq-insights">
      <h2 className="insights-title">{t('insights.title')}</h2>
      <div className="insights-list">
        {insights.map((insight, index) => (
          <div key={index} className={`insight-card ${getInsightClass(insight.type)}`}>
            <div className="insight-header">
              <span className="insight-icon">{getInsightIcon(insight.type)}</span>
              <h3 className="insight-title">{insight.title}</h3>
            </div>
            <p className="insight-message">{insight.message}</p>
            {insight.action && (
              <a href={insight.action.href} className="insight-action">
                {insight.action.label}
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Generate insights from optimization results.
 */
export function generateOptimizationInsights(
  currentCashiers: number,
  optimizedCashiers: number,
  currentWait: number | null,
  optimizedWait: number | null,
  currentUtilization: number | null,
  t: (key: string, params?: Record<string, string | number>) => string,
): Insight[] {
  const insights: Insight[] = []

  if (optimizedCashiers > currentCashiers) {
    insights.push({
      type: 'recommendation',
      title: t('insights.staffing_increase_title'),
      message: t('insights.staffing_increase_message', {
        current: currentCashiers,
        recommended: optimizedCashiers,
      }),
    })
  }

  if (optimizedCashiers < currentCashiers) {
    insights.push({
      type: 'success',
      title: t('insights.staffing_reduction_title'),
      message: t('insights.staffing_reduction_message', {
        current: currentCashiers,
        recommended: optimizedCashiers,
      }),
    })
  }

  if (currentWait !== null && currentWait > 0 && optimizedWait !== null) {
    const waitReduction = ((currentWait - optimizedWait) / currentWait) * 100
    if (waitReduction > 20) {
      insights.push({
        type: 'success',
        title: t('insights.wait_improvement_title'),
        message: t('insights.wait_improvement_message', {
          reduction: Math.round(waitReduction),
        }),
      })
    }
  }

  if (currentUtilization !== null && currentUtilization > 0.9) {
    insights.push({
      type: 'warning',
      title: t('insights.high_utilization_title'),
      message: t('insights.high_utilization_message', {
        utilization: Math.round(currentUtilization * 100),
      }),
    })
  }

  return insights
}

/**
 * Generate insights from simulation results.
 */
export function generateSimulationInsights(
  criticalSegments: number,
  totalSegments: number,
  served: number,
  dropped: number,
  t: (key: string, params?: Record<string, string | number>) => string,
): Insight[] {
  const insights: Insight[] = []

  if (criticalSegments > 0) {
    insights.push({
      type: 'warning',
      title: t('insights.queue_pressure_title'),
      message: t('insights.queue_pressure_message', {
        count: criticalSegments,
        total: totalSegments,
      }),
    })
  }

  if (dropped > 0 && (served + dropped) > 0) {
    const dropRate = (dropped / (served + dropped)) * 100
    insights.push({
      type: 'warning',
      title: t('insights.customer_loss_title'),
      message: t('insights.customer_loss_message', {
        dropped,
        rate: Math.round(dropRate),
      }),
    })
  }

  if (criticalSegments === 0 && dropped === 0) {
    insights.push({
      type: 'success',
      title: t('insights.healthy_operation_title'),
      message: t('insights.healthy_operation_message'),
    })
  }

  return insights
}
