# Revision 2: count-valid selected-load inference

Date: 2026-10-19. **Status: APPROVED research COMPLETE with qualifications.** [Actual revision-2 results](../reports/2026-10-19-selected-load-revision-2-validation.md): 37 numerical groups, nine synthetic and three corrected actual-routing cases showed no detected undercoverage; all 60 retained fixture checks remained insufficient at n=20. The conditional proof does not establish deterministic PRNG independence or universal numerical coverage. Source integration, Docker and commit/push remain outside this approval. [Proposed integration scope](../plans/2026-10-19-selected-load-revision-2-integration-proposal.md). The preceding t candidate failed; its [record](../reports/2026-10-19-selected-load-method-calibration.md) remains unchanged.

## Decision and intended outcome

Reject the Student-t candidate as a general selected-load confidence method. Do not salvage it by choosing favorable seeds, lowering confidence, widening the allowed failure cap, treating zero variance as certainty, or assuming routed lane counts are Poisson. Preserve raw MC diagnostics and the original regression assertions.

Next proposed phase: prove and prototype a finite-sample count-mean bound whose assumptions can be established for each selected execution mode. If a valid bound is too wide with the existing 20-run maximum, the honest result is insufficient evidence. A useful or identical Decision label is not an acceptance criterion for mathematical validity.

## Concrete candidate to assess before any integration

One conservative research candidate is deterministic truncation plus a tail allowance and a bounded-mean concentration inequality. It avoids assuming Normal or Poisson *lane* counts. The mathematical adaptation below is a proposed derivation, not a verified NovaQ implementation.

Let X be a nonnegative lane-period arrival count from one complete replication. First establish a valid domination `X <= N` under a coupling, where N has a known Poisson envelope with expectation Lambda from frozen input rates and the applicable full horizon. Actual admission pauses, date boundaries, period labels, missing rows and duration transformations must be audited; a log description of a Poisson stream is insufficient proof. In particular, `separate_optimization.py:1181-1219` can pause admission while no lane accepts arrivals; do not assume each realized routed count is Poisson or that a naive nominal-period equality holds.

For an integer cutoff B>0 fixed from inputs before observing replication outcomes, define `Y=min(X,B)`. Under the domination assumption,

```
0 <= E[X]-E[Y] <= delta(B)
delta(B) = E[(N-B)+]
         = Lambda * P(N >= B) - B * P(N >= B+1).
```

If n replication vectors are independent with common frozen-input law, Hoeffding's bounded-variable inequality gives radius

```
epsilon = B * sqrt(log(2*m/alpha) / (2*n))
```

for each truncated sample mean, with union allocation over m required pairs. Proposed mean-count bounds are `max(0, mean(Y)-epsilon)` through `mean(Y)+epsilon+delta(B)`, optionally intersected with a separately proven known mean envelope. Divide by the actual positive duration in hours to obtain customers/hour. Preserve whole replication vectors; within-vector lane independence is unnecessary for a union bound. This construction still depends on independent replications and the valid domination proof. It does not account for unknown real-world arrival/service parameters.

The bounded-variable inequality originates in [Hoeffding (1963), Probability Inequalities for Sums of Bounded Random Variables](https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830). The truncation/Poisson-envelope adaptation is a proposed project derivation and requires independent review, stable tail evaluation and reference cases. It is not a claim that the paper validates NovaQ routing or its seed scheme.

Expected limitation: a whole-day envelope can make these bounds very wide at n=20. Practical precision, especially near the 5% allowance, is UNKNOWN. A proof-valid but uninformative interval must be reported as insufficient; do not change the replication bound or introduce adaptive stopping under this proposal.

## Proposed bounded work package

1. New external audit only: inspect/prove the count envelope and replication/seed assumptions for period-independent, representative-day and per-date modes. Establish whether existing per-period seed reuse affects vector-independence claims. Missing or unsupported assumptions stop that mode's candidate assessment; do not modify RNG/DES behavior.
2. Independently validate the derivation, tail allowance and numerical stability, including B=1, zero demand, unequal durations, sparse counts, dependent coordinates and all three mode mappings. Confirm that truncation changes only the inferential auxiliary statistic, never stored means, source data or simulated customers.
3. Prespecify a deterministic input-only B rule, coverage/precision cases and acceptance before execution. Run independent-batch calibration, count counterexamples from revision 1, and routing-specific holdout/reference experiments. Preserve all failures and abstentions.
4. Assess likely usefulness under the current 1-20 bounds and largest supported inputs, including storage/compute costs. If valid but uninformative, report that outcome and consider a separately specified evidence-collection change; no silent fallback or increased count.
5. Only after a reviewed successful method report, revise the application specification with exact method/version fields, legacy/currentness/report behavior, frontend copy and integration tests. Application edits, rebuilding, activating, committing and pushing remain separate from this research package.

Approved scope: **isolated proof/prototype/calibration for revision 2 only**, without application changes. A revised approved integration plan is needed after its evidence exists. This staged boundary is required because the preceding plan explicitly stops on candidate failure and forbids silently substituting another estimator.
