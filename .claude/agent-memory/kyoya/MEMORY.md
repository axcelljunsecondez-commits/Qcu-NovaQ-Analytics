# Kyoya review memory index

## Role and continuity

- Role: independent security, code review, boundary enforcement and evidence verification. Follow the active checkout's `AGENTS.md`; permanent rules stay there.
- Application work is findings-only. Write review memory here; return implementation corrections through the parent to Chrome or Hayato.
- Confirm the exact checkout/revision and relevant dirty source before relying on saved findings. Memory and other agents' reports do not prove current behavior.
- Reuse a stable review ID and finding IDs. Keep detailed records in `reviews/<stable-review-id>.md`, with inspected scope, actual verification, unresolved gates, closure evidence and next action.
- Keep this index under 200 lines. The parent coordinates ownership; this index is not a lock or scheduler. Store no secrets or raw customer data.

## Setup provenance

VERIFIED at setup on 2026-10-29: configuration was prepared in `C:/Users/Administrator/Desktop/QUEUING_THEORY_NOVAMART/NovaQ`, branch `main`, base HEAD `ea14e2713ac9950bc032b4a969c1c3bf759feb93`. This identifies the configuration task, not an application security/correctness baseline or evidence about another worktree or production.

Definition: `.claude/agents/kyoya.md`. Current roster and usage: `docs/superpowers/plans/2026-10-29-kyoya-reviewer-and-hayato-rename.md`. The backend agent is now `hayato` (previously `gokudera`); the frontend agent is `chrome`.

## Review index

- [shared-upload-20261030](reviews/2026-10-30-shared-upload.md): scoped source and local evidence review COMPLETE;
  scoped source review complete against base 2e0e3606 plus linked final hashes.
  Final reviewed page is 4f5dae26...e83b97; confirmation-copy and duplicate-conflict
  display deltas preserve guards and use existing wording.
  K-UP-1 (pending closing read/hidden draft) is closed in reviewed source with
  regression evidence. No supported open source finding in scope; corrected full
  frontend final suite passed 805/92 files; TS/lint/build passed; parent browser and
  isolated preservation/staleness evidence inspected. Replacement backend suite
  passed 3331/125 skips/1 existing xfail/9 subtests. Root lint/
  mypy old-output failures and earlier test attempts stay explicitly recorded.

The setup record originally had no delegated application review; that historical
state is superseded by the review indexed above. No Claude invocation or automatic
runtime memory loading is claimed. Application test results and finding closure
must be read from the specific review record with its source identity and limits.
