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

No application review, security audit or numerical validation has been delegated to or completed by Kyoya yet. No Claude invocation, passing application tests, closed findings or runtime memory loading are claimed by this index.
