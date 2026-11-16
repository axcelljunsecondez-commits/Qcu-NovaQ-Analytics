# Current and Suggested break schedules

APPROVED SCOPE: on 2026-11-16 the owner explicitly requested implementation: optimized NovaQ breaks apply only to Suggested plans; Current uses the uploaded break schedule. This supersedes the 2026-10-23 supervisor specification's global Setup-write behavior. Protected Current DES changes below are necessary to that request and were explained in the preceding owner-file inspection/proposal. No release, operational-data mutation, migration, commit, or push is authorized.

## Evidence and invariant

Base: `8f611d879fdb64373f526a24b540c721934d81ba`. Workbook reviewed read-only: owner-supplied `NOVAMART_DATA_UPLOAD.xlsx`, SHA256 `29781130e4c99e5d0730e2d21aff7a78daaec0e986dbb8ad713b598991af13be`. It has 1,600 events, 14 dates, five staff rows and 15 daily break rows. There are zero service starts inside scheduled breaks, 103 services crossing a scheduled start, and 192 arrivals to lanes during breaks. Actual attendance is not recorded.

The workbook upload already maps breaks into Analysis Setup. Current ignores them; optimizer Apply and Supervisor Apply overwrite Setup; schema-2 scenario verification/execution/reporting always use Setup. The invariant is: **Analysis Setup is Current's baseline. A suggested break schedule belongs to its saved scenario and never mutates that baseline.** Uploading a replacement workbook or explicitly saving manual Setup corrections remains an intentional baseline change. Do not claim that a legacy baseline already changed by old Apply is the original upload; restoration requires the source or owner-confirmed corrections. This implementation does not silently reconstruct or backfill operational data.

## Current execution

Keep dedicated FIFO lanes, per-lane arrival rates, service resampling, per-date/representative-day grouping, seeds, and existing measurement/closing definitions. Add service availability for validated baseline breaks. The intervals are half-open scheduled wall-clock windows mapped onto the operating clock.

- No new service starts during a lane's scheduled window. A service already underway finishes without interruption.
- Arrivals and waiting customers remain in their original lane; do not skip arrivals, reroute customers, or empty the whole queue before pausing service.
- Resume at the scheduled end, subject to the existing staffing/closing rules. A service crossing the entire window may leave no idle break time. Do not claim full actual break attendance.
- Preserve waiting vs service units: service samples remain `service_end - service_start`; no recorded waiting is added again. Do not separately discount service rates or staffing for the same break.
- Playback events and metrics come from one execution. Show scheduled windows, finishing an ongoing service, actual modeled idle interval, and resumed availability. Define ties at start/end explicitly.
- Validate unknown lanes, overlap, malformed times/durations and out-of-shift windows even for stored data. Reject unmappable/noncontiguous operating clocks rather than silently shifting breaks.
- Preserve no-break outputs exactly. Add a new Current basis marker and require old evidence to rerun. Per-date compact regeneration uses the same engine and break policy, with trace digests retaining integrity.

## Suggested persistence and execution

Add an optional `calculation.break_optimization` descriptor containing strictly `max_shift_minutes` (whole 0–240, multiple of 15) to existing schema-2 scenario requests. Derive target and seed from existing verified options. Never accept client-supplied optimized times as authoritative.

A shared helper without workflow/scenario import cycles recomputes the current break optimizer on the baseline, validates the proposed Setup, and exposes the existing conservation, wait interval and break-cap blockers. Scenario save reruns staffing on that proposed Setup and verifies submitted results. Keep `calculation.setup_hash` bound to baseline Setup. Server-stamp `plan_breaks` and `plan_setup_hash`; selected DES/MC/validation and plan reports resolve that effective plan Setup. Old scenarios without the descriptor retain their original Setup-based behavior. Existing generation/freshness/ownership protections remain effective; invalid/tampered plan setup identities refuse use.

Both legacy break Apply and Supervisor Apply become nonmutating draft confirmations: retain existing response fields as far as truthful, return baseline `analysis` unchanged, and add explicit `plan_setup`/destination information. A draft confirmation alone does not create/select a saved scenario. Preserve preview-hash and final freshness checks. The Suggested UI confirms plan-only changes, then saves/uses the verified scenario with the optimization descriptor. It must not replace the Current analysis cache or invalidate Current due solely to a draft confirmation. Do not claim optimized breaks were saved before scenario creation succeeds.

Suggested replay and reports use scenario breaks. Current replay uses baseline breaks. Update both English and Filipino labels and test that switching plans changes only Suggested schedules.

## Boundaries and checks

No queueing formula, model selection, arrival/service calculation, optimization objective, paired interval, Suggested routing/break policy, Current MC/validation mathematics, or Decision statistics change. Current DES break handling changes only as explicitly described. No database migration or dependency addition.

Verify deterministic timing reference cases, conservation/lane retention, boundaries across segments/shifts, compact/date replay, exact no-break snapshots, upload mapping, nonmutating Apply, server-derived plan verification/tampering/freshness, two saved plans with different breaks, plan selection/execution/reports, and UI cache isolation. Run applicable repository gates and independent review. Runtime claims require executed checks; deployment is not in scope.
