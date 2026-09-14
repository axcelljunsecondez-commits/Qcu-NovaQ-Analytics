export interface Insight {
  type: 'warning' | 'success' | 'info' | 'recommendation'
  title: string
  message: string
  action?: {
    label: string
    href: string
  }
}

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
