/**
 * NovaQ Insights - Plain language explanations of queue analysis results.
 */
import { useTranslation } from 'react-i18next'
import type { Insight } from '../../lib/insights'

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
    <div className="novaq-insights" role="status">
      <h2 className="insights-title">{t('insights.title')}</h2>
      <div className="insights-list">
        {insights.map((insight, index) => (
          <div key={index} className={`insight-card ${getInsightClass(insight.type)}`}>
            <div className="insight-header">
              <span className="insight-icon" aria-hidden="true">{getInsightIcon(insight.type)}</span>
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
