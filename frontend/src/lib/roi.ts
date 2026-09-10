export const SUNDAYS_PER_YEAR = 52
export const DAYS_PER_YEAR = 365

export interface RoiInput {
  currentTotal: number
  optimalTotal: number
  holidays: number
  closedSundays: boolean
}

export interface RoiResult {
  dailySavings: number
  monthlySavings: number
  annualSavings: number
  workingDaysPerYear: number
}

export function computeRoi({ currentTotal, optimalTotal, holidays, closedSundays }: RoiInput): RoiResult {
  const dailySavings = currentTotal - optimalTotal
  const sundays = closedSundays ? SUNDAYS_PER_YEAR : 0
  const workingDaysPerYear = DAYS_PER_YEAR - sundays - holidays
  const annualSavings = dailySavings * workingDaysPerYear
  const monthlySavings = annualSavings / 12
  return { dailySavings, monthlySavings, annualSavings, workingDaysPerYear }
}

export function clampHolidays(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.min(DAYS_PER_YEAR, Math.max(0, Math.round(value)))
}