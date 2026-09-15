import type { SimulationTrace } from '../api/types'

const TIME_EPSILON = 1e-9

export type PlaybackLayout = 'shared' | 'separate'

/**
 * Route playback rendering by queue structure, never by model id.
 * Trace-level `shared` maps to the pooled renderer; trace-level `separate`
 * (setup-level `separate_queues`) maps to the separate renderer.
 * Unknown values fall back to the shared renderer.
 */
export function selectPlaybackLayout(queueStructure: string): PlaybackLayout {
  return queueStructure === 'separate' || queueStructure === 'separate_queues'
    ? 'separate'
    : 'shared'
}

export interface SeparateLaneSnapshot {
  queueId: string
  serverId: string | number | null
  arrived: number
  waitingCustomerIds: number[]
  servingByServer: Record<string, number>
  servedCustomerIds: number[]
  abandonedCustomerIds: number[]
}

function laneKeyFor(queueId: string | number | null | undefined, serverId: string | number | null): string {
  if (queueId !== null && queueId !== undefined) return String(queueId)
  if (serverId !== null) return String(serverId)
  return 'unassigned'
}

/**
 * Pure per-queue reducer over the authoritative backend trace.
 * Presentation-only: filters by simulation time and groups by traced
 * queue_id/server_id. Never regenerates arrivals, never reroutes customers.
 */
export function deriveSeparateLaneSnapshots(
  trace: SimulationTrace,
  simulationTime: number,
): SeparateLaneSnapshot[] {
  const laneOrder: string[] = []
  const serverByLane = new Map<string, string | number | null>()
  trace.trace.forEach((event) => {
    const key = laneKeyFor(event.queue_id, event.server_id)
    if (!laneOrder.includes(key)) laneOrder.push(key)
    if (!serverByLane.has(key) || serverByLane.get(key) === null) {
      if (event.server_id !== null) serverByLane.set(key, event.server_id)
      else if (!serverByLane.has(key)) serverByLane.set(key, null)
    }
  })

  const processed = trace.trace.filter((event) => event.t <= simulationTime + TIME_EPSILON)
  return laneOrder.map((laneKey) => {
    const laneEvents = processed.filter(
      (event) => laneKeyFor(event.queue_id, event.server_id) === laneKey,
    )
    const arrivedIds = new Set<number>()
    const waitingCustomerIds: number[] = []
    const servingByServer: Record<string, number> = {}
    const servedCustomerIds: number[] = []
    const abandonedCustomerIds: number[] = []

    laneEvents.forEach((event) => {
      if (event.type === 'arrival') {
        arrivedIds.add(event.customer_id)
        waitingCustomerIds.push(event.customer_id)
        return
      }
      if (event.type === 'service_start' && event.server_id !== null) {
        const waitingIndex = waitingCustomerIds.indexOf(event.customer_id)
        if (waitingIndex >= 0) waitingCustomerIds.splice(waitingIndex, 1)
        servingByServer[event.server_id] = event.customer_id
        return
      }
      if (event.type === 'service_end') {
        const waitingIndex = waitingCustomerIds.indexOf(event.customer_id)
        if (waitingIndex >= 0) waitingCustomerIds.splice(waitingIndex, 1)
        if (event.server_id !== null && servingByServer[event.server_id] === event.customer_id) {
          delete servingByServer[event.server_id]
        }
        servedCustomerIds.push(event.customer_id)
        return
      }
      if (event.type === 'abandon') {
        const waitingIndex = waitingCustomerIds.indexOf(event.customer_id)
        if (waitingIndex >= 0) waitingCustomerIds.splice(waitingIndex, 1)
        abandonedCustomerIds.push(event.customer_id)
      }
    })

    return {
      queueId: laneKey,
      serverId: serverByLane.get(laneKey) ?? null,
      arrived: arrivedIds.size,
      waitingCustomerIds,
      servingByServer,
      servedCustomerIds,
      abandonedCustomerIds,
    }
  })
}

export interface PlaybackSnapshot {
  segmentId: string | number
  eventCount: number
  arrived: number
  waitingCustomerIds: number[]
  servingByServer: Record<string, number>
  servedCustomerIds: number[]
  abandonedCustomerIds: number[]
  latestArrivalId: number | null
  averageWaitMinutes: number | null
  utilization: number | null
  accountingMatches: boolean
}

function activeSegmentId(trace: SimulationTrace, simulationTime: number): string | number {
  if (trace.segments.length === 0) return 0
  const candidate = trace.trace_hours > 0
    ? Math.floor((Math.max(0, simulationTime) + TIME_EPSILON) / trace.trace_hours)
    : 0
  return trace.segments.reduce<string | number>((active, segment) => {
    if (typeof segment.segment_id !== 'number' || typeof active !== 'number') return active
    return segment.segment_id <= candidate && segment.segment_id >= active
      ? segment.segment_id
      : active
  }, trace.segments[0].segment_id)
}

export function derivePlaybackSnapshot(
  trace: SimulationTrace,
  simulationTime: number,
): PlaybackSnapshot {
  const segmentId = activeSegmentId(trace, simulationTime)
  const processed = trace.trace.filter((event) => event.t <= simulationTime + TIME_EPSILON)
  const events = processed.filter((event) => event.segment_id === segmentId)
  const arrivedIds = new Set<number>()
  const waitingCustomerIds: number[] = []
  const servingByServer: Record<string, number> = {}
  const serviceStarts = new Map<number, number>()
  const arrivalTimes = new Map<number, number>()
  const servedCustomerIds: number[] = []
  const abandonedCustomerIds: number[] = []
  let latestArrivalId: number | null = null
  let waitTotalHours = 0
  let waitCount = 0
  let completedBusyHours = 0

  events.forEach((event) => {
    if (event.type === 'arrival') {
      arrivedIds.add(event.customer_id)
      waitingCustomerIds.push(event.customer_id)
      arrivalTimes.set(event.customer_id, event.t)
      latestArrivalId = event.customer_id
      return
    }

    if (event.type === 'service_start' && event.server_id !== null) {
      const waitingIndex = waitingCustomerIds.indexOf(event.customer_id)
      if (waitingIndex >= 0) waitingCustomerIds.splice(waitingIndex, 1)
      const arrivalTime = arrivalTimes.get(event.customer_id)
      if (arrivalTime !== undefined) {
        waitTotalHours += Math.max(0, event.t - arrivalTime)
        waitCount += 1
      }
      servingByServer[event.server_id] = event.customer_id
      serviceStarts.set(event.customer_id, event.t)
      return
    }

    if (event.type === 'service_end') {
      const waitingIndex = waitingCustomerIds.indexOf(event.customer_id)
      if (waitingIndex >= 0) waitingCustomerIds.splice(waitingIndex, 1)
      if (event.server_id !== null && servingByServer[event.server_id] === event.customer_id) {
        delete servingByServer[event.server_id]
      }
      const serviceStart = serviceStarts.get(event.customer_id)
      if (serviceStart !== undefined) {
        completedBusyHours += Math.max(0, event.t - serviceStart)
        serviceStarts.delete(event.customer_id)
      }
      servedCustomerIds.push(event.customer_id)
      return
    }

    if (event.type === 'abandon') {
      const waitingIndex = waitingCustomerIds.indexOf(event.customer_id)
      if (waitingIndex >= 0) waitingCustomerIds.splice(waitingIndex, 1)
      abandonedCustomerIds.push(event.customer_id)
    }
  })

  const segment = trace.segments.find((item) => item.segment_id === segmentId)
  const segmentStart = typeof segmentId === 'number' ? segmentId * trace.trace_hours : 0
  const elapsedInSegment = Math.max(0, simulationTime - segmentStart)
  let busyHours = completedBusyHours
  serviceStarts.forEach((start) => {
    busyHours += Math.max(0, simulationTime - start)
  })
  const utilization = elapsedInSegment > 0 && segment && segment.c > 0
    ? Math.min(1, busyHours / (elapsedInSegment * segment.c))
    : null
  const accounted = waitingCustomerIds.length
    + Object.keys(servingByServer).length
    + servedCustomerIds.length
    + abandonedCustomerIds.length

  return {
    segmentId,
    eventCount: processed.length,
    arrived: arrivedIds.size,
    waitingCustomerIds,
    servingByServer,
    servedCustomerIds,
    abandonedCustomerIds,
    latestArrivalId,
    averageWaitMinutes: waitCount > 0 ? (waitTotalHours / waitCount) * 60 : null,
    utilization,
    accountingMatches: arrivedIds.size === accounted,
  }
}

export function nextPlaybackTime(trace: SimulationTrace, simulationTime: number): number {
  const next = trace.trace.find((event) => event.t > simulationTime + TIME_EPSILON)
  return next?.t ?? Math.max(trace.total_hours, simulationTime)
}

export function advancePlaybackTime(
  simulationTime: number,
  elapsedMilliseconds: number,
  traceEnd: number,
  speed: number,
  playbackSecondsAt1x = 60,
): number {
  if (traceEnd <= 0 || playbackSecondsAt1x <= 0) return 0
  const hoursPerMillisecond = traceEnd / (playbackSecondsAt1x * 1000)
  return Math.min(
    traceEnd,
    simulationTime + Math.max(0, elapsedMilliseconds) * hoursPerMillisecond * Math.max(0, speed),
  )
}

export function formatSimulationTime(hours: number): string {
  const totalSeconds = Math.max(0, Math.floor(hours * 60 * 60))
  const hh = Math.floor(totalSeconds / 3600)
  const mm = Math.floor((totalSeconds % 3600) / 60)
  const ss = totalSeconds % 60
  return [hh, mm, ss].map((value) => String(value).padStart(2, '0')).join(':')
}
