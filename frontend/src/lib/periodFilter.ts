/** Sentinel select value meaning "no restriction" for the period / service-line filter. */
export const ALL = '__all__'

export function matchesFilter(time: unknown, queueId: unknown, period: string, line: string) {
  return (period === ALL || time === period) && (line === ALL || queueId === line)
}
