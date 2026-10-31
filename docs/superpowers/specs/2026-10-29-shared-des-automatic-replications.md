# Shared DES: one Run action with automatic replications

Date: 2026-10-29. Owner direction: remove user-managed repetitions and use the
separate-queue DES interaction pattern, preserving mathematical correctness.

## Verified baseline

- ContinuousRunBar exposes a Repeated days numeric field under Advanced. It submits
  replications and seed to the existing continuous API and checks the returned limits.
- Separate DES already repeats a candidate internally with controlled seeds
  (separate_optimization.evaluate_candidate_with_des_replications). Shared DES also
  already repeats the same scenario inputs with spawned seed streams
  (shared_replications.run_shared_replications). Their queue disciplines remain distinct.
- The server supplies default_replications (currently 5), max_replications (currently 9),
  expected_customers_per_day and max_expected_customers_per_run (currently 2,900).
- Saved run params, cards, charts, replay and Decision already use actual persisted
  replication counts. A single shared line does not imply a single stochastic execution.

## Bounded change

Remove only the shared full-day repetition input and its local editable state. One Run
full operation action chooses the server default automatically, bounded by the server's
maximum repetitions and expected-customer budget. Use only server-returned values; no
new arrival calculation, data aggregation, seed scheme, model or simulation algorithm.

Automatic count is the smaller of the server default, repetition limit, and the number
of complete replications affordable under its expected-customer cap. Zero expected
customers does not restrict the count. Missing/invalid budget metadata refuses a request.
If even one replication exceeds the cap, explain the existing limit and submit nothing.
Do not change demand or silently run a partial operating day to fit the cap.

This budget selection replaces the user's existing manual lowering of the count; it
does not relax the cap or promise that the selected count establishes statistical precision.
For the supplied CSV (107.5 expected customers per 13-hour day), the current default of
5 remains unchanged, as do its generated samples and numerical results at the same seed.

Keep seed access under Advanced for reproducibility. Keep factual stored replication
counts, uncertainty/range captions and the replay-day selector: they identify which
execution produced the shown trace. Keep all key metrics and Decision/cache behavior.
Do not force one replication or copy the separate-queue simulation engine.

## Scope and prior decisions

Files: frontend/src/components/queueSimulation/ContinuousRun.tsx;
frontend/src/lib/continuous.ts; their existing page/helper test files; this spec, its
implementation plan, report and owned verification artifacts.

This owner request revises the editable count part of OD-B4a-3. The nominal default,
server limits and statistical aggregation remain. No backend/API/DB/engine/locale/wording
policy change, production activation, commit or push. Existing labels cover the action,
seed and cap refusal. Preserve the earlier four-file workflow repair.

## Acceptance

1. No Repeated days input exists, including when Advanced is open. One click sends one
   API request with the default count and seed when affordable.
2. At 600 expected customers/day with a 2,900 cap, choose 4 complete replications. At
   580 choose 5. Above 580 choose at most 4. Do not increase a smaller server default.
3. Respect a smaller server repetition limit; preserve zero-demand and unknown-data
   distinctions. Refuse invalid metadata or a day that cannot fit once, without a request.
4. Key metrics, actual persisted counts, replay selection, seeded reproduction, current/
   suggested input provenance and Decision invalidation retain regression coverage.
5. Verify engine and backend files unchanged; run relevant source gates and browser checks.

Status at creation: specification for the owner's requested implementation, not execution proof.
