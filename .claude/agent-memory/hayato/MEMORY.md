# Hayato backend agent memory index

## How to resume

- Read the active checkout's `AGENTS.md`, `memory.md`, latest relevant `handoff.md` entries and task spec/plan. Permanent rules stay there.
- Confirm checkout/branch/HEAD and dirty files before relying on a task record. History and saved notes do not prove current behavior.
- Match the delegated goal to a record before repeating investigation or implementation. Resume the same task identifier when appropriate.
- One owner writes a task and its record at a time. This index is advisory, not a concurrency lock; the parent coordinates ownership.
- Store detailed records in `tasks/<stable-task-id>.md`. Include ownership, source references, actual verification, relevant dirty-source identity and the next action. Keep this index under 200 lines.
- Read/write this memory explicitly if automatic memory loading is unavailable. Report any inability to persist the handoff.

## Setup provenance

VERIFIED at setup on 2026-10-29: the repository root was `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ`, branch `main`, HEAD `3ee8fe2c5d3f1521e37255959f2383e67e374b4c`. This identifies where the configuration was prepared; it is not a backend verification baseline or a claim about another worktree, GitHub or production.

The role is defined in `.claude/agents/novaq-backend.md`. Setup specification and usage are in `docs/superpowers/specs/2026-10-29-claude-backend-subagent.md` and `docs/superpowers/plans/2026-10-29-claude-backend-subagent-plan.md`.

## Backend task index

- [2026-11-17 D2 Current DES accounting (v5)](tasks/2026-11-17-d2-current-des-accounting.md): CLOSED; Kyoya PASS; merged via PR #60 (merge 5f4a884e), released 2026-11-17.
- [2026-11-17 break check PDF/Excel + K-PR58-1..5](tasks/2026-11-17-break-check-pdf.md): CLOSED; Kyoya PASS; merged via PR #59 (merge c2316ed4), released 2026-11-17.
- [2026-11-16 follow-ups K1/K2/K3 + Cobalt](tasks/2026-11-16-followups-reports-pdf-cobalt.md): CLOSED; Kyoya PASS; merged via PR #57 (merge 69613970), released 2026-11-16.
- [2026-11-11 SEED-001 guard finish](tasks/2026-11-11-seed-001-guard-finish.md): CLOSED; Kyoya PASS; merged via PR #51 (merge 8b51e45e).
- [2026-11-10 remove dead review leftovers](tasks/2026-11-10-remove-dead-review-leftovers.md): CLOSED; Kyoya PASS; merged via PR #50 (merge 6d46a01a).
- [2026-11-10 simulation-actions integrate](tasks/2026-11-10-simulation-actions-integrate.md): CLOSED; Kyoya PASS; merged via PR #49 (merge 9baeee43).
- [2026-10-30 shared upload simplification](tasks/2026-10-30-shared-upload-simplification.md): in_progress; additive shared aggregate preview/apply and isolated backend verification. Starting HEAD 2e0e3606; no completed tests claimed yet.
- [2026-11-10 banner + workbook focus](tasks/2026-11-10-banner-and-workbook-focus.md): CLOSED; commit 2e104cfe merged to origin/main via PR #47 (merge 702a6aa1), VERIFIED 2026-11-10.
- [2026-11-09 upload follow-ups D1-D4/T1 + K-UF-1/2](tasks/2026-11-09-upload-preview-rate-bucket.md): CLOSED; round 2 (A1, B1, N1) commit 05e4cfa8 merged to origin/main via PR #46 (merge d87cb514), VERIFIED 2026-11-10.
