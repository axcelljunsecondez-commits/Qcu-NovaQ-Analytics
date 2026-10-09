export type Answer = 'yes' | 'no' | 'unsure'
export type RecommendedStructure = 'shared_queue' | 'separate_queues'

/** Advisory only: Q1 Yes decides shared; otherwise Q2 Yes decides separate. */
export function recommend(q1: Answer | null, q2: Answer | null): RecommendedStructure | null {
  if (q1 === 'yes') return 'shared_queue'
  if (q1 !== null && q2 === 'yes') return 'separate_queues'
  return null
}

export function answered(q1: Answer | null, q2: Answer | null): boolean {
  return q1 !== null && (q1 === 'yes' || q2 !== null)
}
