# System remediation design

Implement the user-approved system-first plan without changing observations or deploying the running stack. Add optional minimum staffing (default 1) and maximum waiting minutes (default disabled), enforce all constraints simultaneously, and expose feasibility and effective inputs. Retain utilization domain (0,1] and default 0.7. Use Monte Carlo failure allowance 0.05 across paths and preserve utilization-threshold analytical perturbation with Wilson 95% intervals. DES must report actual busy-time utilization and honor requested duration without an unstable-case override.

Preserve existing response envelopes and optional legacy snapshots; additive metadata identifies model, provenance, assumptions, and effective constraints/costs. Existing stored calculations must not be relabeled as verified under a new engine. No new simulation model or raw-data correction is included. Unsupported simulation coverage remains explicit. New labels are bilingual.
