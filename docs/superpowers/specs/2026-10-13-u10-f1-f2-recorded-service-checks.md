# U10 F1/F2: checks with recorded service times for one shared line

Status: IMPLEMENTED 2026-10-13, uncommitted (owner asked: F2 "choose the best", F1 "verify before apply"). Branch `feat/ux-u1-shell`. §5 stays a proposal.

## 1. Findings (VERIFIED, file:line on `dd367b97`)

- F2. `run_validation` passes the saved plan's result rows to `validate_with_simulation` (`backend/api/workflow.py:1434-1441`). Result rows carry `service_cv` but no `variance`, `K` or `theta` (`backend/queueing_engine/services/optimization.py:357-389`). `validate_with_simulation` forwards only those three keys (`backend/queueing_engine/simulation/simulation.py:1391`), so the shared dispatcher sees none of them and every M/G/c, M/M/c/K, M/G/c/K and Erlang-A plan is checked as M/M/c (or M/M/1).
- F1. The standalone DES gets the plan's model inputs from the calculation snapshot (`workflow.py:540-585`), so an M/G/c plan is refused there: DES and Monte Carlo cover M/M/1, M/M/c and separate M/G/1 only (`simulation.py:169-170`). The shared Decision needs supported DES for every period (`workflow.py:1577-1581`), so a shared line from customer records stops at "insufficient evidence".
- Shared customer-record uploads already store each period's recorded service durations (`backend/data/analysis_ingestion.py:300-317`: `variance` = population variance of `service_hours`, `mu` = 1 / mean, `service_samples_hours`, `service_time_source` = empirical).
- `mgc` takes utilization and stability from `mmc` (`backend/queueing_engine/models/queue_models.py:231-239`). The Monte Carlo fails a trial only on utilization (`simulation.py:1199-1210`), so its pass/fail result for M/G/c equals M/M/c for the same seed; only its wait estimate differs.

## 2. Basis (VERIFIED from the source text)

Green, Kolesar and Whitt, "Coping with time-varying demand when setting staffing requirements for a service system", Production and Operations Management 16(1) 13-39, 2007 (author preprint, columbia.edu/~ww2040/TimeVarying1217.pdf):
- staffing must meet "a targeted level of service performance in each staffing interval" (p. 9);
- after an analytical method, simulate "to verify that the suggested staffing levels indeed produce the desired" performance (p. 10);
- for non-exponential service, estimate "the service-time distribution by its empirical distribution and use that in a simulation of the resulting M/GI/s model" (p. 11).

NovaQ precedent: separate M/G/1 DES already resamples recorded durations (`simulation.py:661-683`, `:760`).

## 3. Change (F2, which also resolves F1 for the period-by-period checks)

1. DES: an M/G/c segment is supported only when it carries recorded durations (`service_time_source` empirical, a non-empty list of finite positive hours) whose mean and population variance equal the plan's `1/mu` and `variance` (relative tolerance 1e-9). Each service time is drawn uniformly from those durations (`rng.choice`), as for separate M/G/1. Every other case keeps today's refusal. M/M/1 and M/M/c draws are unchanged.
2. Monte Carlo: M/G/c trials use `mgc` with the perturbed rates. A perturbed service rate `m = mu * f` divides every service time by `f`, so the variance becomes `variance * (mu / m)^2` (the service-time distribution is rescaled, its shape kept). Pass/fail is unchanged by construction (§1).
3. Validation and the standalone DES/MC: the plan's `variance`, `K` and `theta` come from the calculation snapshot, and the recorded durations from the plan's dataset row with the same period label. The durations are not stored in the validation result.
4. Not in scope: M/M/c/K, M/G/c/K and Erlang-A stay refused (now visibly, instead of being checked as M/M/c). Aggregate uploads with a variance but no recorded durations stay refused: NovaQ will not assume a distribution.

No pass/fail rule, threshold, cap or Decision rule changes. The existing shared Decision (`workflow.py:1627-1672`) applies unchanged.

## 4. Verification

- Reference cases: M/G/1 with recorded durations against the exact Pollaczek-Khinchine mean wait of the same empirical distribution; recorded exponential-like durations against Erlang C; constant durations (M/D/1) against the exact formula.
- Regression: M/M/1 and M/M/c DES/MC outputs identical before and after for fixed seeds; Monte Carlo pass/fail for M/G/c equals M/M/c for the same seed.
- Gates and mutation tests as for every phase.

## 5. Open, not changed here

- OD-UX-13 (pass/fail for the full-day run): proposal only. Use the separate-lanes rule (DES conserved and supported for every period; per-period Monte Carlo failure rate at most the cap with an adequate Wilson interval; FAIL > insufficient > PASS, `workflow.py:1220-1253`, `:2861-2900`) with the full-day run as the DES evidence. Needs the owner's GO.
- F16: see `handoff.md`.
