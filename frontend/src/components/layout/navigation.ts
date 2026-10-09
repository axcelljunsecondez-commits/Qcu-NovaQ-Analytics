// Global navigation model (spec 2026-10-09 §7.3, MASTER §9.1 version 1.1).
// Insights and Simulation items open the last-used analysis. Until the new
// Analysis results and Queue simulation pages ship (plan phases U6/U7), they
// point at the existing Current, Simulate and Reports workspace pages.

export type NavIconName = 'analyses' | 'results' | 'reports' | 'simulation' | 'calculator'

export interface NavItem {
  key: 'my_analyses' | 'analysis_results' | 'reports' | 'queue_simulation' | 'quick_calculator'
  icon: NavIconName
  target: (lastAnalysisId: number | null) => string
  matches: (pathname: string) => boolean
}

export interface NavGroup {
  key: 'workspace' | 'insights' | 'simulation' | 'tools'
  items: NavItem[]
}

function analysisPage(step: string) {
  return (lastAnalysisId: number | null) => (lastAnalysisId ? `/analyses/${lastAnalysisId}/${step}` : '/analyses')
}

function analysisStep(...steps: string[]) {
  const pattern = new RegExp(`^/analyses/\\d+/(${steps.join('|')})/?$`)
  return (pathname: string) => pattern.test(pathname)
}

const analysisResults: NavItem = {
  key: 'analysis_results',
  icon: 'results',
  target: analysisPage('current'),
  matches: analysisStep('current', 'compare'),
}
const reports: NavItem = { key: 'reports', icon: 'reports', target: analysisPage('reports'), matches: analysisStep('reports') }
const queueSimulation: NavItem = {
  key: 'queue_simulation',
  icon: 'simulation',
  target: analysisPage('simulate'),
  matches: analysisStep('simulate', 'decision'),
}
const quickCalculator: NavItem = {
  key: 'quick_calculator',
  icon: 'calculator',
  target: () => '/tools/calculator',
  matches: (pathname) => pathname.startsWith('/tools/calculator'),
}
const myAnalyses: NavItem = {
  key: 'my_analyses',
  icon: 'analyses',
  target: () => '/analyses',
  matches: (pathname) =>
    /^\/analyses(\/|$)/.test(pathname) && ![analysisResults, reports, queueSimulation].some((item) => item.matches(pathname)),
}

export const navGroups: NavGroup[] = [
  { key: 'workspace', items: [myAnalyses] },
  { key: 'insights', items: [analysisResults, reports] },
  { key: 'simulation', items: [queueSimulation] },
  { key: 'tools', items: [quickCalculator] },
]

export const settingsSections = ['account', 'preferences', 'appearance', 'files', 'users'] as const
export type SettingsSection = (typeof settingsSections)[number]

export function isSettingsSection(value: string | undefined): value is SettingsSection {
  return settingsSections.includes(value as SettingsSection)
}

// Breadcrumb as translation keys, outermost first.
export function breadcrumbKeys(pathname: string): string[] {
  for (const group of navGroups) {
    const item = group.items.find((candidate) => candidate.matches(pathname))
    if (item) return [`nav.group_${group.key}`, `nav.${item.key}`]
  }
  const settings = /^\/settings\/([^/]+)/.exec(pathname)
  if (settings && isSettingsSection(settings[1])) return ['nav.settings', `settings.section_${settings[1]}`]
  if (pathname.startsWith('/settings')) return ['nav.settings']
  if (pathname.startsWith('/help')) return ['nav.get_help']
  return []
}
